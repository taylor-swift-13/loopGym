from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from rl_pipeline.common.program import parse_program, strip_postcondition
from rl_pipeline.common.state import State, eval_predicate, first_falsifying_state
from rl_pipeline.inference import InferenceFramework, MockRolloutProvider
from rl_pipeline.inference import inference as inference_module
from rl_pipeline.reward import annotate
from rl_pipeline.reward.filters import HoudiniFilter, PositiveFilter
from rl_pipeline.reward import service
from rl_pipeline.reward import io as reward_io
from rl_pipeline.reward.score_file import score_file
from rl_pipeline.sampler import ExampleSampler
from rl_pipeline.sampler import cexec


ROOT = Path(__file__).resolve().parents[1]


class PredicateRegressionTests(unittest.TestCase):
    def test_positive_filter_checks_every_reachable_state(self):
        program = parse_program(
            "void f(void) { int x = 0; while (x < 10000) { x++; } }"
        )
        positives = [State(vars={"x": value}) for value in range(10000)]

        witness = first_falsifying_state("x != 4501", positives)

        self.assertIsNotNone(witness)
        self.assertEqual(witness.vars["x"], 4501)
        self.assertEqual(
            PositiveFilter().filter(program, 0, ["x != 4501"], positives),
            [],
        )

    def test_nested_implication_and_equivalence_work_scalar_and_vector(self):
        expression = (
            "(x > 0 ==> y > 0) && "
            "((x == 1) <==> (y == 1)) && z == 0"
        )
        states = [
            State(vars={"x": 0, "y": 0, "z": 0}),
            State(vars={"x": 1, "y": 1, "z": 0}),
            State(vars={"x": 1, "y": 0, "z": 0}),
        ]

        self.assertEqual(
            [eval_predicate(expression, state) for state in states],
            [True, True, False],
        )
        self.assertIs(first_falsifying_state(expression, states), states[2])

    def test_positive_dedup_preserves_distinct_pre_values(self):
        positives = [
            State(vars={"n": 0}, pre={"n": 65}),
            State(vars={"n": 0}, pre={"n": 0}),
        ]

        deduplicated = ExampleSampler._dedup(positives)

        self.assertEqual(deduplicated, positives)
        program = parse_program("void f(int n) { while (n > 0) { n--; } }")
        invariant = r"n == 0 ==> \at(n,Pre) == 65"
        self.assertEqual(
            PositiveFilter().filter(program, 0, [invariant], deduplicated),
            [],
        )


class ParserAndAnnotationRegressionTests(unittest.TestCase):
    def test_strip_postcondition_keeps_requires_in_shared_block(self):
        source = (
            "/*@ requires n >= 0; ensures \\result == 0; */\n"
            "int f(int n) { while (n > 0) { n--; } return n; }"
        )

        stripped = strip_postcondition(source)

        self.assertIn("requires n >= 0;", stripped)
        self.assertNotIn("ensures", stripped)
        self.assertNotIn(r"\result", stripped)

        line_source = (
            "//@ requires n >= 0; ensures \\result == 0;\n"
            "int g(int n) { while (n > 0) { n--; } return n; }"
        )
        line_stripped = strip_postcondition(line_source)
        self.assertIn("requires n >= 0;", line_stripped)
        self.assertNotIn("ensures", line_stripped)
        line_program = parse_program(line_source)
        self.assertEqual(line_program.requires, "n >= 0")
        self.assertEqual(line_program.post, r"\result == 0")

    def test_parser_skips_helper_before_loop_function(self):
        source = (
            "int unknown(void) { return 0; }\n"
            "void target(void) { int x = 0; while (x < 1) { x++; } }"
        )

        program = parse_program(source)

        self.assertEqual(program.func_name, "target")
        self.assertEqual(program.loop.guard, "x < 1")

    def test_prefix_and_postfix_updates_are_loop_assigns(self):
        source = (
            "void f(void) { int x = 0; int y = 3; "
            "while (x < y) { x++; --y; } }"
        )
        program = parse_program(source)

        annotated = annotate.build_annotated(program, ["x <= y + 1"])

        self.assertIn("loop assigns x, y;", annotated)

    def test_parenthesized_initializers_and_globals_are_tracked(self):
        source = (
            "unsigned int g; void f(int n) { "
            "int k = n % (g + 1); int q = 4 * (n - g); "
            "while (g < n) { g++; k = q; } }"
        )

        program = parse_program(source)

        self.assertEqual(program.pre_vars, ["g", "n", "k", "q"])
        self.assertIn("g", program.unsigned_vars)
        self.assertEqual(dict(program.local_inits)["k"], "n % (g + 1)")
        self.assertEqual(dict(program.local_inits)["q"], "4 * (n - g)")

    def test_unsupported_loop_shapes_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "for loops are not supported"):
            parse_program("void f(void) { for (int i = 0; i < 3; i++) {} }")
        with self.assertRaisesRegex(ValueError, "multiple loops are not supported"):
            parse_program(
                "void f(void) { int x = 0; while (x < 1) { x++; } "
                "while (x < 2) { x++; } }"
            )
        with self.assertRaisesRegex(ValueError, "scalar integer parameters"):
            parse_program("void f(int *p) { while (*p) { (*p)--; } }")

    def test_state_render_includes_pre_values(self):
        rendered = State(vars={"n": 0}, pre={"n": 65}).render()

        self.assertEqual(rendered, "n == 0; Pre: n == 65")


class SyntaxScrubRegressionTests(unittest.TestCase):
    def test_bad_superstring_does_not_remove_valid_invariant(self):
        source = "void f(void) { int x = 0; while (x < 2) { x++; } }"
        program = parse_program(source)

        def fake_frama(command, **_kwargs):
            path = Path(command[-1])
            lines = path.read_text(encoding="utf-8").splitlines()
            bad_line = next(
                (index for index, line in enumerate(lines, 1)
                 if line.strip() == "loop invariant x >= 0 +;"),
                None,
            )
            if bad_line is not None:
                return SimpleNamespace(
                    returncode=1,
                    stdout=f"{path}:{bad_line}: user error: invalid expression\n",
                    stderr="",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=fake_frama):
            survivors = HoudiniFilter()._syntax_scrub(
                program, 0, ["x >= 0", "x >= 0 +"]
            )

        self.assertEqual(survivors, ["x >= 0"])


@unittest.skipUnless(shutil.which("gcc"), "gcc is required for sampler tests")
class SamplerIntegrationRegressionTests(unittest.TestCase):
    def test_offline_jsonl_scoring_writes_structured_rows(self):
        source = "void f(void) { int x = 0; while (x < 2) { x++; } }"
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory, "rollouts.jsonl")
            output_path = Path(directory, "rewards.jsonl")
            reward_io.write_rows(str(input_path), [{
                "group_id": "g0",
                "program": source,
                "rollouts": [
                    {"invariants": ["x >= 0"]},
                    {"invariants": ["1 == 1"]},
                ],
            }])

            with mock.patch(
                "rl_pipeline.reward.score_file.filters.auto_filter",
                return_value=PositiveFilter(),
            ):
                stats = score_file(
                    str(input_path),
                    str(output_path),
                    reward_io.IOConfig(),
                    sampler_kwargs={"n_runs": 1, "seed": 0},
                )

            rows = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(stats["failed"], 0)
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows[0]["invariants"], list)
        self.assertIsInstance(rows[0]["survivors"], list)

    def test_oracle_sampling_repeats_a_fixed_valid_input(self):
        inputs = cexec.sample_inputs(
            ["x"],
            {"x": {"min": 0, "max": 0}},
            n_runs=5,
            requires="x == 0",
            single_ok=False,
        )

        self.assertEqual(inputs, [{"x": 0}] * 5)

    def test_unsigned_linear_234_stays_nonnegative(self):
        source = (ROOT / "src/input/linear/234.c").read_text(encoding="utf-8")
        program = parse_program(source)

        examples = ExampleSampler(source, n_runs=2).sample()

        self.assertIn("N", program.unsigned_vars)
        self.assertIn("x", program.unsigned_vars)
        self.assertGreater(len(examples.pos(0)), 0)
        self.assertTrue(all(state.vars["N"] >= 0 for state in examples.pos(0)))
        self.assertTrue(all(state.pre["N"] >= 0 for state in examples.pos(0)))
        self.assertEqual(
            PositiveFilter().filter(program, 0, ["N >= 0"], examples.pos(0)),
            ["N >= 0"],
        )
        instrumented = cexec.instrument(source, program)
        self.assertIn("N=%u", instrumented)
        self.assertIn("x=%u", instrumented)

    def test_invalid_c_fails_sampling_and_returns_http_400(self):
        source = (
            "void f(void) { int x = 0; while (x < 1) { "
            "this_is_not_c; x++; } }"
        )

        with self.assertRaisesRegex(ValueError, "gcc failed"):
            ExampleSampler(source, n_runs=1).sample()

        service._EXAMPLE_CACHE.clear()
        response = TestClient(service.build_app()).post(
            "/reward",
            json={
                "program": source,
                "rollouts": [{"invariants": ["x >= 0"]}],
                "sampler": {"n_runs": 1, "seed": 0},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("gcc failed", response.json()["detail"])

    def test_nondeterministic_guard_and_body_produce_no_negatives(self):
        programs = {
            "guard": (
                "int unknown(void); void f(void) { int x = 0; "
                "while (unknown()) { x++; } }"
            ),
            "body": (
                "int unknown(void); void f(void) { int x = 0; "
                "while (x < 100) { if (unknown()) break; x += 5; } }"
            ),
        }

        for label, source in programs.items():
            with self.subTest(label=label):
                examples = ExampleSampler(source, n_runs=1).sample()
                self.assertGreater(len(examples.pos(0)), 0)
                self.assertEqual(examples.neg(0), [])
                self.assertEqual(examples.groups(0), [])
                self.assertEqual(examples.stats[0]["relation"], 0)
                self.assertEqual(examples.stats[0]["bound_overrun"], 0)
                self.assertEqual(examples.stats[0]["bound_escape"], 0)

    def test_untracked_block_state_disables_synthetic_negatives(self):
        source = (
            "void f(void) { int x = 0; while (x < 10) { "
            "int temporary = x; temporary++; x++; } }"
        )

        examples = ExampleSampler(source, n_runs=1).sample()

        self.assertEqual(examples.neg(0), [])
        self.assertEqual(examples.stats[0]["untracked_state"], ["temporary"])


class InferenceRegressionTests(unittest.TestCase):
    class _IdentityFilter:
        @staticmethod
        def filter(program, loop_idx, invariants, positives=None):
            return list(invariants)

    @staticmethod
    def _fake_verifier(verify_result):
        class FakeOutputVerifier:
            def __init__(self, logger=None):
                self.syntax_correct = True
                self.syntax_error = "syntax Correct"
                self.validate_result = [True]
                self.verify_result = list(verify_result)

            def run(self, path):
                return None

        return FakeOutputVerifier

    def test_importing_inference_does_not_import_sampler(self):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command = (
            "import sys; import rl_pipeline.inference; "
            "raise SystemExit(int('rl_pipeline.sampler' in sys.modules))"
        )

        completed = subprocess.run(
            [sys.executable, "-c", command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_ensures_requires_a_successful_verification_goal(self):
        source = (
            "/*@ ensures \\result == 1; */ "
            "int f(void) { int x = 0; while (x < 1) { x++; } return 0; }"
        )
        framework = InferenceFramework(
            source,
            rollout_provider=MockRolloutProvider([["1 == 1"]]),
            invariant_filter=self._IdentityFilter(),
            n_rollouts=1,
            max_rerolls=0,
        )

        for verify_result, expected in (([], False), ([False], False), ([True], True)):
            with self.subTest(verify_result=verify_result):
                fake = self._fake_verifier(verify_result)
                with (
                    mock.patch.object(
                        inference_module.filters,
                        "frama_c_available",
                        return_value=True,
                    ),
                    mock.patch("src.output_verify.OutputVerifier", fake),
                ):
                    self.assertIs(framework._verify(source), expected)

    def test_reroll_count_reports_attempts_even_when_first_result_stays_best(self):
        class Provider:
            def __init__(self):
                self.calls = 0

            def __call__(self, _program, _n):
                self.calls += 1
                if self.calls == 1:
                    return [["x >= 0", "x <= 2"]]
                return [["1 == 1"]]

        framework = InferenceFramework(
            "void f(void) { int x = 0; while (x < 2) { x++; } }",
            rollout_provider=Provider(),
            invariant_filter=self._IdentityFilter(),
            n_rollouts=1,
            max_rerolls=1,
        )
        framework._verify = mock.Mock(return_value=False)

        result = framework.run()

        self.assertEqual(result.final_invariants, ["x >= 0", "x <= 2"])
        self.assertEqual(result.reroll_count, 1)


class CommandAndPackagingRegressionTests(unittest.TestCase):
    def test_refine_reward_rejects_an_out_of_range_loop_index(self):
        source = "void f(void) { int x = 0; while (x < 1) { x++; } }"
        service._EXAMPLE_CACHE.clear()
        with mock.patch.object(service, "_SHARED_FILTER", PositiveFilter()):
            response = TestClient(service.build_app()).post(
                "/refine_reward",
                json={
                    "program": source,
                    "pool": ["x >= 0"],
                    "refinements": [["x <= 1"]],
                    "loop_idx": 1,
                    "sampler": {"n_runs": 1, "seed": 0},
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("loop_idx 1 is out of range", response.json()["detail"])

    def test_score_file_accepts_valid_options_and_reports_failed_batches(self):
        score_module = importlib.import_module("rl_pipeline.reward.score_file")
        valid_argv = [
            "score_file",
            "--input", "input.jsonl",
            "--output", "output.jsonl",
            "--runs", "3",
            "--seed", "7",
            "--w-base", "0.7",
            "--w-marg", "0.3",
            "--reroll-threshold", "0.4",
            "--include-program",
            "--quiet",
        ]
        with (
            mock.patch.object(sys, "argv", valid_argv),
            mock.patch.object(
                score_module,
                "score_file",
                return_value={"failed": 0},
            ) as scorer,
        ):
            self.assertEqual(score_module.main(), 0)

        args = scorer.call_args.args
        self.assertEqual(args[0:2], ("input.jsonl", "output.jsonl"))
        self.assertEqual(args[3], {"n_runs": 3, "seed": 7})
        self.assertEqual(args[4:8], (0.7, 0.3, 0.4, True))

        failed_argv = [
            "score_file",
            "--input", "input.jsonl",
            "--output", "output.jsonl",
        ]
        with (
            mock.patch.object(sys, "argv", failed_argv),
            mock.patch.object(
                score_module,
                "score_file",
                return_value={"failed": 1},
            ),
        ):
            self.assertEqual(score_module.main(), 1)

    def test_docker_context_keeps_inference_package(self):
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        patterns = {
            line.strip().rstrip("/")
            for line in dockerignore.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "!"))
        }

        self.assertNotIn("rl_pipeline", patterns)
        self.assertNotIn("rl_pipeline/inference", patterns)
        dockerfile = (ROOT / "deploy/Dockerfile.inference").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "COPY rl_pipeline/inference/ /app/rl_pipeline/inference/",
            dockerfile,
        )


if __name__ == "__main__":
    unittest.main()

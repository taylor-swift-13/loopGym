import unittest
from pathlib import Path

from rl_pipeline.common.program import parse_program
from rl_pipeline.sampler import cexec


ROOT = Path(__file__).resolve().parents[1]


class SamplerRequirementTests(unittest.TestCase):
    def test_negated_comparison_is_not_used_as_a_literal_bound(self):
        requires = "!(n < 0)"
        constraints = cexec.param_constraints(requires, ["n"])

        self.assertEqual(constraints, {"n": {}})
        inputs = cexec.sample_inputs(
            ["n"], constraints, n_runs=8, requires=requires
        )
        self.assertEqual(len(inputs), 8)
        self.assertTrue(all(values["n"] >= 0 for values in inputs))

    def test_c_identifier_that_is_a_python_keyword_can_be_constrained(self):
        requires = "from >= 0 && from <= k && k <= 100"
        constraints = cexec.param_constraints(requires, ["from", "k"])

        inputs = cexec.sample_inputs(
            ["from", "k"], constraints, n_runs=8, requires=requires
        )

        self.assertEqual(len(inputs), 8)
        self.assertTrue(
            all(0 <= values["from"] <= values["k"] <= 100 for values in inputs)
        )

    def test_mixed_radix_grid_rotates_the_varying_dimension(self):
        params = ["a", "b", "c", "d"]
        constraints = {name: {} for name in params}
        candidates = [
            cexec._grid_tuple(
                params,
                constraints,
                candidate // len(params),
                seed=0,
                rotation=candidate % len(params),
            )
            for candidate in range(2 * len(params))
        ]

        for name in params:
            with self.subTest(name=name):
                self.assertGreater(len({values[name] for values in candidates}), 1)

    def test_collect_traces_resolves_integer_macros_and_globals(self):
        source = (
            "#define LIMIT 100\n"
            "int SIZE = 20;\n"
            "/*@ requires from >= 0; requires from <= SIZE; "
            "requires from <= LIMIT; */\n"
            "void f(int from) {\n"
            "  int x = from;\n"
            "  int local = 3;\n"
            "  while (x > 0) { x--; }\n"
            "}\n"
        )
        program = parse_program(source)
        constants = cexec._integer_source_constants(source)

        reachable, _overrun, _capped = cexec.collect_traces(program, n_runs=3)

        self.assertEqual(constants, {"LIMIT": 100, "SIZE": 20})
        self.assertTrue(reachable)
        self.assertTrue(all(0 <= state.pre["from"] <= 20 for state in reachable))

    def test_loopy_relational_requirement_constructs_full_run_set(self):
        source = (ROOT / "src/input/Loopy/26.c").read_text(encoding="ascii")
        program = parse_program(source)
        constraints = cexec.param_constraints(program.requires, program.params)

        inputs = cexec.sample_inputs(
            program.params,
            constraints,
            n_runs=12,
            requires=program.requires,
        )

        self.assertEqual(len(inputs), 12)
        self.assertTrue(
            all(
                values["leader_len"] > 0
                and values["ielen"] > 0
                and values["bufsize"] >= values["leader_len"]
                and values["bufsize"] >= 2 * values["ielen"]
                for values in inputs
            )
        )


if __name__ == "__main__":
    unittest.main()

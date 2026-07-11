# Inference Backend Setup

The default inference path is the in-process vLLM CLI exposed by
`rl_pipeline.inference`. `LLMRolloutProvider` is an optional Python API for a
local HuggingFace Transformers model or an OpenAI-compatible endpoint.

Run every command below from the repository root. This keeps module imports and
the canonical files under `prompt/` consistent.

## Common verification dependencies

Meaningful inference requires `frama-c`, `why3`, and `z3` on `PATH`. Configure
Why3 so Frama-C/WP can find Z3:

```bash
frama-c -version
z3 --version
why3 config detect
```

Without Frama-C, generation can still run, but `InferenceResult.verified` is
`None` and the real Houdini/verification path is unavailable.

## Default: vLLM CLI

Install vLLM in a GPU environment whose CUDA and PyTorch versions are supported
by the selected vLLM release. The `vllm` package supplies the Python runtime
needed by this path:

```bash
python3 -m pip install vllm
```

Run the CLI with a HuggingFace model ID or local model directory:

```bash
python3 -m rl_pipeline.inference \
  --model /path/to/hf-model \
  --inputs 'src/input/NLA_lipus/*.c' \
  --n-rollouts 8 \
  --output inference-results.jsonl
```

This creates one in-process `VLLMRolloutProvider` and batches all rollouts for a
program in one vLLM call. Generation, refinement, WP prechecks, and Houdini
pruning never receive the assertion; only final verification uses the original
target-bearing program.

The inference Docker image provides the containerized vLLM environment:

```bash
docker build -f deploy/Dockerfile.inference -t loopgym-inference .
docker run --gpus all --rm \
  -v /path/to/model:/model \
  -v /path/to/programs:/data \
  loopgym-inference \
  --model /model --inputs '/data/*.c' --output /data/results.jsonl
```

## Optional: local Transformers backend

The repository's Transformers adapter lives in `src/llm.py`. Install all of its
runtime dependencies; `accelerate` is required by `device_map="auto"`, and the
current module imports `openai` even when the local backend is selected:

```bash
python3 -m pip install openai torch transformers accelerate
```

Use it through `LLMRolloutProvider`:

```python
from pathlib import Path

from rl_pipeline.inference import InferenceFramework, LLMRolloutProvider
from src.config import LLMConfig
from src.llm import Chatbot

source = Path("src/input/linear/34.c").read_text()
config = LLMConfig(
    use_local=True,
    local_model_path="/path/to/hf-model",
    api_temperature=1.0,
    api_top_p=1.0,
    api_max_tokens=2048,
)
provider = LLMRolloutProvider(chat_fn=Chatbot(config).chat)
result = InferenceFramework(
    source,
    rollout_provider=provider,
    n_rollouts=4,
).run()
print(result.final_invariants, result.verified)
```

`local_model_path` must be a HuggingFace model directory containing its model
and tokenizer configuration. This adapter generates rollouts sequentially; use
the vLLM provider for batched high-throughput evaluation.

## Optional: OpenAI-compatible backend

Only the `openai` Python package is required for the client backend:

```bash
python3 -m pip install openai
export OPENAI_API_KEY='...'
```

Pass an explicitly configured `Chatbot.chat` function to
`LLMRolloutProvider`; `base_url` may point to OpenAI or any compatible server:

```python
from pathlib import Path

from rl_pipeline.inference import InferenceFramework, LLMRolloutProvider
from src.config import LLMConfig
from src.llm import Chatbot

source = Path("src/input/linear/34.c").read_text()
config = LLMConfig(
    use_local=False,
    api_model="your-model-name",
    base_url="https://your-endpoint.example/v1",
    api_temperature=1.0,
    api_top_p=1.0,
    api_max_tokens=2048,
)
provider = LLMRolloutProvider(chat_fn=Chatbot(config).chat)
result = InferenceFramework(source, rollout_provider=provider).run()
print(result.final_invariants, result.verified)
```

`LLMRolloutProvider` also accepts any custom `chat_fn: str -> str`, so an
existing trainer or serving client can be connected without using `src/llm.py`.
The provider formats `prompt/generate_prompt.txt` and
`prompt/refine_prompt.txt`; the bundled chat backends load
`prompt/system_prompt.txt` as the system message.

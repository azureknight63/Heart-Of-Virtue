# Heart-Of-Virtue
Adventure RPG
Follow former crusader Jean Claire into a strange and dangerous world as he tries to make sense of his situation and piece together the fragments of his tragic past.

This is a text RPG - all graphics are represented using text characters! The human mind is far better at producing images than any pixel editor.

If you like this project and are interested in contributing, please drop me a message.

## Requirements
- Python 3.13 (see .python-version)
- See requirements.txt for dependencies

## Optional AI Integration (Mynx LLM Adapter)
The in-game creature "mynx" can optionally be driven by an LLM for richer ambient behavior. Two provider modes are supported:

1. Local [Ollama](https://ollama.com/) model (default)
2. Remote [OpenRouter](https://openrouter.ai/) API (e.g. Grok 4 Fast:Free)

By default the adapter is disabled and the game uses deterministic stub responses.

### Enabling the Adapter
Set environment variables before launching the game (or in a local `.env` that your shell loads):

#### Common
```
MYNX_LLM_ENABLED=1                 # Enable LLM integration
MYNX_LLM_PROVIDER=ollama|openrouter
MYNX_LLM_MODEL=<model_id>          # Optional; provider-specific default chosen if omitted
MYNX_LLM_DEBUG=1                   # (Optional) Print detailed adapter availability + fallback reasons
```

#### Ollama (local)
```
MYNX_LLM_PROVIDER=ollama
MYNX_LLM_MODEL=llama3.1:7b         # Example (default if unset)
MYNX_LLM_URL=http://localhost:11434
```
Make sure the model is pulled in Ollama: `ollama pull llama3.1:7b`.

#### OpenRouter (remote API)
```
MYNX_LLM_PROVIDER=openrouter
MYNX_LLM_MODEL=x-ai/grok-4-fast:free   # Default if unset; you can switch to other models later
OPENROUTER_API_KEY=sk_or_...          # Required (keep secret!)
OPENROUTER_SITE=https://your-site.example (optional ranking metadata)
OPENROUTER_SITE_TITLE=Your Site Name   (optional ranking metadata)
```
The adapter only reports `available()` as True for OpenRouter when an API key is present; it does not proactively send a network probe (to keep tests fast and avoid unexpected calls). Calls to the API occur only when you request a mynx interaction in-game.

### Behavior Modes
The adapter offers two generation styles used internally:
- Plain text: concise present-tense nonverbal action description.
- Structured JSON: a small action object with keys: `action, intensity, description, duration_seconds, audible`.

The prompt-building logic strongly constrains output and post-parses/repairs minimal schema issues.

### Safety & Fallbacks
If the provider is unavailable (no API key, server down, etc.) the game gracefully falls back to stubbed deterministic descriptions. No crashes should occur.

### Quick Local Test (without running full game)
You can quickly instantiate the adapter in a Python shell:
```python
from ai.llm_client import MynxLLMAdapter
import os
os.environ["MYNX_LLM_ENABLED"] = "1"
os.environ["MYNX_LLM_PROVIDER"] = "openrouter"
os.environ["OPENROUTER_API_KEY"] = "sk_or_your_key"
adapter = MynxLLMAdapter()
print("Available?", adapter.available())
print(adapter.generate_plain("The mynx notices a dangling thread on the player's cloak."))
```
(If you omit the API key `available()` will be False and generation returns None.)

### Notes on Costs & Rate Limits
- The `x-ai/grok-4-fast:free` tier may impose rate limits and/or injection of a queue delay.
- Keep prompts succinct; the adapter already constrains output length and max tokens.

### Changing Models Later
For OpenRouter, just set `MYNX_LLM_MODEL` to any model ID they expose (e.g. `anthropic/claude-3.5-sonnet` if you have access). The rest of the adapter flow remains the same.

## Development
Run tests:
```
pytest -q
```
Generate a coverage report:
```
pytest --cov=src --cov=ai --cov-report=term-missing
```

## Contributing
1. Fork / create a feature branch
2. Add tests for new behavior
3. Keep changes focused and documented
4. Open a PR

### Troubleshooting Mynx LLM Integration
If the mynx keeps returning deterministic fallback responses:
1. Set `MYNX_LLM_DEBUG=1` and interact with the mynx again; watch console output.
2. Confirm `MYNX_LLM_ENABLED=1` and `MYNX_LLM_PROVIDER` are set.
3. For `openrouter` provider, ensure `OPENROUTER_API_KEY` is present and the `openai` Python package is installed (already declared in requirements.txt).
4. For `ollama`, ensure the Ollama daemon is running and the model is pulled (`ollama pull llama3.1:7b` or whichever model you set in `MYNX_LLM_MODEL`).
5. If using Ollama and you see a timeout message, verify the URL in `MYNX_LLM_URL` (default `http://localhost:11434`).
6. Structured generations failing? The adapter enforces a strict JSON action schema. Check that the model output is valid JSON without code fences.
7. To quickly inspect adapter state in a Python shell:
```python
from ai.llm_client import MynxLLMAdapter
import os
os.environ['MYNX_LLM_ENABLED'] = '1'
os.environ['MYNX_LLM_PROVIDER'] = 'openrouter'  # or 'ollama'
os.environ['OPENROUTER_API_KEY'] = 'sk_or_your_key'  # if using openrouter
adapter = MynxLLMAdapter()
print(adapter.debug_status())
```
If `available` is False, the `reason` field will indicate the issue (missing key, connection error, etc.).

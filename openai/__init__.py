"""Lightweight stub of the openai package for test environments where the real
OpenAI Python SDK is not installed. The test suite monkeypatches OpenAI to a
custom factory; this stub simply provides a compatible surface so the import
succeeds. If the real package is installed, Python's module resolution should
prefer that version depending on sys.path ordering.

This stub avoids any network calls. If used without monkeypatching, it returns
an empty completion object with a blank content string so callers gracefully
fall back.
"""
from __future__ import annotations
import types

class _StubMessage:
    def __init__(self, content: str):
        self.content = content

class _StubChoice:
    def __init__(self, content: str):
        self.message = _StubMessage(content)

class _StubCompletions:
    def create(self, *args, **kwargs):  # mimic signature flexibility
        # Return a structure similar enough for adapter parsing
        return types.SimpleNamespace(choices=[_StubChoice("")])

class _StubChat:
    def __init__(self):
        self.completions = _StubCompletions()

class OpenAI:  # noqa: D401 - simple stub
    _is_stub = True
    def __init__(self, *args, **kwargs):
        # If user is trying to use openrouter provider, surface a gentle warning once.
        import os
        if os.getenv("MYNX_LLM_PROVIDER", "").lower() == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
            if not os.getenv("HEART_OF_VIRTUE_SUPPRESS_OPENAI_STUB_WARNING"):
                print("[openai-stub] Real 'openai' package not installed; Mynx LLM OpenRouter calls will noop.")
        self.chat = _StubChat()

__all__ = ["OpenAI"]

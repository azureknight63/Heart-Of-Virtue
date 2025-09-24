import os
import types
from ai.llm_client import MynxLLMAdapter


class _DummyMessage:
    def __init__(self, content: str):
        self.content = content


class _DummyChoice:
    def __init__(self, content: str):
        self.message = _DummyMessage(content)


class _DummyCompletion:
    def __init__(self, content: str):
        self.choices = [_DummyChoice(content)]


class _DummyChatCompletions:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def create(self, **kwargs):  # mimic OpenAI SDK signature flexibility
        return _DummyCompletion(self._response_text)


class _DummyChat:
    def __init__(self, response_text: str):
        self.completions = _DummyChatCompletions(response_text)


class _DummyOpenAI:
    def __init__(self, base_url: str, api_key: str):  # noqa: D401
        self._base_url = base_url
        self._api_key = api_key
        # Default plain response; tests will patch attribute for structured case
        self._response_text = "The mynx tilts its head, whiskers twitching."
        self.chat = _DummyChat(self._response_text)


def test_openrouter_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
    adapter = MynxLLMAdapter()
    assert adapter.available() is False, "Adapter should be unavailable without API key"
    assert adapter.generate_plain("context") is None


def test_openrouter_plain_generation(monkeypatch):
    # Provide fake key to mark available
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-dummy")
    monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")

    # Monkeypatch openai.OpenAI to our dummy class
    import openai  # type: ignore
    dummy_instance = _DummyOpenAI(base_url="", api_key="")

    def _factory(**kwargs):  # mimic call signature used in adapter
        return dummy_instance

    monkeypatch.setattr(openai, "OpenAI", _factory)

    adapter = MynxLLMAdapter()
    assert adapter.available() is True
    out = adapter.generate_plain("The player wiggles a ribbon.")
    assert out is not None
    assert "mynx" in out.lower()


def test_openrouter_structured_generation(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-dummy")
    monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")

    # Structured JSON response (valid schema)
    structured_json = (
        '{"action":"investigate_object","intensity":"low","description":"The mynx sniffs the offered herb.",'
        '"duration_seconds":2,"audible":"soft chitter"}'
    )

    import openai  # type: ignore

    class _FactoryOpenAI(_DummyOpenAI):
        def __init__(self, base_url: str, api_key: str):
            super().__init__(base_url, api_key)
            self._response_text = structured_json
            self.chat = _DummyChat(self._response_text)

    def _factory(**kwargs):
        return _FactoryOpenAI(kwargs.get("base_url", ""), kwargs.get("api_key", ""))

    monkeypatch.setattr(openai, "OpenAI", _factory)

    adapter = MynxLLMAdapter()
    assert adapter.available() is True
    obj = adapter.generate_structured("The player holds out a strange herb.")
    assert isinstance(obj, dict)
    assert obj.get("action") == "investigate_object"
    assert obj.get("description")
    assert obj.get("duration_seconds") == 2


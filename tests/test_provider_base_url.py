import json

from agi_prototype import providers
from agi_prototype.providers import MockProvider, OpenAIProvider, configured_provider


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def read(self): return json.dumps(self.payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False


def test_default_base_url_is_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    assert OpenAIProvider(api_key="test").base_url == "https://api.openai.com/v1"


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1/")
    assert OpenAIProvider(api_key="test").base_url == "https://openrouter.ai/api/v1"


def test_request_goes_to_configured_base_url(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"], seen["body"] = req.full_url, json.loads(req.data)
        return FakeResponse({"choices": [{"message": {"content": '{"topic": "sql"}'}}]})

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_urlopen)
    p = OpenAIProvider(api_key="test", model="openai/gpt-4o-mini", base_url="http://localhost:11434/v1")
    assert p.learn("sql") == {"topic": "sql"}
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["body"]["model"] == "openai/gpt-4o-mini"


def test_no_key_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(configured_provider(), MockProvider)

from copilot import providers


def test_local_providers_use_openai_compatible_endpoints_without_keys():
    expected = {
        "ollama": "http://localhost:11434/v1",
        "lm-studio": "http://localhost:1234/v1",
    }

    for provider_id, base_url in expected.items():
        service = providers.provider(provider_id)
        assert service.base_url == base_url
        assert service.key_required is False
        assert providers.api_key(provider_id) == (None, "")


def test_local_provider_model_listing_uses_placeholder_key(monkeypatch):
    calls = {}

    class Models:
        def list(self):
            return [type("Model", (), {"id": "llama3.2"})()]

    class Client:
        def __init__(self, **kwargs):
            calls.update(kwargs)
            self.models = Models()

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: Client(**kwargs))

    assert providers.list_models("ollama") == ["llama3.2"]
    assert calls["api_key"] == "local"
    assert calls["base_url"] == "http://localhost:11434/v1"


def test_local_provider_suggestions_do_not_fetch_remote_recommendations(monkeypatch):
    def unexpected_network_call():
        raise AssertionError("local provider suggestions must work offline")

    monkeypatch.setattr(providers, "recommended", unexpected_network_call)
    assert providers.suggest("ollama", ["llama3.2"]) == "llama3.2"

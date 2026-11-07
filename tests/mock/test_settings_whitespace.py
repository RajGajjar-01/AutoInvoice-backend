from app.core.config import Settings


def test_env_values_are_stripped(monkeypatch):
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", " https://x.example/cb ")
    assert Settings().GOOGLE_REDIRECT_URI == "https://x.example/cb"

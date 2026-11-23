from gemini_pro_mcp.config import Settings


def test_invalid_numbers_fall_back_to_defaults(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_PRO_AGY_TIMEOUT", "10m")
    monkeypatch.setenv("GEMINI_PRO_FLOW_PORT", "")

    settings = Settings.from_env()

    assert settings.agy_timeout == 600
    assert settings.flow_cdp_port == 9333
    assert "GEMINI_PRO_AGY_TIMEOUT='10m' is not a whole number" in capsys.readouterr().err


def test_valid_numbers_are_used(monkeypatch):
    monkeypatch.setenv("GEMINI_PRO_AGY_TIMEOUT", " 120 ")
    monkeypatch.setenv("GEMINI_PRO_FLOW_PORT", "9444")

    settings = Settings.from_env()

    assert settings.agy_timeout == 120
    assert settings.flow_cdp_port == 9444

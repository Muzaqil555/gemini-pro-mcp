import os

import pytest

from gemini_pro_mcp.config import load_env_file, parse_env_line, set_env_values


@pytest.mark.parametrize(
    "line, expected",
    [
        ("GEMINI_API_KEY=abc123", ("GEMINI_API_KEY", "abc123")),
        ("  GEMINI_API_KEY = abc123  ", ("GEMINI_API_KEY", "abc123")),
        ("export GEMINI_API_KEY=abc123", ("GEMINI_API_KEY", "abc123")),
        ('GEMINI_API_KEY="abc123"', ("GEMINI_API_KEY", "abc123")),
        ("GEMINI_API_KEY='abc123'", ("GEMINI_API_KEY", "abc123")),
        ("GEMINI_API_KEY=abc123  # from AI Studio", ("GEMINI_API_KEY", "abc123")),
        ('NOTE="keep # this"', ("NOTE", "keep # this")),
        ('KEY="a # b" # note', ("KEY", "a # b")),
        ("KEY=abc\t# note", ("KEY", "abc")),
        ("PASSWORD=ends-with-quote'", ("PASSWORD", "ends-with-quote'")),
        ("URL=https://example.com/a#frag", ("URL", "https://example.com/a#frag")),
        ("EMPTY=", ("EMPTY", "")),
        ("", None),
        ("# a comment", None),
        ("no equals sign", None),
        ("=value", None),
    ],
)
def test_parse_env_line(line, expected):
    assert parse_env_line(line) == expected


def test_load_env_file_handles_bom_and_keeps_existing_values(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GPM_TEST_KEY=from-file\nGPM_TEST_SET=from-file\n", encoding="utf-8-sig")
    monkeypatch.delenv("GPM_TEST_KEY", raising=False)
    monkeypatch.setenv("GPM_TEST_SET", "from-env")

    load_env_file(env)

    assert os.environ["GPM_TEST_KEY"] == "from-file"
    assert os.environ["GPM_TEST_SET"] == "from-env"


def test_set_env_values_preserves_comments_and_other_keys(tmp_path):
    env = tmp_path / "nested" / ".env"
    env.parent.mkdir(parents=True)
    env.write_text("# My keys\nOTHER=keep\nGEMINI_API_KEY=old\n", encoding="utf-8")

    saved = set_env_values({"GEMINI_API_KEY": "new-key", "JULES_API_KEY": "a # b"}, env)

    assert saved == env
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "# My keys",
        "OTHER=keep",
        "GEMINI_API_KEY=new-key",
        'JULES_API_KEY="a # b"',
    ]
    assert parse_env_line(lines[3]) == ("JULES_API_KEY", "a # b")

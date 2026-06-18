import os

from src.legal_case_rag.runtime.env import load_env_file


def test_load_env_file_sets_missing_values_and_keeps_existing(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "A=one\n"
        "B='two words'\n"
        'C="three # not comment"\n'
        "D=four # comment\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("B", "kept")

    values = load_env_file(env_path)

    assert values == {
        "A": "one",
        "B": "two words",
        "C": "three # not comment",
        "D": "four",
    }
    assert os.environ["A"] == "one"
    assert os.environ["B"] == "kept"
    assert os.environ["C"] == "three # not comment"
    assert os.environ["D"] == "four"

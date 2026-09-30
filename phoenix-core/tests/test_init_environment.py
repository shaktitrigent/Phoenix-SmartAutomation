"""Regression coverage for environment loading in newly initialized projects."""

import json
import os
from pathlib import Path
import subprocess
import sys

from click.testing import CliRunner
import pytest

from phoenix.cli.main import main
from phoenix import scaffold


@pytest.mark.parametrize("bdd", [False, True])
@pytest.mark.parametrize("environment", ["local", "shell", "defaults"])
def test_init_loads_project_environment(tmp_path, monkeypatch, bdd, environment):
    # Keep initialization's real registry writes inside the temporary directory.
    monkeypatch.setattr(scaffold, "_registry_path", lambda: tmp_path / "projects.json")
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "generated-project"
    args = [
        "init", "generated-project", "--non-interactive", "--dir", str(project),
        "--base-url", "https://default.example", "--browser", "chromium",
    ]
    if bdd:
        args.append("--bdd")
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    conftest = project / "conftest.py"
    source = conftest.read_text(encoding="utf-8")
    assert "PROJECT_ROOT = Path(__file__).resolve().parent" in source
    assert 'load_dotenv(PROJECT_ROOT / ".env.local", override=True)' in source
    assert not (project / ".env.local").exists()
    assert ".env.local" in (project / ".gitignore").read_text().splitlines()

    values = {
        "APP_URL": "https://project.example",
        "TEST_USERNAME": "test-user",
        "TEST_PASSWORD": "test-password",
        "PHOENIX_BROWSER": "firefox",
        "PHOENIX_LOG_LEVEL": "DEBUG",
        "ANTHROPIC_API_KEY": "test-api-key",
        "CUSTOM_PROJECT_SETTING": "custom-value",
    }
    child_env = os.environ.copy()
    child_env.pop("PYTHON_DOTENV_DISABLED", None)
    for key in values:
        child_env.pop(key, None)
    expected = {}
    if environment != "defaults":
        expected = {key: "shell-placeholder" for key in values}
        child_env.update(expected)
    if environment == "local":
        (project / ".env.local").write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
        )
        expected = values

    # A conflicting file in the terminal directory must never be loaded.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".env.local").write_text("APP_URL=https://wrong.example\n", encoding="utf-8")
    script = """
import json
import os
from pathlib import Path
import runpy
import sys

project = Path(sys.argv[1])
expected = json.loads(sys.argv[2])
sys.path.insert(0, str(project))
config = runpy.run_path(str(project / "conftest.py"))
assert config["PROJECT_ROOT"] == project
assert config["BASE_URL"] == expected.get("APP_URL", "https://default.example")
assert config["DEFAULT_BROWSER"] == expected.get("PHOENIX_BROWSER", "chromium")
for key, value in expected.items():
    assert os.environ[key] == value, key
# This module reads APP_URL at import time, so it must see the loaded value too.
import fixtures.auth
assert fixtures.auth._BASE_URL == config["BASE_URL"]
"""
    loaded = subprocess.run(
        [sys.executable, "-c", script, str(project), json.dumps(expected)],
        cwd=elsewhere, env=child_env, capture_output=True, text=True, timeout=60,
    )
    assert loaded.returncode == 0, loaded.stdout + loaded.stderr


def test_dotenv_is_a_core_runtime_dependency():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    core = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((core / "pyproject.toml").read_text(encoding="utf-8"))
    assert "python-dotenv>=1.0.0" in metadata["project"]["dependencies"]
    assert "python-dotenv>=1.0.0" in (core / "requirements.txt").read_text().splitlines()

"""V1.0 packaging and tool-registry contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path

import src.main as main_module
from src.agent import REGISTERED_TOOLS, SIMPLE_TOOL_HANDLER_NAMES
from src.config import resolve_application_root


ROOT = Path(__file__).resolve().parents[1]


def test_registered_tools_are_unique_and_stable() -> None:
    names = [tool["name"] for tool in REGISTERED_TOOLS]

    assert len(names) == 28
    assert len(set(names)) == 28
    assert set(SIMPLE_TOOL_HANDLER_NAMES).issubset(names)


def test_pyproject_exposes_installable_cli() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["project"]["requires-python"] == ">=3.11"
    assert config["project"]["scripts"]["hragent"] == "src.main:main"


def test_main_loads_environment_before_running(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "load_local_environment",
        lambda: calls.append("load_environment"),
    )
    monkeypatch.setattr(main_module, "run", lambda: calls.append("run") or 0)

    assert main_module.main() == 0
    assert calls == ["load_environment", "run"]


def test_runtime_root_prefers_explicit_configuration(monkeypatch, tmp_path) -> None:
    configured = tmp_path / "configured"
    monkeypatch.setenv("HR_AGENT_HOME", str(configured))

    assert resolve_application_root(cwd=tmp_path, home=tmp_path) == configured


def test_runtime_root_uses_private_home_outside_source_project(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("HR_AGENT_HOME", raising=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    installed_source = tmp_path / "site-packages"
    installed_source.mkdir()

    assert resolve_application_root(
        cwd=outside,
        source_root=installed_source,
        home=tmp_path,
    ) == tmp_path / ".hragent"

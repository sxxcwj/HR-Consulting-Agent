"""Resolve one stable runtime root for source and installed CLI execution."""

from __future__ import annotations

import os
from pathlib import Path


def _is_project_root(path: Path) -> bool:
    return (path / "PRODUCT_SPEC.md").is_file() and (path / "src").is_dir()


def resolve_application_root(
    *, cwd: Path | None = None, source_root: Path | None = None, home: Path | None = None
) -> Path:
    """Resolve runtime data root without writing into an installed package."""
    configured = os.getenv("HR_AGENT_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    working_directory = (cwd or Path.cwd()).resolve()
    if _is_project_root(working_directory):
        return working_directory

    package_source = (source_root or Path(__file__).resolve().parents[1]).resolve()
    if _is_project_root(package_source):
        return package_source

    return (home or Path.home()).expanduser().resolve() / ".hragent"


APPLICATION_ROOT = resolve_application_root()

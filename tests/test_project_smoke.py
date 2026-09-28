"""Minimal checks for the Python project layout."""

import sys

import src


def test_python_version() -> None:
    assert sys.version_info >= (3, 11)


def test_package_imports() -> None:
    assert src.__doc__ is not None

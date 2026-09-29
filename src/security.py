"""Shared privacy, credential detection, and private-file helpers."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any


SENSITIVE_PATTERNS = (
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证号已脱敏]"),
    (
        "手机号",
        re.compile(r"(?<![A-Za-z0-9])1[3-9]\d{9}(?![A-Za-z0-9])"),
        "[手机号已脱敏]",
    ),
    (
        "邮箱",
        re.compile(r"(?<![\w.])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.])"),
        "[邮箱已脱敏]",
    ),
    (
        "姓名",
        re.compile(r"(?P<label>(?:员工)?姓名\s*[：:])\s*[\u4e00-\u9fff·]{2,12}"),
        r"\g<label>[姓名已脱敏]",
    ),
    (
        "地址",
        re.compile(r"(?P<label>(?:家庭|居住|联系)?地址\s*[：:])[^\n，,；;]{4,100}"),
        r"\g<label>[地址已脱敏]",
    ),
    (
        "高度敏感记录",
        re.compile(r"(?P<label>(?:医疗信息|个人薪酬|处分记录|投诉记录)\s*[：:])[^\n]{1,300}"),
        r"\g<label>[敏感内容已脱敏]",
    ),
)
CREDENTIAL_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        r"(?:api[ _-]?key|access[ _-]?token|password|密码|密钥|令牌)"
        r"\s*[:=：]\s*[^\s,，;；]{6,}",
        re.IGNORECASE,
    ),
)


def redact_sensitive_text(text: str) -> tuple[str, list[str]]:
    """Mask supported personal identifiers and return detected labels."""
    detected: list[str] = []
    result = text
    for label, pattern, replacement in SENSITIVE_PATTERNS:
        result, count = pattern.subn(replacement, result)
        if count:
            detected.append(label)
    return result, detected


def detect_sensitive_labels(value: Any, *, include_credentials: bool = True) -> list[str]:
    """Recursively detect personal identifiers and optional credentials."""
    labels: list[str] = []
    if isinstance(value, str):
        _, detected = redact_sensitive_text(value)
        labels.extend(detected)
        if include_credentials and any(pattern.search(value) for pattern in CREDENTIAL_PATTERNS):
            labels.append("密钥或凭据")
    elif isinstance(value, list):
        for item in value:
            labels.extend(detect_sensitive_labels(item, include_credentials=include_credentials))
    elif isinstance(value, dict):
        for item in value.values():
            labels.extend(detect_sensitive_labels(item, include_credentials=include_credentials))
    return sorted(set(labels))


def ensure_private_directory(path: str | Path) -> Path:
    """Create a directory and restrict it to the current user on POSIX."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        target.chmod(0o700)
    return target


def ensure_private_file(path: str | Path) -> Path:
    """Restrict an existing file to the current user on POSIX."""
    target = Path(path)
    if target.exists() and os.name == "posix":
        target.chmod(0o600)
    return target


def atomic_write_text(path: str | Path, content: str) -> None:
    """Atomically replace a UTF-8 text file using a private temporary file."""
    target = Path(path)
    ensure_private_directory(target.parent)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(target)
        ensure_private_file(target)
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise

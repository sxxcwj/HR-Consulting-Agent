"""Tests for shared privacy and private-file helpers."""

from __future__ import annotations

import os
import stat

from src.security import atomic_write_text, detect_sensitive_labels, redact_sensitive_text


def test_redact_sensitive_text_masks_supported_identifiers() -> None:
    text = "姓名：张三，手机号：13812345678，邮箱：zhangsan@example.com"

    redacted, labels = redact_sensitive_text(text)

    assert "张三" not in redacted
    assert "13812345678" not in redacted
    assert "zhangsan@example.com" not in redacted
    assert labels == ["手机号", "邮箱", "姓名"]


def test_detect_sensitive_labels_recurses_and_detects_credentials() -> None:
    value = {"items": ["联系邮箱 hr@example.com", {"secret": "api_key=abcdef123456"}]}

    assert detect_sensitive_labels(value) == ["密钥或凭据", "邮箱"]


def test_phone_detector_ignores_digits_embedded_in_internal_ids() -> None:
    assert detect_sensitive_labels("memory_id：MEM-15134033911F") == []
    assert detect_sensitive_labels("员工手机号：15134033911") == ["手机号"]


def test_atomic_write_text_is_private_and_leaves_no_temp_files(tmp_path) -> None:
    target = tmp_path / "private" / "state.json"

    atomic_write_text(target, '{"version": 1}')
    atomic_write_text(target, '{"version": 2}')

    assert target.read_text(encoding="utf-8") == '{"version": 2}'
    assert not list(target.parent.glob(".state.json.*.tmp"))
    if os.name == "posix":
        assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

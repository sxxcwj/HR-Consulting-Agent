"""Small fakes for deterministic tests."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest


VALID_ANALYSIS = """# 问题判断

这是需要进一步诊断的组织与 HR 问题，目前只有用户描述的现象。

# 可能原因

可能与目标设置有关，尚需核验。

# 需要补充的信息

请提供目标和实际结果，以便区分原因。

# 建议措施

请先核对目标记录，形成事实清单。

# 下一步行动

1. 由 HR 负责人核对目标记录，形成核对表。
"""


class FakeResponses:
    def __init__(self, outputs: Sequence[str | Exception | SimpleNamespace]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if not self.outputs:
            raise AssertionError("unexpected API call")
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        if isinstance(output, str):
            return SimpleNamespace(output_text=output)
        return output


class FakeClient:
    def __init__(self, outputs: Sequence[str | Exception | SimpleNamespace]) -> None:
        self.responses = FakeResponses(outputs)


@pytest.fixture
def valid_analysis() -> str:
    return VALID_ANALYSIS

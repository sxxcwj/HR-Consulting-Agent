"""Data model and validation for explicit V0.8 long-term memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MEMORY_CATEGORIES = (
    "preference",
    "organization",
    "terminology",
    "standing_instruction",
)
MEMORY_STATUSES = ("active", "archived")
MEMORY_SOURCE = "user_explicit"


class MemoryValidationError(ValueError):
    """A memory value violates the V0.8 contract."""


def validate_text(
    value: Any,
    field_name: str,
    *,
    required: bool = False,
    maximum: int = 2000,
) -> str:
    if not isinstance(value, str):
        raise MemoryValidationError(f"{field_name} 必须是字符串。")
    normalized = value.strip()
    if required and not normalized:
        raise MemoryValidationError(f"{field_name} 不能为空。")
    if len(normalized) > maximum:
        raise MemoryValidationError(f"{field_name} 不能超过 {maximum} 个字符。")
    return normalized


def validate_category(value: Any) -> str:
    if value not in MEMORY_CATEGORIES:
        raise MemoryValidationError(
            f"category 必须是：{', '.join(MEMORY_CATEGORIES)}。"
        )
    return value


@dataclass(frozen=True)
class MemoryEntry:
    memory_id: str
    category: str
    content: str
    status: str
    source: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryEntry":
        try:
            memory_id = validate_text(value["memory_id"], "memory_id", required=True)
            category = validate_category(value["category"])
            content = validate_text(value["content"], "content", required=True)
            status = value["status"]
            if status not in MEMORY_STATUSES:
                raise MemoryValidationError("status 必须是 active 或 archived。")
            source = value["source"]
            if source != MEMORY_SOURCE:
                raise MemoryValidationError("source 必须是 user_explicit。")
            return cls(
                memory_id=memory_id,
                category=category,
                content=content,
                status=status,
                source=source,
                created_at=validate_text(
                    value["created_at"], "created_at", required=True
                ),
                updated_at=validate_text(
                    value["updated_at"], "updated_at", required=True
                ),
            )
        except KeyError as exc:
            raise MemoryValidationError(f"Memory 缺少字段：{exc.args[0]}。") from exc

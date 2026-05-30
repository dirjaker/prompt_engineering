"""
数据模型 - Prompt、版本、变量、评估结果
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 枚举 ────────────────────────────────────────────────────────────────
class VariableType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class EvalMetric(str, Enum):
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    FORMAT = "format"
    FLUENCY = "fluency"
    COMPLETENESS = "completeness"


class ABTestStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ── 变量定义 ──────────────────────────────────────────────────────────────
class VariableDefinition(BaseModel):
    name: str = Field(..., description="变量名")
    var_type: VariableType = Field(VariableType.STRING, description="变量类型")
    description: str = Field("", description="变量描述")
    default: Any = Field(None, description="默认值")
    required: bool = Field(True, description="是否必填")
    enum_values: Optional[list[Any]] = Field(None, description="枚举可选值")

    def validate_value(self, value: Any) -> Any:
        """类型验证与转换"""
        if value is None:
            if self.required and self.default is None:
                raise ValueError(f"变量 '{self.name}' 是必填项")
            return self.default

        if self.enum_values and value not in self.enum_values:
            raise ValueError(
                f"变量 '{self.name}' 的值必须是 {self.enum_values} 之一"
            )

        converters = {
            VariableType.STRING: str,
            VariableType.INTEGER: int,
            VariableType.FLOAT: float,
            VariableType.BOOLEAN: lambda v: v
            if isinstance(v, bool)
            else str(v).lower() in ("true", "1", "yes"),
            VariableType.LIST: lambda v: v if isinstance(v, list) else list(v),
            VariableType.DICT: lambda v: v if isinstance(v, dict) else dict(v),
        }

        try:
            return converters[self.var_type](value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"变量 '{self.name}' 期望类型 {self.var_type.value}, "
                f"实际值: {value!r}"
            ) from exc


# ── Prompt 版本 ──────────────────────────────────────────────────────────
class PromptVersion(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt_id: str
    version: int
    template: str
    variables: list[VariableDefinition] = Field(default_factory=list)
    system_prompt: str = ""
    model_hint: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    change_note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Prompt ───────────────────────────────────────────────────────────────
class Prompt(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    status: PromptStatus = PromptStatus.DRAFT
    current_version: int = 1
    versions: list[PromptVersion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def latest_version(self) -> Optional[PromptVersion]:
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version)

    @property
    def active_template(self) -> str:
        v = self.latest_version
        return v.template if v else ""


# ── 评估结果 ──────────────────────────────────────────────────────────────
class EvalResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt_id: str
    version: int
    metric: EvalMetric
    score: float = Field(..., ge=0.0, le=1.0)
    details: str = ""
    input_sample: str = ""
    output_sample: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── A/B 测试 ─────────────────────────────────────────────────────────────
class ABTestVariant(BaseModel):
    prompt_id: str
    version: int
    weight: float = Field(1.0, ge=0, description="流量权重")


class ABTest(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    status: ABTestStatus = ABTestStatus.DRAFT
    variants: list[ABTestVariant] = Field(default_factory=list)
    sample_size: int = Field(100, ge=1, description="每组样本量")
    results: list[dict[str, Any]] = Field(default_factory=list)
    winner_variant_idx: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── 通用响应 ──────────────────────────────────────────────────────────────
class RenderRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class EvalRequest(BaseModel):
    metrics: list[EvalMetric] = Field(
        default_factory=lambda: list(EvalMetric)
    )
    samples: list[dict[str, Any]] = Field(default_factory=list)

"""
模板引擎 - Jinja2 风格的变量注入、条件渲染、循环、过滤器
"""
from __future__ import annotations

import re
import json
from typing import Any

from jinja2 import (
    Environment,
    BaseLoader,
    TemplateSyntaxError,
    UndefinedError,
    Undefined,
)
from jinja2.sandbox import SandboxedEnvironment

from models import VariableDefinition, VariableType


# ── 自定义过滤器 ─────────────────────────────────────────────────────────
def _filter_upper(value: str) -> str:
    return str(value).upper()


def _filter_lower(value: str) -> str:
    return str(value).lower()


def _filter_title(value: str) -> str:
    return str(value).title()


def _filter_truncate(value: str, length: int = 50, end: str = "...") -> str:
    s = str(value)
    return s[:length] + end if len(s) > length else s


def _filter_json(value: Any, indent: int = 2) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent)


def _filter_join(value: list, sep: str = ", ") -> str:
    return sep.join(str(i) for i in value)


def _filter_default(value: Any, default_value: str = "") -> str:
    return default_value if isinstance(value, Undefined) or value is None else str(value)


def _filter_word_count(value: str) -> int:
    return len(str(value).split())


def _filter_strip(value: str) -> str:
    return str(value).strip()


# ── 模板引擎 ──────────────────────────────────────────────────────────────
class TemplateEngine:
    """企业级模板引擎，支持变量注入、条件渲染、循环、过滤器"""

    def __init__(self):
        self.env = SandboxedEnvironment(
            loader=BaseLoader(),
            undefined=_StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_filters()

    def _register_filters(self):
        self.env.filters.update({
            "upper": _filter_upper,
            "lower": _filter_lower,
            "title": _filter_title,
            "truncate": _filter_truncate,
            "to_json": _filter_json,
            "join": _filter_join,
            "default": _filter_default,
            "word_count": _filter_word_count,
            "strip": _filter_strip,
        })

    def extract_variables(self, template: str) -> list[str]:
        """从模板中提取所有变量名"""
        ast = self.env.parse(template)
        from jinja2.meta import find_undeclared_variables
        return sorted(find_undeclared_variables(ast))

    def validate_template(self, template: str) -> tuple[bool, str]:
        """验证模板语法"""
        try:
            self.env.parse(template)
            return True, "模板语法正确"
        except TemplateSyntaxError as exc:
            return False, f"模板语法错误: {exc}"

    def validate_variables(
        self,
        template: str,
        var_defs: list[VariableDefinition],
        provided: dict[str, Any],
    ) -> tuple[bool, list[str], dict[str, Any]]:
        """
        验证并转换变量值
        返回: (是否通过, 错误列表, 转换后的变量字典)
        """
        errors: list[str] = []
        var_map = {v.name: v for v in var_defs}
        template_vars = set(self.extract_variables(template))
        resolved: dict[str, Any] = {}

        for var_name in template_vars:
            if var_name in var_map:
                vdef = var_map[var_name]
                raw = provided.get(var_name, vdef.default)
                try:
                    resolved[var_name] = vdef.validate_value(raw)
                except ValueError as exc:
                    errors.append(str(exc))
            else:
                # 模板变量没有显式定义 → 直接使用提供的值
                if var_name in provided:
                    resolved[var_name] = provided[var_name]
                else:
                    errors.append(f"变量 '{var_name}' 未定义且未提供值")

        # 检查多余变量 (警告, 不阻断)
        return len(errors) == 0, errors, resolved

    def render(
        self,
        template: str,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """渲染模板"""
        variables = variables or {}
        try:
            tmpl = self.env.from_string(template)
            return tmpl.render(**variables)
        except UndefinedError as exc:
            raise TemplateRenderError(f"渲染失败: 变量未定义 - {exc}") from exc
        except TemplateSyntaxError as exc:
            raise TemplateRenderError(f"渲染失败: 语法错误 - {exc}") from exc

    def render_with_validation(
        self,
        template: str,
        var_defs: list[VariableDefinition],
        variables: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """验证 + 渲染, 一步完成"""
        ok, errors, resolved = self.validate_variables(template, var_defs, variables)
        if not ok:
            return "", errors
        try:
            result = self.render(template, resolved)
            return result, []
        except TemplateRenderError as exc:
            return "", [str(exc)]

    def preview(self, template: str, var_defs: list[VariableDefinition]) -> str:
        """用默认值预览模板"""
        defaults = {}
        for v in var_defs:
            placeholder = f"<{v.name}>"
            defaults[v.name] = v.default if v.default is not None else placeholder
        return self.render(template, defaults)


class TemplateRenderError(Exception):
    pass


class _StrictUndefined(Undefined):
    """严格未定义变量 - 访问时立即报错"""
    def __str__(self):
        raise UndefinedError(f"变量 '{self._undefined_name}' 未定义")

    def __iter__(self):
        raise UndefinedError(f"变量 '{self._undefined_name}' 未定义")

    def __bool__(self):
        raise UndefinedError(f"变量 '{self._undefined_name}' 未定义")

"""
FastAPI 服务 + 内嵌 Web UI
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from database import Database
from evaluator import Evaluator
from models import (
    ABTest,
    ABTestStatus,
    ABTestVariant,
    EvalMetric,
    EvalRequest,
    EvalResult,
    Prompt,
    PromptStatus,
    PromptVersion,
    RenderRequest,
    VariableDefinition,
)
from template_engine import TemplateEngine, TemplateRenderError

# ── 加载配置 ──────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

db: Database
engine: TemplateEngine
evaluator: Evaluator


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, engine, evaluator
    db = Database(CONFIG["database"]["path"])
    engine = TemplateEngine()
    evaluator = Evaluator()
    yield
    db.close()


app = FastAPI(
    title=CONFIG["app"]["name"],
    version=CONFIG["app"]["version"],
    lifespan=lifespan,
)


# ── 请求模型 ──────────────────────────────────────────────────────────────
class PromptCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    tags: list[str] = []
    template: str = ""
    system_prompt: str = ""
    model_hint: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    variables: list[dict[str, Any]] = []
    change_note: str = "初始版本"


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None
    template: Optional[str] = None
    system_prompt: Optional[str] = None
    model_hint: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    variables: Optional[list[dict[str, Any]]] = None
    change_note: str = ""


class ABTestCreate(BaseModel):
    name: str
    description: str = ""
    variants: list[dict[str, Any]]
    sample_size: int = 100


# ── Prompt API ────────────────────────────────────────────────────────────
@app.post("/api/prompts", summary="创建 Prompt")
async def create_prompt(body: PromptCreate):
    prompt = Prompt(
        name=body.name,
        description=body.description,
        category=body.category,
        tags=body.tags,
    )
    var_defs = [VariableDefinition(**v) for v in body.variables]
    version = PromptVersion(
        prompt_id=prompt.id,
        version=1,
        template=body.template,
        variables=var_defs,
        system_prompt=body.system_prompt,
        model_hint=body.model_hint,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        change_note=body.change_note,
    )
    prompt.versions.append(version)
    db.save_prompt(prompt)
    return {"id": prompt.id, "message": "Prompt 创建成功", "version": 1}


@app.get("/api/prompts", summary="列出 Prompts")
async def list_prompts(
    category: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
):
    prompts = db.list_prompts(category=category, status=status, tag=tag, search=search)
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "tags": p.tags,
            "status": p.status.value,
            "current_version": p.current_version,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in prompts
    ]


@app.get("/api/prompts/{prompt_id}", summary="获取 Prompt 详情")
async def get_prompt(prompt_id: str):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")
    v = prompt.latest_version
    return {
        "id": prompt.id,
        "name": prompt.name,
        "description": prompt.description,
        "category": prompt.category,
        "tags": prompt.tags,
        "status": prompt.status.value,
        "current_version": prompt.current_version,
        "template": v.template if v else "",
        "system_prompt": v.system_prompt if v else "",
        "model_hint": v.model_hint if v else "",
        "temperature": v.temperature if v else 0.7,
        "max_tokens": v.max_tokens if v else 2048,
        "variables": [vi.model_dump() for vi in v.variables] if v else [],
        "versions": [
            {
                "version": ver.version,
                "change_note": ver.change_note,
                "created_at": ver.created_at.isoformat(),
            }
            for ver in prompt.versions
        ],
        "created_at": prompt.created_at.isoformat(),
        "updated_at": prompt.updated_at.isoformat(),
    }


@app.put("/api/prompts/{prompt_id}", summary="更新 Prompt (自动创建新版本)")
async def update_prompt(prompt_id: str, body: PromptUpdate):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")

    if body.name is not None:
        prompt.name = body.name
    if body.description is not None:
        prompt.description = body.description
    if body.category is not None:
        prompt.category = body.category
    if body.tags is not None:
        prompt.tags = body.tags
    if body.status is not None:
        prompt.status = PromptStatus(body.status)

    # 如果模板或变量变化，创建新版本
    latest = prompt.latest_version
    template_changed = body.template is not None and (not latest or body.template != latest.template)
    variables_changed = body.variables is not None

    if template_changed or variables_changed:
        new_ver_num = prompt.current_version + 1
        var_defs = (
            [VariableDefinition(**v) for v in body.variables]
            if body.variables
            else (latest.variables if latest else [])
        )
        new_version = PromptVersion(
            prompt_id=prompt_id,
            version=new_ver_num,
            template=body.template if body.template is not None else (latest.template if latest else ""),
            variables=var_defs,
            system_prompt=body.system_prompt if body.system_prompt is not None else (latest.system_prompt if latest else ""),
            model_hint=body.model_hint if body.model_hint is not None else (latest.model_hint if latest else ""),
            temperature=body.temperature if body.temperature is not None else (latest.temperature if latest else 0.7),
            max_tokens=body.max_tokens if body.max_tokens is not None else (latest.max_tokens if latest else 2048),
            change_note=body.change_note or f"版本 {new_ver_num}",
        )
        prompt.versions.append(new_version)
        prompt.current_version = new_ver_num

    prompt.updated_at = datetime.utcnow()
    db.save_prompt(prompt)
    return {"id": prompt_id, "message": "更新成功", "version": prompt.current_version}


@app.delete("/api/prompts/{prompt_id}", summary="删除 Prompt")
async def delete_prompt(prompt_id: str):
    if not db.delete_prompt(prompt_id):
        raise HTTPException(404, "Prompt 不存在")
    return {"message": "删除成功"}


# ── 版本管理 ──────────────────────────────────────────────────────────────
@app.get("/api/prompts/{prompt_id}/versions", summary="获取版本历史")
async def get_versions(prompt_id: str):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")
    return [
        {
            "version": v.version,
            "template": v.template,
            "variables": [vi.model_dump() for vi in v.variables],
            "change_note": v.change_note,
            "created_at": v.created_at.isoformat(),
        }
        for v in prompt.versions
    ]


@app.post("/api/prompts/{prompt_id}/rollback/{version}", summary="回滚到指定版本")
async def rollback_version(prompt_id: str, version: int):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")

    target = None
    for v in prompt.versions:
        if v.version == version:
            target = v
            break
    if not target:
        raise HTTPException(404, f"版本 {version} 不存在")

    new_ver_num = prompt.current_version + 1
    rollback_ver = PromptVersion(
        prompt_id=prompt_id,
        version=new_ver_num,
        template=target.template,
        variables=target.variables,
        system_prompt=target.system_prompt,
        model_hint=target.model_hint,
        temperature=target.temperature,
        max_tokens=target.max_tokens,
        change_note=f"回滚到版本 {version}",
    )
    prompt.versions.append(rollback_ver)
    prompt.current_version = new_ver_num
    prompt.updated_at = datetime.utcnow()
    db.save_prompt(prompt)
    return {"message": f"已回滚到版本 {version}，新版本号: {new_ver_num}"}


# ── 渲染 & 评估 ──────────────────────────────────────────────────────────
@app.post("/api/prompts/{prompt_id}/render", summary="渲染模板")
async def render_prompt(prompt_id: str, body: RenderRequest):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")
    v = prompt.latest_version
    if not v:
        raise HTTPException(400, "该 Prompt 没有版本")

    result, errors = engine.render_with_validation(v.template, v.variables, body.variables)
    if errors:
        return {"success": False, "errors": errors}

    # 模拟 LLM 输出
    from evaluator import _mock_llm_call
    output = _mock_llm_call(result, v.model_hint)

    return {
        "success": True,
        "rendered": result,
        "mock_output": output,
        "model_hint": v.model_hint,
    }


@app.post("/api/prompts/{prompt_id}/evaluate", summary="评估 Prompt")
async def evaluate_prompt(
    prompt_id: str,
    body: EvalRequest | None = None,
):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt 不存在")

    body = body or EvalRequest()
    metrics = [EvalMetric(m) for m in body.metrics] if body.metrics else list(EvalMetric)
    samples = body.samples if body.samples else [{}]

    results = evaluator.evaluate_prompt(prompt, metrics=metrics, samples=samples)
    for r in results:
        db.save_eval_result(r)

    avg_scores: dict[str, list[float]] = {}
    for r in results:
        avg_scores.setdefault(r.metric.value, []).append(r.score)

    return {
        "prompt_id": prompt_id,
        "version": prompt.current_version,
        "total_evaluations": len(results),
        "average_scores": {
            k: round(sum(v) / len(v), 4) for k, v in avg_scores.items()
        },
        "details": [
            {
                "metric": r.metric.value,
                "score": r.score,
                "details": r.details,
            }
            for r in results
        ],
    }


@app.get("/api/prompts/{prompt_id}/evaluations", summary="获取评估历史")
async def get_evaluations(
    prompt_id: str, version: Optional[int] = Query(None)
):
    results = db.get_eval_results(prompt_id, version=version)
    return [
        {
            "id": r.id,
            "version": r.version,
            "metric": r.metric.value,
            "score": r.score,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


# ── A/B 测试 ─────────────────────────────────────────────────────────────
@app.post("/api/ab-tests", summary="创建 A/B 测试")
async def create_ab_test(body: ABTestCreate):
    variants = [ABTestVariant(**v) for v in body.variants]
    test = ABTest(
        name=body.name,
        description=body.description,
        variants=variants,
        sample_size=body.sample_size,
    )
    db.save_ab_test(test)
    return {"id": test.id, "message": "A/B 测试创建成功"}


@app.post("/api/ab-tests/{test_id}/run", summary="运行 A/B 测试")
async def run_ab_test(test_id: str):
    test = db.get_ab_test(test_id)
    if not test:
        raise HTTPException(404, "A/B 测试不存在")

    prompts: dict[str, Prompt] = {}
    for v in test.variants:
        p = db.get_prompt(v.prompt_id)
        if p:
            prompts[v.prompt_id] = p

    test = evaluator.run_ab_test(test, prompts)
    db.save_ab_test(test)
    return {
        "id": test.id,
        "status": test.status.value,
        "winner_variant_idx": test.winner_variant_idx,
        "results": test.results,
    }


@app.get("/api/ab-tests", summary="列出 A/B 测试")
async def list_ab_tests():
    tests = db.list_ab_tests()
    return [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status.value,
            "variants_count": len(t.variants),
            "winner_variant_idx": t.winner_variant_idx,
            "created_at": t.created_at.isoformat(),
        }
        for t in tests
    ]


@app.get("/api/ab-tests/{test_id}", summary="获取 A/B 测试详情")
async def get_ab_test(test_id: str):
    test = db.get_ab_test(test_id)
    if not test:
        raise HTTPException(404, "A/B 测试不存在")
    return test.model_dump()


# ── 统计 ──────────────────────────────────────────────────────────────────
@app.get("/api/stats", summary="平台统计")
async def get_stats():
    return db.get_stats()


# ── 模板工具 ──────────────────────────────────────────────────────────────
@app.post("/api/template/validate", summary="验证模板语法")
async def validate_template(body: dict[str, str]):
    template = body.get("template", "")
    ok, msg = engine.validate_template(template)
    return {"valid": ok, "message": msg}


@app.post("/api/template/extract-variables", summary="提取模板变量")
async def extract_variables(body: dict[str, str]):
    template = body.get("template", "")
    try:
        vars_ = engine.extract_variables(template)
        return {"variables": vars_}
    except Exception as exc:
        raise HTTPException(400, str(exc))


# ── 内嵌 Web UI ──────────────────────────────────────────────────────────
TEMPLATES_DIR = Path(__file__).parent / "templates"
# ── Web UI ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_ui():
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>templates/index.html not found</h1>")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host=CONFIG["app"]["host"],
        port=CONFIG["app"]["port"],
        reload=CONFIG["app"]["debug"],
    )

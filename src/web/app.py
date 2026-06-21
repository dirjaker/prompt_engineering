"""
Web Dashboard for Prompt Engineering Platform
Provides a dashboard for managing prompts, evaluations, and A/B tests.
"""
import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from database import Database
from evaluator import Evaluator
from models import (
    Prompt, PromptVersion, PromptStatus, VariableDefinition, VariableType,
    EvalMetric, EvalRequest, ABTest, ABTestVariant, ABTestStatus, RenderRequest,
)
from template_engine import TemplateEngine

STATIC_DIR = Path(__file__).parent / "static"

CONFIG_PATH = PROJECT_ROOT / "config.yaml"
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
    title="Prompt Engineering Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats():
    return db.get_stats()


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
    change_note: str = "Initial version"


@app.post("/api/prompts")
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
    return {"id": prompt.id, "message": "Prompt created", "version": 1}


@app.get("/api/prompts")
async def list_prompts(
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
):
    prompts = db.list_prompts(category=category, status=status, search=search)
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


@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")
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
            {"version": ver.version, "change_note": ver.change_note, "created_at": ver.created_at.isoformat()}
            for ver in prompt.versions
        ],
        "created_at": prompt.created_at.isoformat(),
        "updated_at": prompt.updated_at.isoformat(),
    }


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    if not db.delete_prompt(prompt_id):
        raise HTTPException(404, "Prompt not found")
    return {"message": "Deleted"}


@app.post("/api/prompts/{prompt_id}/evaluate")
async def evaluate_prompt(prompt_id: str, body: EvalRequest = None):
    prompt = db.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")
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
        "average_scores": {k: round(sum(v) / len(v), 4) for k, v in avg_scores.items()},
    }


@app.post("/api/ab-tests")
async def create_ab_test(body: dict):
    variants = [ABTestVariant(**v) for v in body.get("variants", [])]
    test = ABTest(
        name=body.get("name", ""),
        description=body.get("description", ""),
        variants=variants,
        sample_size=body.get("sample_size", 100),
    )
    db.save_ab_test(test)
    return {"id": test.id, "message": "A/B test created"}


@app.post("/api/ab-tests/{test_id}/run")
async def run_ab_test(test_id: str):
    test = db.get_ab_test(test_id)
    if not test:
        raise HTTPException(404, "A/B test not found")
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


@app.get("/api/ab-tests")
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


def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_dashboard()

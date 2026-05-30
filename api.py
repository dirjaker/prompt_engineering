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
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_ui():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prompt Engineering Platform</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--primary:#6366f1;
        --primary-h:#818cf8;--text:#e2e8f0;--muted:#94a3b8;--green:#22c55e;
        --red:#ef4444;--orange:#f59e0b;--radius:12px}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);
       color:var(--text);min-height:100vh}
  .container{max-width:1200px;margin:0 auto;padding:20px}
  header{background:linear-gradient(135deg,#1e1b4b,#312e81,#1e1b4b);
         padding:30px;border-radius:var(--radius);margin-bottom:24px;text-align:center}
  header h1{font-size:28px;font-weight:700;background:linear-gradient(90deg,#c7d2fe,#a5b4fc,#c7d2fe);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent}
  header p{color:var(--muted);margin-top:6px;font-size:14px}
  nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
  nav button{padding:8px 18px;border:1px solid var(--border);background:var(--card);
             color:var(--text);border-radius:8px;cursor:pointer;font-size:14px;transition:.2s}
  nav button:hover,nav button.active{background:var(--primary);border-color:var(--primary)}
  .card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
        padding:20px;margin-bottom:16px}
  .card h2{font-size:18px;margin-bottom:12px;color:var(--primary-h)}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}
  .stat{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
        padding:16px;text-align:center}
  .stat .num{font-size:32px;font-weight:700;color:var(--primary-h)}
  .stat .label{color:var(--muted);font-size:13px;margin-top:4px}
  input,textarea,select{width:100%;padding:10px;border:1px solid var(--border);
                        background:var(--bg);color:var(--text);border-radius:8px;
                        font-size:14px;font-family:inherit;margin-bottom:10px}
  textarea{min-height:120px;resize:vertical}
  button.btn{padding:10px 24px;border:none;border-radius:8px;cursor:pointer;
             font-size:14px;font-weight:600;transition:.2s}
  .btn-primary{background:var(--primary);color:white}
  .btn-primary:hover{background:var(--primary-h)}
  .btn-green{background:var(--green);color:white}
  .btn-red{background:var(--red);color:white}
  .btn-sm{padding:6px 14px;font-size:12px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border)}
  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase}
  .tag{display:inline-block;padding:2px 8px;background:var(--primary);color:white;
       border-radius:4px;font-size:11px;margin:2px}
  .badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600}
  .badge-draft{background:#334155;color:#94a3b8}
  .badge-active{background:#064e3b;color:#34d399}
  .badge-archived{background:#451a03;color:#fbbf24}
  .result-box{background:var(--bg);border:1px solid var(--border);border-radius:8px;
              padding:14px;margin-top:10px;white-space:pre-wrap;font-size:13px;line-height:1.6}
  .hidden{display:none}
  .flex{display:flex;gap:10px;align-items:center}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .score-bar{height:8px;background:var(--border);border-radius:4px;margin-top:4px}
  .score-fill{height:100%;border-radius:4px;transition:width .5s}
  @media(max-width:768px){.grid-2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>⚡ Prompt Engineering Platform</h1>
    <p>企业级 Prompt 管理 · 模板引擎 · A/B 测试 · 效果评估</p>
  </header>

  <nav>
    <button class="active" onclick="show('dashboard')">📊 仪表盘</button>
    <button onclick="show('prompts')">📝 Prompt 管理</button>
    <button onclick="show('editor')">✏️ 编辑器</button>
    <button onclick="show('evaluate')">🧪 评估</button>
    <button onclick="show('abtest')">🔬 A/B 测试</button>
  </nav>

  <!-- 仪表盘 -->
  <div id="dashboard" class="section">
    <div class="stats" id="statsBox"></div>
    <div class="card"><h2>最近 Prompts</h2><div id="recentPrompts"></div></div>
  </div>

  <!-- Prompt 管理 -->
  <div id="prompts" class="section hidden">
    <div class="flex" style="margin-bottom:16px;justify-content:space-between">
      <div class="flex">
        <input id="searchInput" placeholder="搜索 Prompt..." style="width:250px;margin:0"
               oninput="loadPrompts()">
        <select id="filterCat" style="width:150px;margin:0" onchange="loadPrompts()">
          <option value="">全部分类</option>
          <option value="general">通用</option>
          <option value="summarization">摘要</option>
          <option value="translation">翻译</option>
          <option value="code_generation">代码生成</option>
          <option value="qa">问答</option>
        </select>
      </div>
      <button class="btn btn-primary" onclick="show('editor')">+ 新建 Prompt</button>
    </div>
    <div class="card"><div id="promptTable"></div></div>
  </div>

  <!-- 编辑器 -->
  <div id="editor" class="section hidden">
    <div class="card">
      <h2 id="editorTitle">新建 Prompt</h2>
      <input id="editId" type="hidden">
      <div class="grid-2">
        <div><label>名称</label><input id="editName" placeholder="Prompt 名称"></div>
        <div><label>分类</label>
          <select id="editCat">
            <option value="general">通用</option><option value="summarization">摘要</option>
            <option value="translation">翻译</option><option value="code_generation">代码生成</option>
            <option value="qa">问答</option><option value="creative_writing">创意写作</option>
          </select>
        </div>
      </div>
      <label>描述</label><input id="editDesc" placeholder="描述">
      <label>标签 (逗号分隔)</label><input id="editTags" placeholder="tag1, tag2">
      <label>System Prompt</label><textarea id="editSys" placeholder="系统提示词"></textarea>
      <label>模板 <span style="color:var(--muted);font-size:12px">(支持 {{variable}}, {% if %}, {% for %}, 过滤器)</span></label>
      <textarea id="editTpl" placeholder="你好 {{name}}，请帮我{{action}}以下内容：{{content}}" style="min-height:180px"></textarea>
      <label>变量定义 (JSON)</label>
      <textarea id='editVars' placeholder='[{"name":"name","var_type":"string","description":"用户名","required":true}]'></textarea>
      <div class="grid-2">
        <div><label>模型提示</label><input id="editModel" placeholder="gpt-4"></div>
        <div><label>Temperature</label><input id="editTemp" type="number" step="0.1" value="0.7"></div>
      </div>
      <label>变更说明</label><input id="editNote" placeholder="版本说明">
      <div style="margin-top:14px">
        <button class="btn btn-primary" onclick="savePrompt()">💾 保存</button>
        <button class="btn btn-green" onclick="previewTemplate()" style="margin-left:8px">👁️ 预览</button>
        <button class="btn" style="margin-left:8px;background:var(--border)" onclick="show('prompts')">取消</button>
      </div>
      <div id="previewBox" class="result-box hidden" style="margin-top:14px"></div>
    </div>
  </div>

  <!-- 评估 -->
  <div id="evaluate" class="section hidden">
    <div class="card">
      <h2>Prompt 评估</h2>
      <div class="grid-2">
        <div><label>选择 Prompt</label><select id="evalPrompt" onchange="loadEvals()"></select></div>
        <div style="align-self:end"><button class="btn btn-primary" onclick="runEval()">🚀 运行评估</button></div>
      </div>
      <div id="evalResults" style="margin-top:16px"></div>
      <div id="evalHistory" style="margin-top:16px"></div>
    </div>
  </div>

  <!-- A/B 测试 -->
  <div id="abtest" class="section hidden">
    <div class="card">
      <h2>A/B 测试</h2>
      <label>测试名称</label><input id="abName" placeholder="对比测试名称">
      <div class="grid-2">
        <div><label>变体 A - Prompt ID</label><input id="abA" placeholder="Prompt ID"></div>
        <div><label>变体 B - Prompt ID</label><input id="abB" placeholder="Prompt ID"></div>
      </div>
      <label>每组样本量</label><input id="abSize" type="number" value="50">
      <button class="btn btn-primary" onclick="runAB()">🔬 创建并运行</button>
      <div id="abResults" style="margin-top:16px"></div>
    </div>
    <div class="card" style="margin-top:12px">
      <h2>历史测试</h2><div id="abHistory"></div>
    </div>
  </div>
</div>

<script>
const API = '/api';
let currentSection = 'dashboard';

function show(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  currentSection = id;
  if (id === 'dashboard') loadDashboard();
  if (id === 'prompts') loadPrompts();
  if (id === 'evaluate') loadEvalPrompts();
  if (id === 'abtest') loadABHistory();
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: {'Content-Type': 'application/json'}, ...opts
  });
  return res.json();
}

// Dashboard
async function loadDashboard() {
  const stats = await api('/stats');
  document.getElementById('statsBox').innerHTML = `
    <div class="stat"><div class="num">${stats.total_prompts}</div><div class="label">Prompts</div></div>
    <div class="stat"><div class="num">${stats.total_versions}</div><div class="label">版本</div></div>
    <div class="stat"><div class="num">${stats.total_evaluations}</div><div class="label">评估次数</div></div>
    <div class="stat"><div class="num">${stats.total_ab_tests}</div><div class="label">A/B 测试</div></div>`;
  const prompts = await api('/prompts');
  let html = '<table><tr><th>名称</th><th>分类</th><th>状态</th><th>版本</th><th>更新时间</th></tr>';
  prompts.slice(0, 10).forEach(p => {
    html += `<tr><td>${p.name}</td><td>${p.category}</td>
      <td><span class="badge badge-${p.status}">${p.status}</span></td>
      <td>v${p.current_version}</td><td>${p.updated_at?.slice(0,16)}</td></tr>`;
  });
  html += '</table>';
  document.getElementById('recentPrompts').innerHTML = html;
}

// Prompts
async function loadPrompts() {
  const search = document.getElementById('searchInput').value;
  const cat = document.getElementById('filterCat').value;
  let url = '/prompts?';
  if (search) url += `search=${encodeURIComponent(search)}&`;
  if (cat) url += `category=${cat}`;
  const prompts = await api(url);
  let html = '<table><tr><th>名称</th><th>描述</th><th>分类</th><th>标签</th><th>状态</th><th>版本</th><th>操作</th></tr>';
  prompts.forEach(p => {
    const tags = p.tags.map(t => `<span class="tag">${t}</span>`).join('');
    html += `<tr><td><strong>${p.name}</strong></td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${p.description}</td>
      <td>${p.category}</td><td>${tags}</td>
      <td><span class="badge badge-${p.status}">${p.status}</span></td>
      <td>v${p.current_version}</td>
      <td><button class="btn btn-primary btn-sm" onclick="editPrompt('${p.id}')">编辑</button>
          <button class="btn btn-red btn-sm" onclick="delPrompt('${p.id}')">删除</button></td></tr>`;
  });
  html += '</table>';
  document.getElementById('promptTable').innerHTML = html;
}

// Editor
async function editPrompt(id) {
  const p = await api(`/prompts/${id}`);
  document.getElementById('editId').value = p.id;
  document.getElementById('editName').value = p.name;
  document.getElementById('editDesc').value = p.description;
  document.getElementById('editCat').value = p.category;
  document.getElementById('editTags').value = p.tags.join(', ');
  document.getElementById('editSys').value = p.system_prompt;
  document.getElementById('editTpl').value = p.template;
  document.getElementById('editVars').value = JSON.stringify(p.variables, null, 2);
  document.getElementById('editModel').value = p.model_hint;
  document.getElementById('editTemp').value = p.temperature;
  document.getElementById('editNote').value = '';
  document.getElementById('editorTitle').textContent = '编辑 Prompt';
  show('editor');
}

async function savePrompt() {
  const id = document.getElementById('editId').value;
  const data = {
    name: document.getElementById('editName').value,
    description: document.getElementById('editDesc').value,
    category: document.getElementById('editCat').value,
    tags: document.getElementById('editTags').value.split(',').map(t => t.trim()).filter(Boolean),
    system_prompt: document.getElementById('editSys').value,
    template: document.getElementById('editTpl').value,
    variables: JSON.parse(document.getElementById('editVars').value || '[]'),
    model_hint: document.getElementById('editModel').value,
    temperature: parseFloat(document.getElementById('editTemp').value),
    change_note: document.getElementById('editNote').value,
  };
  if (id) {
    await api(`/prompts/${id}`, {method: 'PUT', body: JSON.stringify(data)});
    alert('更新成功!');
  } else {
    const r = await api('/prompts', {method: 'POST', body: JSON.stringify(data)});
    alert('创建成功! ID: ' + r.id);
  }
  show('prompts');
  loadPrompts();
}

async function delPrompt(id) {
  if (!confirm('确定删除?')) return;
  await api(`/prompts/${id}`, {method: 'DELETE'});
  loadPrompts();
}

async function previewTemplate() {
  const tpl = document.getElementById('editTpl').value;
  const res = await api('/template/validate', {method: 'POST', body: JSON.stringify({template: tpl})});
  let vars;
  try {
    vars = await api('/template/extract-variables', {method: 'POST', body: JSON.stringify({template: tpl})});
  } catch(e) { vars = {variables: []}; }
  const box = document.getElementById('previewBox');
  box.classList.remove('hidden');
  box.innerHTML = `<strong>语法检查:</strong> ${res.valid ? '✅ 正确' : '❌ ' + res.message}\n<strong>模板变量:</strong> ${vars.variables?.join(', ') || '无'}`;
}

// Evaluate
async function loadEvalPrompts() {
  const prompts = await api('/prompts');
  const sel = document.getElementById('evalPrompt');
  sel.innerHTML = prompts.map(p => `<option value="${p.id}">${p.name} (v${p.current_version})</option>`).join('');
  if (prompts.length) loadEvals();
}

async function runEval() {
  const id = document.getElementById('evalPrompt').value;
  const res = await api(`/prompts/${id}/evaluate`, {method: 'POST', body: '{}'});
  let html = '<div class="card"><h2>评估结果</h2>';
  for (const [metric, score] of Object.entries(res.average_scores || {})) {
    const pct = Math.round(score * 100);
    const color = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--orange)' : 'var(--red)';
    html += `<div style="margin-bottom:12px"><div class="flex" style="justify-content:space-between">
      <span>${metric}</span><span style="font-weight:700">${pct}%</span></div>
      <div class="score-bar"><div class="score-fill" style="width:${pct}%;background:${color}"></div></div></div>`;
  }
  html += '</div>';
  document.getElementById('evalResults').innerHTML = html;
  loadEvals();
}

async function loadEvals() {
  const id = document.getElementById('evalPrompt').value;
  if (!id) return;
  const evals = await api(`/prompts/${id}/evaluations`);
  let html = '<table><tr><th>指标</th><th>分数</th><th>版本</th><th>时间</th></tr>';
  evals.slice(0, 20).forEach(e => {
    html += `<tr><td>${e.metric}</td><td>${(e.score * 100).toFixed(1)}%</td><td>v${e.version}</td><td>${e.created_at?.slice(0,16)}</td></tr>`;
  });
  html += '</table>';
  document.getElementById('evalHistory').innerHTML = html;
}

// A/B Test
async function runAB() {
  const name = document.getElementById('abName').value;
  const a = document.getElementById('abA').value;
  const b = document.getElementById('abB').value;
  const size = parseInt(document.getElementById('abSize').value) || 50;
  if (!a || !b) { alert('请输入两个 Prompt ID'); return; }
  const res = await api('/ab-tests', {method: 'POST', body: JSON.stringify({
    name: name || 'A/B Test',
    variants: [{prompt_id: a, version: 1, weight: 1}, {prompt_id: b, version: 1, weight: 1}],
    sample_size: size
  })});
  const run = await api(`/ab-tests/${res.id}/run`, {method: 'POST'});
  let html = '<div class="card"><h2>A/B 测试结果</h2>';
  (run.results || []).forEach((r, i) => {
    const win = i === run.winner_variant_idx;
    html += `<div style="padding:12px;margin:8px 0;border-radius:8px;background:${win ? 'rgba(34,197,94,0.1)' : 'var(--bg)'};border:1px solid ${win ? 'var(--green)' : 'var(--border)'}">
      <strong>变体 ${i + 1} ${win ? '🏆 胜出' : ''}</strong><br>
      Prompt: ${r.prompt_id} | 均分: ${(r.mean_score * 100).toFixed(1)}% | 标准差: ${(r.std_dev * 100).toFixed(1)}% | 样本: ${r.sample_size}</div>`;
  });
  html += '</div>';
  document.getElementById('abResults').innerHTML = html;
  loadABHistory();
}

async function loadABHistory() {
  const tests = await api('/ab-tests');
  let html = '<table><tr><th>名称</th><th>状态</th><th>变体数</th><th>胜出</th><th>时间</th></tr>';
  tests.forEach(t => {
    html += `<tr><td>${t.name}</td><td>${t.status}</td><td>${t.variants_count}</td>
      <td>${t.winner_variant_idx !== null ? '变体 ' + (t.winner_variant_idx + 1) : '-'}</td>
      <td>${t.created_at?.slice(0,16)}</td></tr>`;
  });
  html += '</table>';
  document.getElementById('abHistory').innerHTML = html;
}

loadDashboard();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host=CONFIG["app"]["host"],
        port=CONFIG["app"]["port"],
        reload=CONFIG["app"]["debug"],
    )

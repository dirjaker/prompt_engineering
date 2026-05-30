# ⚡ Prompt Engineering Platform

> 企业级 Prompt 管理平台 — 模板引擎 · 版本控制 · A/B 测试 · 效果评估

---

## ✨ 核心特性

| 功能 | 描述 |
|------|------|
| 📝 **Prompt 管理** | CRUD、标签、分类、全文搜索 |
| 📜 **版本控制** | 每次修改自动创建版本，支持回滚到任意历史版本 |
| 🔧 **模板引擎** | Jinja2 风格：变量注入、条件渲染、循环、过滤器 |
| 🏷️ **变量系统** | 类型定义、类型验证、默认值、枚举约束 |
| 🔬 **A/B 测试** | 多变体对比，统计分析，自动判定胜出方 |
| 📊 **评估引擎** | 多维度自动评分（准确性/相关性/格式/流畅性/完整性） |
| 📈 **统计分析** | 使用统计、分类分布、效果趋势 |
| 🌐 **Web UI** | 内嵌暗色主题管理界面 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (内嵌 HTML)                        │
├─────────────────────────────────────────────────────────────────┤
│                      FastAPI RESTful API                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ Prompt   │  │ Version  │  │  A/B     │  │   Template   │    │
│  │ CRUD API │  │ Mgmt API │  │ Test API │  │   Tool API   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘    │
│       │              │             │                │            │
├───────┴──────────────┴─────────────┴────────────────┴────────────┤
│                       核心引擎层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Template     │  │  Evaluator   │  │    Variable System     │ │
│  │ Engine       │  │  (模拟模式)   │  │    (类型验证/转换)      │ │
│  │ Jinja2 沙箱  │  │  5 维评分     │  │    默认值/枚举约束      │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘ │
│         │                 │                        │             │
├─────────┴─────────────────┴────────────────────────┴─────────────┤
│                    SQLite 持久化层                                 │
│  ┌─────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ prompts │  │  versions  │  │ eval_results │  │  ab_tests │  │
│  └─────────┘  └────────────┘  └──────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 安装依赖

```bash
cd prompt_engineering
pip install -r requirements.txt
```

### 启动服务

```bash
python api.py
```

服务启动后访问：
- **Web UI**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

---

## 📖 API 文档

### Prompt 管理

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/prompts` | 创建 Prompt |
| `GET` | `/api/prompts` | 列出 Prompts（支持搜索、过滤） |
| `GET` | `/api/prompts/{id}` | 获取 Prompt 详情 |
| `PUT` | `/api/prompts/{id}` | 更新 Prompt（自动创建新版本） |
| `DELETE` | `/api/prompts/{id}` | 删除 Prompt |

### 版本管理

| 方法 | 路径 | 描述 |
|------|------|------|
| `GET` | `/api/prompts/{id}/versions` | 获取版本历史 |
| `POST` | `/api/prompts/{id}/rollback/{ver}` | 回滚到指定版本 |

### 渲染 & 评估

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/prompts/{id}/render` | 渲染模板（变量注入） |
| `POST` | `/api/prompts/{id}/evaluate` | 运行评估 |
| `GET` | `/api/prompts/{id}/evaluations` | 获取评估历史 |

### A/B 测试

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/ab-tests` | 创建 A/B 测试 |
| `POST` | `/api/ab-tests/{id}/run` | 运行测试 |
| `GET` | `/api/ab-tests` | 列出测试 |
| `GET` | `/api/ab-tests/{id}` | 测试详情 |

### 工具

| 方法 | 路径 | 描述 |
|------|------|------|
| `POST` | `/api/template/validate` | 验证模板语法 |
| `POST` | `/api/template/extract-variables` | 提取模板变量 |
| `GET` | `/api/stats` | 平台统计 |

---

## 💡 使用示例

### 1. 创建一个 Prompt

```bash
curl -X POST http://localhost:8000/api/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "智能摘要生成器",
    "description": "根据输入文本生成结构化摘要",
    "category": "summarization",
    "tags": ["摘要", "文本处理"],
    "template": "请对以下文本进行{{action | default(\"总结\")}}，要求：\n\n{% if style == \"formal\" %}\n使用正式、学术的语气。\n{% else %}\n使用简洁、通俗的语言。\n{% endif %}\n\n文本内容：\n{{text}}\n\n{% if max_words %}\n字数限制：{{max_words}} 字以内。\n{% endif %}",
    "variables": [
      {"name": "action", "var_type": "string", "default": "总结", "required": false},
      {"name": "style", "var_type": "string", "default": "concise", "enum_values": ["formal", "concise"]},
      {"name": "text", "var_type": "string", "description": "待处理文本"},
      {"name": "max_words", "var_type": "integer", "required": false}
    ],
    "model_hint": "gpt-4",
    "change_note": "初始版本"
  }'
```

### 2. 渲染模板

```bash
curl -X POST http://localhost:8000/api/prompts/{prompt_id}/render \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "action": "总结",
      "style": "formal",
      "text": "人工智能（AI）是计算机科学的一个分支...",
      "max_words": 200
    }
  }'
```

### 3. 运行评估

```bash
curl -X POST http://localhost:8000/api/prompts/{prompt_id}/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": ["accuracy", "relevance", "format"],
    "samples": [
      {"text": "样本1", "style": "formal"},
      {"text": "样本2", "style": "concise"}
    ]
  }'
```

### 4. 创建 A/B 测试

```bash
curl -X POST http://localhost:8000/api/ab-tests \
  -H "Content-Type: application/json" \
  -d '{
    "name": "摘要风格对比",
    "variants": [
      {"prompt_id": "prompt_v1_id", "version": 1, "weight": 1},
      {"prompt_id": "prompt_v2_id", "version": 2, "weight": 1}
    ],
    "sample_size": 100
  }'

# 运行测试
curl -X POST http://localhost:8000/api/ab-tests/{test_id}/run
```

---

## 🔧 模板语法

模板使用 Jinja2 语法：

```jinja2
{# 变量注入 #}
你好，{{name}}！

{# 过滤器 #}
{{content | upper}}
{{text | truncate(100)}}
{{items | join(", ")}}
{{data | to_json}}

{# 条件渲染 #}
{% if language == "zh" %}
请用中文回答。
{% elif language == "en" %}
Please answer in English.
{% else %}
请使用默认语言。
{% endif %}

{# 循环 #}
{% for item in items %}
{{loop.index}}. {{item}}
{% endfor %}

{# 默认值 #}
{{optional_var | default("默认值")}}
```

### 内置过滤器

| 过滤器 | 说明 | 示例 |
|--------|------|------|
| `upper` | 转大写 | `{{name \| upper}}` |
| `lower` | 转小写 | `{{name \| lower}}` |
| `title` | 首字母大写 | `{{name \| title}}` |
| `truncate(n)` | 截断 | `{{text \| truncate(50)}}` |
| `to_json` | JSON 格式 | `{{data \| to_json}}` |
| `join(sep)` | 列表连接 | `{{items \| join(", ")}}` |
| `default(val)` | 默认值 | `{{x \| default("N/A")}}` |
| `word_count` | 单词计数 | `{{text \| word_count}}` |
| `strip` | 去除空白 | `{{text \| strip}}` |

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| 数据存储 | SQLite (WAL 模式) |
| 数据校验 | Pydantic v2 |
| 模板引擎 | Jinja2 (沙箱模式) |
| 配置管理 | PyYAML |
| CLI 美化 | Rich |

---

## 📁 项目结构

```
prompt_engineering/
├── api.py              # FastAPI 服务 + 内嵌 Web UI
├── models.py           # 数据模型 (Prompt/Version/Variable/Eval)
├── template_engine.py  # 模板引擎 (变量注入/条件/循环/过滤器)
├── evaluator.py        # 评估引擎 (模拟模式)
├── database.py         # SQLite 数据库
├── config.yaml         # 配置文件
├── requirements.txt    # 依赖
├── README.md           # 本文档
├── .gitignore
└── data/               # 数据目录 (自动创建)
    └── prompts.db
```

---

## 📄 License

MIT

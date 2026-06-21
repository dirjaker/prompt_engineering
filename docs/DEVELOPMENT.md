# 开发指南

> Prompt 工程平台的开发环境搭建、代码规范、调试技巧和贡献流程。

---

## 一、环境搭建

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| Python | 3.12+ |
| 操作系统 | macOS / Linux / Windows |
| 包管理器 | conda 或 pip |

### 1.2 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/dirjaker/prompt_engineering.git
cd prompt_engineering

# 2. 创建虚拟环境（推荐 conda）
conda create -n prompt_engineering python=3.12 -y
conda activate prompt_engineering

# 3. 安装依赖
pip install -r requirements.txt

# 4. 验证安装
python -c "from models import Prompt; print('安装成功')"
```

### 1.3 依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| `fastapi` | >=0.104.0 | Web 框架 |
| `uvicorn[standard]` | >=0.24.0 | ASGI 服务器 |
| `pydantic` | >=2.5.0 | 数据验证与序列化 |
| `Jinja2` | >=3.1.2 | 模板引擎 |
| `PyYAML` | >=6.0.1 | 配置文件解析 |
| `rich` | >=13.7.0 | 终端美化输出 |
| `python-multipart` | >=0.0.6 | 表单数据解析 |
| `py2app` | >=0.28.0 | macOS 打包（可选） |

---

## 二、运行项目

### 2.1 启动 API 服务

```bash
# 方式一：直接运行
python api.py

# 方式二：使用 uvicorn
uvicorn api:app --host 0.0.0.0 --port 10003 --reload
```

服务启动后：
- API 服务：`http://localhost:10003`
- Swagger 文档：`http://localhost:10003/docs`
- Web UI：`http://localhost:10003/`

### 2.2 启动 Web Dashboard

```bash
cd src/web
python app.py
```

### 2.3 启动 macOS GUI

```bash
python src/macos/app.py
```

---

## 三、代码架构

### 3.1 核心文件

```
api.py                  # FastAPI 应用入口，所有 API 端点
models.py               # Pydantic 数据模型定义
database.py             # SQLite 数据库 CRUD 封装
template_engine.py      # Jinja2 沙箱模板引擎
evaluator.py            # 评估引擎 + A/B 测试逻辑
config.yaml             # 全局配置文件
```

### 3.2 数据流

```
用户请求 → FastAPI 路由 → Pydantic 验证 → 业务逻辑 → Database → 响应
                                      ↓
                              TemplateEngine（模板渲染）
                              Evaluator（评估打分）
```

### 3.3 模块依赖关系

```
api.py
├── models.py          (数据模型)
├── database.py        (数据库操作)
│   └── models.py
├── template_engine.py (模板渲染)
│   └── models.py
└── evaluator.py       (评估引擎)
    ├── models.py
    └── template_engine.py
```

---

## 四、配置说明

配置文件 `config.yaml`：

```yaml
app:
  name: "Prompt Engineering Platform"
  version: "1.0.0"
  host: "0.0.0.0"          # 监听地址
  port: 10003               # 监听端口
  debug: true               # 调试模式（生产环境请关闭）

database:
  path: "data/prompts.db"   # SQLite 数据库路径

template:
  max_length: 10000         # 模板最大字符数
  max_variables: 50         # 最大变量数
  strict_mode: true         # 严格模式

evaluation:
  simulation_mode: true     # 模拟模式（不调用真实 LLM）
  default_sample_size: 10   # A/B 测试默认样本量
  max_sample_size: 1000     # 最大样本量

defaults:
  model: "gpt-4"
  temperature: 0.7
  max_tokens: 2048

categories:                 # 预定义分类
  - general
  - summarization
  - translation
  - code_generation
  - data_analysis
  - creative_writing
  - qa
  - classification
```

---

## 五、开发规范

### 5.1 代码风格

- 遵循 PEP 8 规范
- 使用类型注解（Python 3.12+ 语法）
- Pydantic 模型使用 `Field()` 添加描述
- 函数和类使用 docstring 说明用途

### 5.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `template_engine.py` |
| 类名 | PascalCase | `TemplateEngine` |
| 函数名 | snake_case | `render_prompt()` |
| 常量 | UPPER_SNAKE | `DB_PATH` |
| 私有方法 | `_前缀` | `_create_tables()` |

### 5.3 API 设计规范

- RESTful 风格，资源名使用复数（`/api/prompts`）
- 使用 Pydantic 模型定义请求体
- 返回 JSON 格式响应
- 错误使用 HTTP 状态码 + `detail` 字段

---

## 六、调试技巧

### 6.1 查看 API 文档

启动服务后访问 `http://localhost:10003/docs`，可直接在 Swagger UI 中测试所有 API。

### 6.2 数据库调试

```python
from database import Database

db = Database("data/prompts.db")
print(db.get_stats())
db.close()
```

### 6.3 模板调试

```python
from template_engine import TemplateEngine

engine = TemplateEngine()
# 验证语法
ok, msg = engine.validate_template("你好，{{ name }}！")
# 提取变量
vars = engine.extract_variables("{{ a }} + {{ b }}")
# 渲染
result = engine.render("{{ a }} + {{ b }}", {"a": 1, "b": 2})
```

### 6.4 评估调试

```python
from evaluator import Evaluator
from models import Prompt, PromptVersion

evaluator = Evaluator()
prompt = Prompt(
    name="测试",
    versions=[PromptVersion(prompt_id="test", version=1, template="总结：{{ text }}")]
)
results = evaluator.evaluate_prompt(prompt)
for r in results:
    print(f"{r.metric.value}: {r.score}")
```

---

## 七、已知问题

详见 [代码审查报告](../REVIEW.md)，主要关注：

1. **生产配置**：`config.yaml` 中 `debug: true` 需在部署时关闭
2. **CORS**：Web Dashboard 默认限制为本地访问
3. **SQLite 线程安全**：`check_same_thread=False` 在高并发下需注意
4. **缺少单元测试**：建议添加 `tests/` 目录覆盖核心功能

---

## 八、贡献流程

1. Fork 项目仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "feat: 添加 xxx 功能"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

**提交信息规范：**

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复 Bug |
| `docs:` | 文档更新 |
| `refactor:` | 代码重构 |
| `chore:` | 构建/配置变更 |

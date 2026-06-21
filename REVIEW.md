# 代码审查报告 - prompt_engineering

**审查日期**: 2026-06-22
**审查范围**: 全部 Python 源文件（11 个）、配置文件、依赖文件

---

## 🔴 致命问题

### 1. 生产配置开启调试模式
- **文件**: `config.yaml` **行号**: 7
- **描述**: `debug: true`，且代码中 `api.py:472` 使用 `reload=CONFIG["app"]["debug"]`。调试模式会：(1) 启用自动重载，降低性能；(2) 可能泄露详细错误信息；(3) Uvicorn 的 reload 模式在生产环境不稳定。
- **修复建议**: 生产环境必须设置 `debug: false`，或通过环境变量控制。

### 2. CORS 全开 + 无认证
- **文件**: `src/web/app.py` **行号**: 56-61
- **描述**: `allow_origins=["*"]` 且所有 API 端点无认证。任何人可以创建、修改、删除 Prompt，运行 A/B 测试。
- **修复建议**: 限制 CORS 来源，添加 API Key 或 OAuth2 认证。

### 3. 监听 0.0.0.0 无访问控制
- **文件**: `config.yaml` **行号**: 5-6; `src/web/app.py` **行号**: 249
- **描述**: 服务默认绑定 `0.0.0.0:10003`，暴露在所有网络接口。
- **修复建议**: 生产环境使用 `127.0.0.1` 或通过防火墙限制。

### 4. SQLite 多线程安全问题
- **文件**: `database.py` **行号**: 34
- **描述**: `sqlite3.connect(str(self.db_path), check_same_thread=False)` 允许多线程共享同一连接，但 SQLite 的默认线程安全级别为 `SERIALIZED`，在高并发下可能出现 "database is locked" 错误或数据损坏。
- **修复建议**:
  ```python
  # 方案1: 使用连接池
  from contextlib import contextmanager

  @contextmanager
  def get_connection(self):
      conn = sqlite3.connect(str(self.db_path))
      conn.row_factory = sqlite3.Row
      try:
          yield conn
      finally:
          conn.close()

  # 方案2: 使用 aiosqlite 异步库
  ```

---

## 🟡 警告问题

### 5. 配置文件缺失会导致启动崩溃
- **文件**: `api.py` **行号**: 35-37; `src/web/app.py` **行号**: 31-33
- **描述**: 模块加载时直接 `open(CONFIG_PATH)` 读取配置，若 `config.yaml` 不存在会抛出 `FileNotFoundError` 导致整个应用无法启动。
- **修复建议**:
  ```python
  CONFIG_PATH = Path(__file__).parent / "config.yaml"
  if CONFIG_PATH.exists():
      with open(CONFIG_PATH) as f:
          CONFIG = yaml.safe_load(f)
  else:
      CONFIG = {"app": {"name": "Default", "version": "1.0", "host": "127.0.0.1", "port": 10003, "debug": False}}
  ```

### 6. SQL 查询拼接存在注入风险
- **文件**: `database.py` **行号**: 216-218
- **描述**: `f"%{search}%"` 通过 f-string 构造 LIKE 模式，虽然最终使用参数化查询（`params.extend`），`search` 值本身不会被直接拼入 SQL，但 LIKE 通配符（`%`, `_`）未被转义，用户可构造 `%` 进行模糊匹配攻击。
- **修复建议**:
  ```python
  # 转义 LIKE 特殊字符
  safe_search = search.replace('%', '\\%').replace('_', '\\_')
  params.extend([f"%{safe_search}%", f"%{safe_search}%"])
  ```

### 7. 全局可变状态
- **文件**: `api.py` **行号**: 39-41; `src/web/app.py` **行号**: 35-37
- **描述**: `db`, `engine`, `evaluator` 为全局变量，通过 `lifespan` 初始化。在多 worker 模式下每个 worker 会创建独立实例，可能导致数据库连接数过多。
- **修复建议**: 使用 FastAPI 依赖注入（`Depends`）管理共享资源。

### 8. A/B 测试创建端点使用 dict 而非 Pydantic 模型
- **文件**: `src/web/app.py` **行号**: 200-210
- **描述**: `create_ab_test(body: dict)` 直接接受原始字典，无输入验证。恶意用户可传入任意字段。
- **修复建议**: 使用与 `api.py` 一致的 `ABTestCreate` Pydantic 模型。

### 9. DELETE 操作无软删除
- **文件**: `database.py` **行号**: 230-239
- **描述**: `delete_prompt()` 直接执行 `DELETE` 语句，关联的版本和评估结果也被级联删除，数据不可恢复。
- **修复建议**: 实现软删除（`is_deleted` 标记）或至少在删除前备份数据。

---

## 🔵 建议

### 10. Jinja2 沙箱环境使用正确 ✅
- **文件**: `template_engine.py` **行号**: 65
- **描述**: 使用 `SandboxedEnvironment` 渲染用户模板，防止模板注入攻击。这是一个好的安全实践。
- **建议**: 保持当前实现。

### 11. 缺少请求速率限制
- **描述**: A/B 测试运行端点 (`POST /api/ab-tests/{test_id}/run`) 会执行大量模拟计算（`sample_size` 次循环），无速率限制可能导致 DoS。
- **修复建议**: 添加速率限制中间件，限制 `sample_size` 最大值。

### 12. datetime.utcnow() 已弃用
- **文件**: `models.py` **行号**: 98, 111, 112, 136, 155, 156
- **描述**: Python 3.12+ 中 `datetime.utcnow()` 已弃用。
- **修复建议**: 使用 `datetime.now(datetime.UTC)` 或 `datetime.now(timezone.utc)`。

### 13. 依赖版本未锁定
- **文件**: `requirements.txt`
- **描述**: 所有依赖使用 `>=` 约束，未锁定精确版本。
- **修复建议**: 使用 `pip freeze` 或 `poetry.lock` 锁定版本。

### 14. 缺少单元测试
- **描述**: 项目无测试目录和测试文件，核心功能（模板渲染、评估引擎、版本管理）缺少测试覆盖。
- **修复建议**: 添加 `tests/` 目录，至少覆盖模板渲染、变量验证、CRUD 操作。

### 15. 数据库连接未在异常时回滚
- **文件**: `database.py`
- **描述**: `save_prompt()`, `save_eval_result()` 等写操作使用 `self.conn.commit()` 但未在异常时调用 `self.conn.rollback()`。
- **修复建议**:
  ```python
  try:
      self.conn.execute(...)
      self.conn.commit()
  except Exception:
      self.conn.rollback()
      raise
  ```

---

## 总结评分

| 维度 | 分数 | 说明 |
|------|------|------|
| **安全** | 5/10 | Jinja2 沙箱用得好，但 CORS 全开、无认证、调试模式默认开启、SQLite 线程安全问题 |
| **质量** | 6/10 | Pydantic 模型设计规范，但配置缺失容错、SQL 注入风险、缺少回滚机制 |
| **架构** | 7/10 | 版本管理、评估引擎、A/B 测试设计合理，模板引擎安全 |

**总体评价**: 三个项目中架构设计最好的一个，版本管理和评估系统设计专业。主要问题集中在安全防护（认证缺失、调试模式）和数据库线程安全方面。

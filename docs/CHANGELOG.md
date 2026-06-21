# 更新日志

> Prompt 工程平台版本发布记录，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [1.0.0] - 2026-06-22

### ✨ 新增功能

- **模板管理系统**
  - Jinja2 沙箱渲染引擎，支持变量注入、条件渲染、循环、过滤器
  - 内置 9 个过滤器：`upper`, `lower`, `title`, `truncate`, `to_json`, `join`, `default`, `word_count`, `strip`
  - 模板语法验证与变量自动提取
  - 严格未定义变量检测（`_StrictUndefined`）

- **版本控制**
  - Prompt 版本历史追踪
  - 更新模板或变量时自动创建新版本
  - 一键回滚到任意历史版本

- **A/B 测试**
  - 多变体对比测试框架
  - 自动统计均值、标准差、极值
  - 自动评选最优变体

- **评估引擎**
  - 五维自动评估：准确率、相关性、格式、流畅度、完整性
  - 支持自定义测试样本
  - 评估结果持久化存储

- **RESTful API**
  - 17 个 API 端点，覆盖所有功能
  - 自动生成 Swagger/OpenAPI 文档
  - Pydantic v2 请求验证

- **Web Dashboard**
  - 内嵌 HTML/JS 前端界面
  - Prompt 管理、评估报告、A/B 测试可视化
  - CORS 环境变量配置

- **macOS 桌面客户端**
  - 原生 tkinter GUI
  - 一键启动/停止 Web 服务
  - 快速创建 Prompt、查看统计

- **数据存储**
  - SQLite 数据库，WAL 模式
  - 自动建表与索引优化
  - 级联删除保护

- **安全设计**
  - Jinja2 沙箱渲染，防止模板注入
  - CORS 来源限制（Web Dashboard）
  - 严格变量类型验证

### 🛠️ 技术栈

- Python 3.12+
- FastAPI + Uvicorn
- Pydantic v2
- Jinja2（沙箱模式）
- SQLite（WAL 模式）

### 📝 文档

- README.md：项目概览、功能特性、快速开始
- REVIEW.md：完整代码审查报告（安全、质量、架构三维度评分）
- docs/README.md：文档索引
- docs/API.md：API 接口文档
- docs/ARCHITECTURE.md：架构设计文档
- docs/DEVELOPMENT.md：开发指南
- docs/CHANGELOG.md：更新日志

---

## [未发布] - 计划中

### 📋 待办

- [ ] Web 编辑器（Monaco Editor 集成）
- [ ] 团队协作功能（用户认证、权限管理）
- [ ] 更多评估指标（语义相似度、LLM-as-Judge）
- [ ] 接入真实 LLM API（DeepSeek、OpenAI）
- [ ] 单元测试覆盖
- [ ] 数据库连接池优化
- [ ] 请求速率限制
- [ ] 软删除机制

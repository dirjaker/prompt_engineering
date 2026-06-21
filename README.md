<div align="center">

<img src="assets/banner.svg" width="100%" alt="Prompt 工程平台">

<br>

### ✍️ Prompt 工程平台

[![Stars](https://img.shields.io/github/stars/dirjaker/prompt_engineering?style=flat-square&label=Stars&color=FFD700)](https://github.com/dirjaker/prompt_engineering/stargazers)
[![Forks](https://img.shields.io/github/forks/dirjaker/prompt_engineering?style=flat-square&label=Forks&color=4A90D9)](https://github.com/dirjaker/prompt_engineering/network/members)
[![Contributors](https://img.shields.io/github/contributors/dirjaker/prompt_engineering?style=flat-square&label=Contributors&color=8B4513)](https://github.com/dirjaker/prompt_engineering/graphs/contributors)
[![License](https://img.shields.io/github/license/dirjaker/prompt_engineering?style=flat-square&label=License&color=20B2AA)](https://github.com/dirjaker/prompt_engineering/blob/dev/LICENSE)

</div>

---

> 企业级 Prompt 管理平台 — 模板管理、版本控制、A/B 测试、自动评估，让团队高效创建与优化 Prompt。

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 📝 **模板管理** | Jinja2 沙箱渲染引擎，支持变量注入、条件渲染、循环、过滤器 |
| 🔄 **版本控制** | Prompt 版本历史追踪，支持一键回滚到任意历史版本 |
| ⚖️ **A/B 测试** | 多变体对比测试，自动统计均值、标准差、极值，评选最优变体 |
| 📊 **评估引擎** | 五维自动评估（准确率、相关性、格式、流畅度、完整性），支持自定义样本 |
| 🌐 **RESTful API** | 完整的 FastAPI 后端，17 个 API 端点，自动生成 Swagger 文档 |
| 🖥️ **Web Dashboard** | 内嵌 Web UI，可视化管理 Prompt、查看评估报告 |
| 🍎 **macOS GUI** | 原生 tkinter 桌面客户端，一键启动 Web 服务 |
| 🏷️ **分类与标签** | 灵活的分类体系（8 大类）和标签系统，支持多维筛选 |
| 🔒 **安全设计** | Jinja2 沙箱渲染，严格未定义变量检测，防止模板注入 |

## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/dirjaker/prompt_engineering.git
cd prompt_engineering

# 创建虚拟环境
conda create -n prompt_engineering python=3.12 -y
conda activate prompt_engineering

# 安装依赖
pip install -r requirements.txt

# 运行项目
python main.py
```

启动后访问 `http://localhost:10003` 查看 Web UI，访问 `http://localhost:10003/docs` 查看 API 文档。

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **数据模型** | Pydantic v2 |
| **模板引擎** | Jinja2（沙箱模式） |
| **数据库** | SQLite（WAL 模式） |
| **前端** | HTML + JavaScript |
| **桌面客户端** | Python tkinter |

## 📁 项目结构

```
prompt_engineering/
├── api.py                  # FastAPI 主服务（17 个 API 端点）
├── models.py               # Pydantic 数据模型（Prompt、版本、评估、A/B 测试）
├── database.py             # SQLite 数据库封装
├── template_engine.py      # Jinja2 沙箱模板引擎
├── evaluator.py            # 评估引擎 + A/B 测试逻辑
├── config.yaml             # 全局配置
├── requirements.txt        # Python 依赖
├── src/
│   ├── web/
│   │   ├── app.py          # Web Dashboard 后端
│   │   └── static/
│   │       └── index.html  # 前端页面
│   └── macos/
│       └── app.py          # macOS 桌面客户端
├── docs/                   # 项目文档
│   ├── README.md           # 文档索引
│   ├── API.md              # API 接口文档
│   ├── ARCHITECTURE.md     # 架构设计文档
│   ├── DEVELOPMENT.md      # 开发指南
│   └── CHANGELOG.md        # 更新日志
└── REVIEW.md               # 代码审查报告
```

## 📊 评估维度

| 维度 | 说明 | 评分范围 |
|------|------|----------|
| `accuracy` | 输出准确性 | 0.0 ~ 1.0 |
| `relevance` | 与输入的相关性 | 0.0 ~ 1.0 |
| `format` | 输出格式规范性 | 0.0 ~ 1.0 |
| `fluency` | 语言流畅度 | 0.0 ~ 1.0 |
| `completeness` | 内容完整性 | 0.0 ~ 1.0 |

## 📝 开发日志

- [x] 模板管理系统
- [x] 版本控制
- [x] A/B 测试框架
- [x] 评估引擎
- [x] CLI 工具
- [x] Web Dashboard
- [x] macOS 桌面客户端
- [ ] Web 编辑器（Monaco Editor）
- [ ] 团队协作功能
- [ ] 更多评估指标（语义相似度、LLM-as-Judge）
- [ ] 接入真实 LLM API

## 📚 文档

- [文档索引](docs/README.md)
- [API 接口文档](docs/API.md)
- [架构设计文档](docs/ARCHITECTURE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [更新日志](docs/CHANGELOG.md)
- [代码审查报告](REVIEW.md)

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

🔗 **GitHub**: [dirjaker/prompt_engineering](https://github.com/dirjaker/prompt_engineering)

⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！

</div>

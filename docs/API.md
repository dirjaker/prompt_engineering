# API 接口文档

> Prompt 工程平台 RESTful API 完整接口说明。
>
> 启动服务后访问 `http://localhost:10003/docs` 查看自动生成的 Swagger 文档。

---

## 基础信息

| 项目 | 值 |
|------|------|
| 基础路径 | `http://localhost:10003` |
| 协议 | HTTP |
| 数据格式 | JSON |
| API 版本 | 1.0.0 |

---

## 一、Prompt 管理

### 1.1 创建 Prompt

```
POST /api/prompts
```

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ | — | Prompt 名称 |
| `description` | string | — | `""` | 描述 |
| `category` | string | — | `"general"` | 分类 |
| `tags` | string[] | — | `[]` | 标签列表 |
| `template` | string | — | `""` | Jinja2 模板内容 |
| `system_prompt` | string | — | `""` | 系统提示 |
| `model_hint` | string | — | `""` | 目标模型 |
| `temperature` | float | — | `0.7` | 温度参数 |
| `max_tokens` | int | — | `2048` | 最大 token 数 |
| `variables` | object[] | — | `[]` | 变量定义列表 |
| `change_note` | string | — | `"初始版本"` | 版本说明 |

**响应：**

```json
{
  "id": "a1b2c3d4e5f6",
  "message": "Prompt 创建成功",
  "version": 1
}
```

### 1.2 列出 Prompts

```
GET /api/prompts
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `category` | string | 按分类筛选 |
| `status` | string | 按状态筛选（draft/active/archived） |
| `tag` | string | 按标签筛选 |
| `search` | string | 搜索名称和描述 |

**响应：** Prompt 摘要列表

### 1.3 获取 Prompt 详情

```
GET /api/prompts/{prompt_id}
```

**响应：** 包含完整模板、变量定义、版本历史

### 1.4 更新 Prompt

```
PUT /api/prompts/{prompt_id}
```

当 `template` 或 `variables` 变化时，自动创建新版本。

**请求体：** 同创建接口，所有字段可选。

### 1.5 删除 Prompt

```
DELETE /api/prompts/{prompt_id}
```

级联删除关联的版本和评估结果。

---

## 二、版本管理

### 2.1 获取版本历史

```
GET /api/prompts/{prompt_id}/versions
```

**响应：** 版本列表，包含模板、变量、变更说明、创建时间

### 2.2 回滚到指定版本

```
POST /api/prompts/{prompt_id}/rollback/{version}
```

创建一个新版本，内容复制自目标版本。版本号自动递增。

---

## 三、渲染与评估

### 3.1 渲染模板

```
POST /api/prompts/{prompt_id}/render
```

**请求体：**

```json
{
  "variables": {
    "topic": "人工智能",
    "language": "中文"
  }
}
```

**响应：**

```json
{
  "success": true,
  "rendered": "渲染后的完整 Prompt",
  "mock_output": "模拟的 LLM 输出",
  "model_hint": "gpt-4"
}
```

### 3.2 评估 Prompt

```
POST /api/prompts/{prompt_id}/evaluate
```

**请求体（可选）：**

```json
{
  "metrics": ["accuracy", "relevance"],
  "samples": [{"topic": "AI"}, {"topic": "ML"}]
}
```

**响应：**

```json
{
  "prompt_id": "a1b2c3d4e5f6",
  "version": 1,
  "total_evaluations": 10,
  "average_scores": {
    "accuracy": 0.75,
    "relevance": 0.82
  },
  "details": [...]
}
```

### 3.3 获取评估历史

```
GET /api/prompts/{prompt_id}/evaluations
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `version` | int | 按版本筛选 |

---

## 四、A/B 测试

### 4.1 创建 A/B 测试

```
POST /api/ab-tests
```

**请求体：**

```json
{
  "name": "摘要 Prompt 对比",
  "description": "对比两个版本的摘要效果",
  "variants": [
    {"prompt_id": "abc123", "version": 1, "weight": 1.0},
    {"prompt_id": "abc123", "version": 2, "weight": 1.0}
  ],
  "sample_size": 100
}
```

### 4.2 运行 A/B 测试

```
POST /api/ab-tests/{test_id}/run
```

**响应：**

```json
{
  "id": "test123",
  "status": "completed",
  "winner_variant_idx": 1,
  "results": [
    {
      "variant_index": 0,
      "prompt_id": "abc123",
      "version": 1,
      "mean_score": 0.72,
      "std_dev": 0.08,
      "min_score": 0.55,
      "max_score": 0.89,
      "sample_size": 100
    },
    ...
  ]
}
```

### 4.3 列出 A/B 测试

```
GET /api/ab-tests
```

### 4.4 获取 A/B 测试详情

```
GET /api/ab-tests/{test_id}
```

---

## 五、模板工具

### 5.1 验证模板语法

```
POST /api/template/validate
```

**请求体：**

```json
{"template": "你好，{{ name }}！"}
```

**响应：**

```json
{"valid": true, "message": "模板语法正确"}
```

### 5.2 提取模板变量

```
POST /api/template/extract-variables
```

**响应：**

```json
{"variables": ["name", "language"]}
```

---

## 六、统计

### 6.1 平台统计

```
GET /api/stats
```

**响应：**

```json
{
  "total_prompts": 15,
  "total_versions": 42,
  "total_evaluations": 128,
  "total_ab_tests": 5,
  "categories": {"general": 8, "summarization": 4, "code_generation": 3},
  "avg_scores_by_metric": {"accuracy": 0.75, "relevance": 0.82}
}
```

---

## 七、错误响应

所有端点在出错时返回标准 HTTP 错误：

```json
{
  "detail": "Prompt 不存在"
}
```

| HTTP 状态码 | 说明 |
|-------------|------|
| `400` | 请求参数错误 |
| `404` | 资源不存在 |
| `422` | 请求体验证失败 |
| `500` | 服务器内部错误 |

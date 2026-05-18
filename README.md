# RAG Learning Project

这个项目用来按工程项目的方式学习 RAG：需要什么就学什么，学完马上加到项目里。

## 当前阶段

- Python 虚拟环境
- Git 基础版本管理
- FastAPI 最小接口
- pytest 最小测试
- 文档上传接口
- Markdown/text 文档切块
- React 上传界面
- SQLite 保存 documents 和 chunks
- 前端文档列表和详情查看
- 本地 hash embedding
- OpenAI 兼容 embedding API
- embedding 重建脚本
- `POST /search` 相似度搜索
- DeepSeek API 回答
- `POST /ask` RAG 问答
- 回答引用来源编号
- 前端来源跳转和 chunk 高亮
- `debug: true` 调试信息
- 后端 ask 日志
- SQLite 保存 ask 日志
- 前端问答日志列表和详情
- 删除文档和级联删除 chunks

## 后端运行方式

创建并启用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app.main:app --reload
```

访问：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## 前端运行方式

进入前端目录：

```bash
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

## 文档导入接口

```text
POST /documents
GET /documents
GET /documents/{document_id}
GET /documents/{document_id}/chunks
DELETE /documents/{document_id}
POST /search
POST /ask
GET /ask-logs
GET /ask-logs/{log_id}
```

支持：

- `.md`
- `.txt`

返回：

```json
{
  "id": 1,
  "filename": "demo.md",
  "created_at": "2026-05-18T11:00:00+00:00",
  "chunk_count": 1,
  "chunks": [
    {
      "id": 1,
      "index": 1,
      "text": "# Demo\n\ncontent",
      "char_count": 15
    }
  ]
}
```

## SQLite 数据

默认数据库文件：

```text
data/rag_project.db
```

当前有两张表：

```text
documents：保存文件名、创建时间、chunk 数量
chunks：保存每个文档拆出来的文本块和 embedding
ask_logs：保存每次问答、耗时、context 和 sources
```

删除文档会同步删除该文档的 chunks；问答日志保留历史快照。

## 搜索接口

请求：

```json
{
  "query": "怎么运行测试",
  "top_k": 5
}
```

返回：

```json
{
  "query": "怎么运行测试",
  "results": [
    {
      "citation": null,
      "document_id": 1,
      "filename": "README.md",
      "chunk_id": 1,
      "index": 1,
      "text": "chunk text",
      "char_count": 100,
      "score": 0.42
    }
  ]
}
```

## DeepSeek 配置

复制示例配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

## Embedding 配置

默认使用本地 hash embedding：

```text
EMBEDDING_PROVIDER=hash
```

如果要使用 OpenAI 兼容 embedding API：

```text
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=你的 embedding API Key
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

DeepSeek 官方文档目前没有公开 embedding endpoint，所以这里用 OpenAI 兼容接口。你也可以把 `EMBEDDING_BASE_URL` 指向其他兼容 `/embeddings` 的服务。

重建已有 chunks 的 embedding：

```bash
python scripts/rebuild_embeddings.py
```

只补缺失的 embedding：

```bash
python scripts/rebuild_embeddings.py --missing-only
```

## 问答接口

请求：

```json
{
  "question": "这个项目怎么运行测试？",
  "top_k": 5,
  "debug": true
}
```

返回：

```json
{
  "question": "这个项目怎么运行测试？",
  "answer": "根据资料，可以运行 pytest。[1]",
  "sources": [
    {
      "citation": 1,
      "document_id": 1,
      "filename": "README.md",
      "chunk_id": 1,
      "index": 1,
      "text": "chunk text",
      "char_count": 100,
      "score": 0.42
    }
  ],
  "debug": {
    "search_ms": 2.1,
    "llm_ms": 630.4,
    "total_ms": 632.5,
    "source_count": 1,
    "context": "[1] 文件：README.md / 分块：1 / 相似度：0.42\nchunk text",
    "sources": [
      {
        "citation": 1,
        "filename": "README.md",
        "score": 0.42
      }
    ]
  }
}
```

## 问答日志接口

列表：

```text
GET /ask-logs
```

详情：

```text
GET /ask-logs/{log_id}
```

每条日志保存：

- question
- answer
- search_ms / llm_ms / total_ms
- source_count
- context
- sources

运行测试：

```bash
pytest
```

## 下一步

下一轮可以改进 RAG 质量：

- 增加对话历史
- 增加日志筛选和删除

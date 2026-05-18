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
```

支持：

- `.md`
- `.txt`

返回：

```json
{
  "filename": "demo.md",
  "chunk_count": 1,
  "chunks": [
    {
      "index": 1,
      "text": "# Demo\n\ncontent",
      "char_count": 15
    }
  ]
}
```

运行测试：

```bash
pytest
```

## 下一步

下一轮可以把 chunks 存起来：

- 用 SQLite 保存文档记录
- 给每个 chunk 分配稳定 ID
- 增加 `GET /documents`

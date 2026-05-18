# RAG Learning Project

这个项目用来按工程项目的方式学习 RAG：需要什么就学什么，学完马上加到项目里。

## 当前阶段

- Python 虚拟环境
- Git 基础版本管理
- FastAPI 最小接口
- pytest 最小测试

## 运行方式

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

运行测试：

```bash
pytest
```

## 下一步

下一轮可以加入文档导入接口：

- `POST /documents`
- 读取 `.txt` 或 `.md`
- 把文档切成 chunks

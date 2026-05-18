from fastapi import FastAPI


app = FastAPI(title="RAG Learning Project")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "RAG learning project is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

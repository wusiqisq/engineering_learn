from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.chunking import chunk_text


app = FastAPI(title="RAG Learning Project")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_EXTENSIONS = {".md", ".txt"}


class DocumentChunk(BaseModel):
    index: int
    text: str
    char_count: int


class DocumentUploadResponse(BaseModel):
    filename: str
    chunk_count: int
    chunks: list[DocumentChunk]


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "RAG learning project is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .md and .txt files are supported")

    raw_content = await file.read()
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded") from exc

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="File is empty")

    return DocumentUploadResponse(
        filename=filename,
        chunk_count=len(chunks),
        chunks=[
            DocumentChunk(index=index, text=chunk, char_count=len(chunk))
            for index, chunk in enumerate(chunks, start=1)
        ],
    )

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.chunking import chunk_text
from app.database import (
    DEFAULT_DATABASE_PATH,
    get_document,
    init_database,
    list_chunks,
    list_documents,
    save_document,
)


SUPPORTED_EXTENSIONS = {".md", ".txt"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database(app.state.database_path)
    yield


app = FastAPI(title="RAG Learning Project", lifespan=lifespan)
app.state.database_path = DEFAULT_DATABASE_PATH

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


class DocumentChunk(BaseModel):
    id: int
    index: int
    text: str
    char_count: int


class DocumentSummary(BaseModel):
    id: int
    filename: str
    created_at: str
    chunk_count: int


class DocumentDetail(DocumentSummary):
    chunks: list[DocumentChunk]


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "RAG learning project is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/documents", response_model=list[DocumentSummary])
def get_documents() -> list[DocumentSummary]:
    init_database(app.state.database_path)
    return [DocumentSummary(**document) for document in list_documents(app.state.database_path)]


@app.post("/documents", response_model=DocumentDetail)
async def upload_document(file: UploadFile = File(...)) -> DocumentDetail:
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

    document = save_document(filename, chunks, app.state.database_path)
    return DocumentDetail(**document)


@app.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document_detail(document_id: int) -> DocumentDetail:
    init_database(app.state.database_path)
    document = get_document(document_id, app.state.database_path)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetail(**document)


@app.get("/documents/{document_id}/chunks", response_model=list[DocumentChunk])
def get_document_chunks(document_id: int) -> list[DocumentChunk]:
    init_database(app.state.database_path)
    document = get_document(document_id, app.state.database_path)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return [DocumentChunk(**chunk) for chunk in list_chunks(document_id, app.state.database_path)]

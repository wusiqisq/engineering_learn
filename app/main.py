from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.chunking import chunk_text
from app.database import (
    DEFAULT_DATABASE_PATH,
    deserialize_embedding,
    get_document,
    init_database,
    list_chunks,
    list_chunks_missing_embeddings,
    list_documents,
    list_searchable_chunks,
    save_document,
    update_chunk_embedding,
)
from app.deepseek import DeepSeekAPIError, DeepSeekConfigError, generate_answer
from app.embeddings import cosine_similarity, embed_texts


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


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    citation: int | None = None
    document_id: int
    filename: str
    chunk_id: int
    index: int
    text: str
    char_count: int
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[SearchResult]


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

    embeddings = _embed_texts(chunks)
    document = save_document(filename, chunks, embeddings, app.state.database_path)
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


@app.post("/search", response_model=SearchResponse)
def search_documents(request: SearchRequest) -> SearchResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    return SearchResponse(query=query, results=_search_chunks(query, request.top_k))


@app.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    sources = _search_chunks(question, request.top_k)
    if not sources:
        return AskResponse(question=question, answer="没有找到可用于回答的资料。", sources=[])

    cited_sources = _add_citations(sources)
    try:
        answer = _generate_answer(question, cited_sources)
    except DeepSeekConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except DeepSeekAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AskResponse(question=question, answer=answer, sources=cited_sources)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    embedding_function = getattr(app.state, "embed_texts", embed_texts)
    return embedding_function(texts)


def _ensure_chunk_embeddings() -> None:
    chunks = list_chunks_missing_embeddings(app.state.database_path)
    if not chunks:
        return

    embeddings = _embed_texts([chunk["text"] for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        update_chunk_embedding(chunk["id"], embedding, app.state.database_path)


def _search_chunks(query: str, top_k: int) -> list[SearchResult]:
    init_database(app.state.database_path)
    _ensure_chunk_embeddings()

    query_embedding = _embed_texts([query])[0]
    scored_results: list[SearchResult] = []
    for chunk in list_searchable_chunks(app.state.database_path):
        chunk_embedding = deserialize_embedding(chunk["embedding"])
        score = cosine_similarity(query_embedding, chunk_embedding)
        scored_results.append(
            SearchResult(
                document_id=chunk["document_id"],
                filename=chunk["filename"],
                chunk_id=chunk["chunk_id"],
                index=chunk["index"],
                text=chunk["text"],
                char_count=chunk["char_count"],
                score=round(score, 6),
            )
        )

    scored_results.sort(key=lambda result: result.score, reverse=True)
    return scored_results[:top_k]


def _generate_answer(question: str, sources: list[SearchResult]) -> str:
    answer_function = getattr(app.state, "generate_answer", None)
    source_payload = [source.model_dump() for source in sources]
    if answer_function is not None:
        return answer_function(question, source_payload)
    return generate_answer(question, source_payload)


def _add_citations(sources: list[SearchResult]) -> list[SearchResult]:
    return [
        source.model_copy(update={"citation": index})
        for index, source in enumerate(sources, start=1)
    ]

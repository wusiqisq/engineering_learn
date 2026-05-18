from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.chunking import chunk_text
from app.database import (
    DEFAULT_DATABASE_PATH,
    deserialize_embedding,
    get_ask_log,
    get_document,
    init_database,
    list_ask_logs,
    list_chunks,
    list_chunks_missing_embeddings,
    list_documents,
    list_searchable_chunks,
    save_ask_log,
    save_document,
    update_chunk_embedding,
)
from app.deepseek import DeepSeekAPIError, DeepSeekConfigError, build_context, generate_answer
from app.embeddings import cosine_similarity, embed_texts


SUPPORTED_EXTENSIONS = {".md", ".txt"}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("rag_project")


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
    debug: bool = False


class AskDebug(BaseModel):
    search_ms: float
    llm_ms: float
    total_ms: float
    source_count: int
    context: str
    sources: list[SearchResult]


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[SearchResult]
    debug: AskDebug | None = None


class AskLogSummary(BaseModel):
    id: int
    question: str
    answer: str
    created_at: str
    search_ms: float
    llm_ms: float
    total_ms: float
    source_count: int


class AskLogDetail(AskLogSummary):
    context: str
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


@app.get("/ask-logs", response_model=list[AskLogSummary])
def get_ask_logs() -> list[AskLogSummary]:
    init_database(app.state.database_path)
    return [AskLogSummary(**log) for log in list_ask_logs(app.state.database_path)]


@app.get("/ask-logs/{log_id}", response_model=AskLogDetail)
def get_ask_log_detail(log_id: int) -> AskLogDetail:
    init_database(app.state.database_path)
    ask_log = get_ask_log(log_id, app.state.database_path)
    if ask_log is None:
        raise HTTPException(status_code=404, detail="Ask log not found")
    return AskLogDetail(**ask_log)


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
    total_start = perf_counter()
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    search_start = perf_counter()
    sources = _search_chunks(question, request.top_k)
    search_ms = _elapsed_ms(search_start)
    if not sources:
        total_ms = _elapsed_ms(total_start)
        logger.info(
            "ask no_sources question=%r top_k=%s search_ms=%.2f total_ms=%.2f",
            question,
            request.top_k,
            search_ms,
            total_ms,
        )
        return AskResponse(
            question=question,
            answer="没有找到可用于回答的资料。",
            sources=[],
            debug=_build_debug(request.debug, search_ms, 0.0, total_ms, "", []),
        )

    cited_sources = _add_citations(sources)
    context = build_context([source.model_dump() for source in cited_sources])
    try:
        llm_start = perf_counter()
        answer = _generate_answer(question, cited_sources)
        llm_ms = _elapsed_ms(llm_start)
    except DeepSeekConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except DeepSeekAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    total_ms = _elapsed_ms(total_start)
    source_payload = [source.model_dump() for source in cited_sources]
    save_ask_log(
        question=question,
        answer=answer,
        search_ms=search_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
        context=context,
        sources=source_payload,
        db_path=app.state.database_path,
    )
    logger.info(
        "ask question=%r top_k=%s sources=%s scores=%s search_ms=%.2f llm_ms=%.2f total_ms=%.2f",
        question,
        request.top_k,
        len(cited_sources),
        [source.score for source in cited_sources],
        search_ms,
        llm_ms,
        total_ms,
    )
    return AskResponse(
        question=question,
        answer=answer,
        sources=cited_sources,
        debug=_build_debug(request.debug, search_ms, llm_ms, total_ms, context, cited_sources),
    )


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


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 2)


def _build_debug(
    enabled: bool,
    search_ms: float,
    llm_ms: float,
    total_ms: float,
    context: str,
    sources: list[SearchResult],
) -> AskDebug | None:
    if not enabled:
        return None

    return AskDebug(
        search_ms=search_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
        source_count=len(sources),
        context=context,
        sources=sources,
    )

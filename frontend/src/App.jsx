import { Database, FileSearch, FileText, Loader2, RefreshCw, Search, UploadCloud, XCircle } from "lucide-react";
import React from "react";
import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function App() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [activeDocumentId, setActiveDocumentId] = useState(null);

  const totalChars = useMemo(() => {
    if (!result) {
      return 0;
    }
    return result.chunks.reduce((sum, chunk) => sum + chunk.char_count, 0);
  }, [result]);

  useEffect(() => {
    loadDocuments();
  }, []);

  async function loadDocuments() {
    setIsLoadingDocuments(true);
    try {
      const response = await fetch(`${API_BASE_URL}/documents`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "读取文档列表失败");
      }

      setDocuments(data);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setIsLoadingDocuments(false);
    }
  }

  async function loadDocumentDetail(documentId) {
    setActiveDocumentId(documentId);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/documents/${documentId}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "读取文档详情失败");
      }

      setResult(data);
    } catch (loadError) {
      setError(loadError.message);
    }
  }

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
    setError("");
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) {
      setError("请选择一个 .md 或 .txt 文件");
      return;
    }

    setIsUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/documents`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "上传失败");
      }

      setResult(data);
      setActiveDocumentId(data.id);
      setSearchResults([]);
      await loadDocuments();
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setIsUploading(false);
    }
  }

  function clearFile() {
    setFile(null);
    setError("");
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function handleSearch(event) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setError("请输入搜索问题");
      return;
    }

    setIsSearching(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: trimmedQuery, top_k: 5 }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "搜索失败");
      }

      setSearchResults(data.results);
    } catch (searchError) {
      setError(searchError.message);
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <div className="header-row">
          <div>
            <p className="eyebrow">RAG Project</p>
            <h1>Document Import</h1>
          </div>
          <a className="api-link" href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">
            API 文档
          </a>
        </div>

        <form className="upload-panel" onSubmit={handleUpload}>
          <label className="drop-zone" htmlFor="document-file">
            <UploadCloud aria-hidden="true" size={28} />
            <span>{file ? file.name : "选择 Markdown 或文本文件"}</span>
            <input
              ref={inputRef}
              id="document-file"
              name="file"
              type="file"
              accept=".md,.txt,text/markdown,text/plain"
              onChange={handleFileChange}
            />
          </label>

          <div className="actions">
            <button className="primary-button" type="submit" disabled={isUploading}>
              {isUploading ? <Loader2 className="spin" size={18} /> : <FileText size={18} />}
              拆分并保存
            </button>
            <button className="icon-button" type="button" onClick={clearFile} aria-label="Clear file">
              <XCircle size={20} />
            </button>
          </div>
        </form>

        {error ? <p className="error-message">{error}</p> : null}

        <form className="search-panel" onSubmit={handleSearch}>
          <div className="search-input-wrap">
            <Search size={20} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="输入问题，搜索最相关的 chunks"
            />
          </div>
          <button className="primary-button search-button" type="submit" disabled={isSearching}>
            {isSearching ? <Loader2 className="spin" size={18} /> : <FileSearch size={18} />}
            搜索
          </button>
        </form>

        <div className="content-grid">
          <aside className="document-library">
            <div className="panel-title">
              <div>
                <Database size={18} />
                <h2>已保存文档</h2>
              </div>
              <button className="ghost-button" type="button" onClick={loadDocuments} aria-label="Refresh documents">
                {isLoadingDocuments ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
              </button>
            </div>

            <div className="document-list">
              {documents.length === 0 && !isLoadingDocuments ? (
                <p className="empty-state">还没有保存的文档</p>
              ) : null}

              {documents.map((document) => (
                <button
                  className={`document-row ${activeDocumentId === document.id ? "active" : ""}`}
                  key={document.id}
                  type="button"
                  onClick={() => loadDocumentDetail(document.id)}
                >
                  <span>{document.filename}</span>
                  <small>{document.chunk_count} chunks</small>
                </button>
              ))}
            </div>
          </aside>

          <section className="result-section" aria-live="polite">
            {searchResults.length > 0 ? (
              <section className="search-results">
                <div className="section-heading">
                  <h2>搜索结果</h2>
                  <span>{searchResults.length} chunks</span>
                </div>
                <div className="chunk-list">
                  {searchResults.map((result) => (
                    <article className="chunk-card search-card" key={result.chunk_id}>
                      <div className="chunk-meta">
                        <span>
                          {result.filename} / 分块 {result.index}
                        </span>
                        <span>score {result.score.toFixed(3)}</span>
                      </div>
                      <pre>{result.text}</pre>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            {result ? (
              <>
                <div className="stats-grid">
                  <div>
                    <span>文件</span>
                    <strong>{result.filename}</strong>
                  </div>
                  <div>
                    <span>分块</span>
                    <strong>{result.chunk_count}</strong>
                  </div>
                  <div>
                    <span>字符数</span>
                    <strong>{totalChars}</strong>
                  </div>
                </div>

                <div className="chunk-list">
                  {result.chunks.map((chunk) => (
                    <article className="chunk-card" key={chunk.id}>
                      <div className="chunk-meta">
                        <span>分块 {chunk.index}</span>
                        <span>{chunk.char_count} chars</span>
                      </div>
                      <pre>{chunk.text}</pre>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <div className="detail-empty">
                <FileText size={24} />
                <span>上传文档或从列表选择文档</span>
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

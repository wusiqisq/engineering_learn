import { FileText, Loader2, UploadCloud, XCircle } from "lucide-react";
import React from "react";
import { useMemo, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function App() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  const totalChars = useMemo(() => {
    if (!result) {
      return 0;
    }
    return result.chunks.reduce((sum, chunk) => sum + chunk.char_count, 0);
  }, [result]);

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
    setResult(null);
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
    setResult(null);

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
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setIsUploading(false);
    }
  }

  function clearFile() {
    setFile(null);
    setResult(null);
    setError("");
    if (inputRef.current) {
      inputRef.current.value = "";
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
              拆分文档
            </button>
            <button className="icon-button" type="button" onClick={clearFile} aria-label="Clear file">
              <XCircle size={20} />
            </button>
          </div>
        </form>

        {error ? <p className="error-message">{error}</p> : null}

        {result ? (
          <section className="result-section" aria-live="polite">
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
                <article className="chunk-card" key={chunk.index}>
                  <div className="chunk-meta">
                    <span>分块 {chunk.index}</span>
                    <span>{chunk.char_count} chars</span>
                  </div>
                  <pre>{chunk.text}</pre>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}

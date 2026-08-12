import { useRef, useState } from 'react'

export default function UploadScreen({ uploading, statusLines, error, onUpload, health }) {
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState('')

  const pick = (e) => {
    const file = e.target.files && e.target.files[0]
    setFileName(file ? file.name : '')
  }

  const submit = (e) => {
    e.preventDefault()
    if (uploading) return
    const file = inputRef.current && inputRef.current.files && inputRef.current.files[0]
    if (file) onUpload(file)
  }

  return (
    <div className="upload-wrap">
      <div className="upload-card">
        <h1>Agentic 835 Assistant</h1>
        <p className="sub">Upload an 835 file and chat with a local AI about your claims.</p>

        {!uploading ? (
          <form onSubmit={submit}>
            <label className="drop" htmlFor="fileInput">
              <strong>[ Upload 835 File ]</strong>
              <span>.835, .x12, .edi, or .txt — stays on your PC</span>
              <input
                id="fileInput"
                ref={inputRef}
                type="file"
                accept=".835,.x12,.edi,.txt,text/plain"
                onChange={pick}
                required
              />
            </label>
            {fileName && <div className="selected">Selected: {fileName}</div>}
            <button className="primary" type="submit" disabled={!fileName}>
              Upload &amp; Analyze
            </button>
            {error && <div className="error-banner">{error}</div>}
          </form>
        ) : (
          <div className="upload-progress">
            {statusLines.map((line, i) => (
              <div key={i} className="status-line">
                {line}
              </div>
            ))}
            <div className="spinner" />
          </div>
        )}

        {health && (
          <div className="upload-health">
            <span className={`mini-status ${health.backend === 'online' ? 'ok' : 'down'}`}>
              Backend {health.backend}
            </span>
            <span className={`mini-status ${health.ollama === 'online' ? 'ok' : 'down'}`}>
              Ollama {health.ollama}
            </span>
            {health.ollama === 'offline' && (
              <span className="mini-warn">Ollama is not running. Please start Ollama and try again.</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

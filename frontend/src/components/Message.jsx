import { useState } from 'react'
import { combineFiles, createZip } from '../api.js'

function DownloadButtons({ sessionId, files }) {
  const [zipBusy, setZipBusy] = useState(false)
  const [mirBusy, setMirBusy] = useState(false)

  if (!files || files.length === 0) return null

  const downloadAll = async () => {
    setZipBusy(true)
    try {
      const res = await createZip(sessionId, files.map((f) => f.file_id))
      window.location.href = res.download_url
    } catch (err) {
      alert(`Could not create ZIP: ${err.message}`)
    } finally {
      setZipBusy(false)
    }
  }

  const downloadCombined = async () => {
    setMirBusy(true)
    try {
      const res = await combineFiles(sessionId, files.map((f) => f.file_id))
      window.location.href = res.download_url
    } catch (err) {
      alert(`Could not create combined MIR: ${err.message}`)
    } finally {
      setMirBusy(false)
    }
  }

  return (
    <div className="downloads">
      <div className="download-row">
        {files.map((f) => (
          <a key={f.file_id} className="dl-btn" href={f.download_url} download={f.file_name}>
            <span>📄</span> {f.file_name}
          </a>
        ))}
      </div>
      {files.length > 1 && (
        <div className="dl-group">
          <button className="dl-all" onClick={downloadCombined} disabled={mirBusy}>
            {mirBusy ? 'Stitching…' : '⬇ Download All (.mir)'}
          </button>
          <button className="dl-all" onClick={downloadAll} disabled={zipBusy}>
            {zipBusy ? 'Zipping…' : '⬇ Download All (ZIP)'}
          </button>
        </div>
      )}
    </div>
  )
}

export default function Message({ message, sessionId }) {
  const role = message.role

  if (role === 'system') {
    return <div className="msg system">{message.content}</div>
  }
  if (role === 'error') {
    return <div className="msg error">{message.content}</div>
  }

  const content = message.content || ''
  const lines = content.split('\n')
  return (
    <div className={`msg ${role}`}>
      <div className="bubble">
        {lines.map((line, i) =>
          line.trim() === '' ? (
            <div key={i} className="msg-break" />
          ) : (
            <div key={i} className="line">
              {line}
            </div>
          ),
        )}
        <DownloadButtons sessionId={sessionId} files={message.files} />
      </div>
    </div>
  )
}

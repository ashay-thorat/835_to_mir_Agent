import { useEffect, useRef, useState } from 'react'
import Message from './Message.jsx'

export default function ChatScreen({ session, messages, busy, onSend, onReset }) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  const submit = (e) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    onSend(text)
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(e)
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <div className="file-info">
          <span className="file-name">📁 {session.fileName}</span>
          <span className="file-meta">
            {session.claimCount} Claims <span className="ok-tag">✓ Analyzed</span>
          </span>
        </div>
        <button className="new-file" onClick={onReset} title="Upload a different 835 file">
          New file
        </button>
      </header>

      <div className="messages" ref={scrollRef}>
        {messages.map((m) => (
          <Message key={m.id} message={m} sessionId={session.id} />
        ))}
        {busy && (
          <div className="msg assistant">
            <div className="bubble typing">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-label">Agent working…</span>
            </div>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask something about your 835…"
          rows={2}
          disabled={busy}
        />
        <button type="submit" className="primary" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

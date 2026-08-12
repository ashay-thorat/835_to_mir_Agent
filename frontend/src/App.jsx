import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHealth, sendChat, uploadFile } from './api.js'
import HealthBar from './components/HealthBar.jsx'
import UploadScreen from './components/UploadScreen.jsx'
import ChatScreen from './components/ChatScreen.jsx'

let messageId = 0
const nextId = () => `m${++messageId}`

function eventsToMessages(events) {
  const out = []
  for (const ev of events) {
    const kind = ev.kind
    const text = ev.text || ''
    if (kind === 'assistant') {
      out.push({ id: nextId(), role: 'assistant', content: text, files: [] })
    } else if (kind === 'block') {
      const last = out[out.length - 1]
      if (last && last.role === 'assistant') {
        last.content = last.content ? last.content + '\n\n' + text : text
      } else {
        out.push({ id: nextId(), role: 'assistant', content: text, files: [] })
      }
    } else if (kind === 'note') {
      out.push({ id: nextId(), role: 'system', content: text, files: [] })
    } else if (kind === 'report') {
      out.push({ id: nextId(), role: 'assistant', content: text, files: [] })
    } else if (kind === 'files') {
      const files = ev.files || []
      const last = out[out.length - 1]
      if (last && last.role === 'assistant' && files.length) {
        last.files = files
      }
    } else if (kind === 'error') {
      out.push({ id: nextId(), role: 'error', content: text, files: [] })
    }
  }
  return out
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [phase, setPhase] = useState('upload') // upload | uploading | chat
  const [uploadStatus, setUploadStatus] = useState([])
  const [uploadError, setUploadError] = useState('')
  const [session, setSession] = useState(null)
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)

  const poll = useCallback(async () => {
    try {
      const h = await fetchHealth()
      setHealth(h)
    } catch {
      setHealth({ backend: 'offline', ollama: 'unknown', model: 'llama3.2', model_ready: false })
    }
  }, [])

  useEffect(() => {
    poll()
    const timer = setInterval(poll, 10000)
    return () => clearInterval(timer)
  }, [poll])

  const handleUpload = async (file) => {
    setUploadError('')
    setUploadStatus(['Uploading…'])
    setPhase('uploading')
    try {
      const res = await uploadFile(file)
      setUploadStatus(['✓ File uploaded', '✓ 835 analyzed', '✓ Claims extracted'])
      await new Promise((r) => setTimeout(r, 300))
      setSession({ id: res.session_id, fileName: res.file_name, claimCount: res.claim_count })
      setMessages([{ id: nextId(), role: 'assistant', content: res.greeting || 'Hi! I’ve analyzed your 835 file. How can I help you?', files: [] }])
      setPhase('chat')
    } catch (err) {
      setUploadError(err.message)
      setPhase('upload')
    }
  }

  const handleSend = async (text) => {
    if (!session) return
    setMessages((prev) => [...prev, { id: nextId(), role: 'user', content: text, files: [] }])
    setBusy(true)
    try {
      const res = await sendChat(session.id, text)
      const newMsgs = eventsToMessages(res.events || [])
      setMessages((prev) => [...prev, ...newMsgs])
    } catch (err) {
      const isOllama = /ollama|runtime/i.test(err.message)
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'error',
          content: isOllama
            ? `Ollama is not running. Please start Ollama and try again.\n(${err.message})`
            : err.message,
          files: [],
        },
      ])
    } finally {
      setBusy(false)
      poll()
    }
  }

  const handleReset = () => {
    setSession(null)
    setMessages([])
    setUploadStatus([])
    setUploadError('')
    setPhase('upload')
  }

  return (
    <div className="app">
      <nav className="topbar">
        <div className="brand">Agentic 835 Assistant</div>
        <HealthBar health={health} />
      </nav>

      {phase === 'upload' || phase === 'uploading' ? (
        <UploadScreen
          uploading={phase === 'uploading'}
          statusLines={uploadStatus}
          error={uploadError}
          onUpload={handleUpload}
          health={health}
        />
      ) : (
        <ChatScreen
          session={session}
          messages={messages}
          busy={busy}
          onSend={handleSend}
          onReset={handleReset}
        />
      )}
    </div>
  )
}

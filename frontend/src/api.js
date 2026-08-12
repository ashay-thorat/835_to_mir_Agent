async function handle(res) {
  let payload = null
  try {
    payload = await res.json()
  } catch {
    payload = null
  }
  if (!res.ok) {
    const detail =
      payload && payload.detail
        ? payload.detail
        : `Request failed (${res.status})`
    throw new Error(detail)
  }
  return payload
}

export async function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/files/upload', { method: 'POST', body: form })
  return handle(res)
}

export async function sendChat(sessionId, message) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  return handle(res)
}

export async function fetchHealth() {
  const res = await fetch('/api/health')
  return handle(res)
}

export async function createZip(sessionId, fileIds) {
  const res = await fetch('/api/mir/zip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, file_ids: fileIds }),
  })
  return handle(res)
}

export async function combineFiles(sessionId, fileIds) {
  const res = await fetch('/api/mir/combine', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, file_ids: fileIds }),
  })
  return handle(res)
}

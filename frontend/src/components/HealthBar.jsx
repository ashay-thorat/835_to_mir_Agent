function Dot({ status, label }) {
  const ok = status === 'online' || status === 'ready' || status === true
  return (
    <div className={`pill ${ok ? 'ok' : 'down'}`} title={status}>
      <span className="dot" />
      {label} {status === true || status === 'ready' ? '' : '●'}
      <span className="pill-state">{status === true ? 'Ready' : status === 'ready' ? 'Ready' : status}</span>
    </div>
  )
}

export default function HealthBar({ health }) {
  if (!health) {
    return (
      <div className="health">
        <span className="pill checking">
          <span className="dot" /> Checking…
        </span>
      </div>
    )
  }
  const modelStatus = health.model_ready ? 'ready' : 'down'
  return (
    <div className="health">
      <Dot status={health.backend} label="Backend" />
      <Dot status={health.ollama} label="Ollama" />
      <Dot status={modelStatus} label={`${health.model || 'Model'}`} />
    </div>
  )
}

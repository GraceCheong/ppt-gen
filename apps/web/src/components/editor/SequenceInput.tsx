interface Props {
  value: string
  onChange: (v: string) => void
}

const PRESETS = ['I', 'V', 'V1', 'V2', 'V3', 'A', 'C', 'Pc', 'B', 'O']

export function SequenceInput({ value, onChange }: Props) {
  const parts = value ? value.split('-').filter(Boolean) : []

  function appendPart(part: string) {
    const next = parts.length ? `${value}-${part}` : part
    onChange(next)
  }

  function removeLast() {
    const idx = value.lastIndexOf('-')
    onChange(idx >= 0 ? value.slice(0, idx) : '')
  }

  return (
    <div>
      <div className="flex gap-1 flex-wrap mb-2">
        {PRESETS.map(p => (
          <button
            key={p}
            type="button"
            onClick={() => appendPart(p)}
            className="text-xs border border-gray-300 rounded px-2 py-1 hover:bg-gray-100 transition-colors"
          >
            {p}
          </button>
        ))}
        {parts.length > 0 && (
          <button
            type="button"
            onClick={removeLast}
            className="text-xs border border-red-200 text-red-400 rounded px-2 py-1 hover:bg-red-50 transition-colors"
          >
            ← 삭제
          </button>
        )}
      </div>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="I-V1-C-C"
        className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono outline-none focus:border-blue-400"
      />
      {parts.length > 0 && (
        <div className="flex gap-1 mt-1.5 flex-wrap">
          {parts.map((p, i) => (
            <span key={i} className="text-xs bg-gray-100 text-gray-600 rounded px-2 py-0.5">{p}</span>
          ))}
        </div>
      )}
    </div>
  )
}

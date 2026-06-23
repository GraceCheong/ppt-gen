import { CornerUpLeft } from 'lucide-react'

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
    <div className="flex flex-col gap-2.5">
      <div className="flex gap-1.5 flex-wrap">
        {PRESETS.map(p => (
          <button
            key={p}
            type="button"
            onClick={() => appendPart(p)}
            className="text-[10px] font-bold border border-neutral-200 text-neutral-600 bg-white rounded-lg px-2.5 py-1.5 hover:bg-neutral-50 hover:border-neutral-300 transition-all cursor-pointer select-none font-mono"
          >
            {p}
          </button>
        ))}
        {parts.length > 0 && (
          <button
            type="button"
            onClick={removeLast}
            className="text-[10px] font-bold border border-danger-200 bg-white text-danger-500 rounded-lg px-2.5 py-1.5 hover:bg-danger-50 hover:border-danger-300 transition-all cursor-pointer flex items-center gap-1 select-none"
          >
            <CornerUpLeft className="w-3 h-3" />
            <span>삭제</span>
          </button>
        )}
      </div>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="예: I-V1-C-C-B-C"
        className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs font-mono outline-none bg-neutral-50/50 hover:bg-neutral-50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all uppercase placeholder:normal-case placeholder:text-neutral-400 text-neutral-800"
      />
      {parts.length > 0 && (
        <div className="flex gap-1 flex-wrap items-center">
          {parts.map((p, i) => (
            <span 
              key={i} 
              className="text-[10px] font-bold bg-neutral-100 border border-neutral-200/50 text-neutral-600 font-mono rounded px-2 py-0.5 select-none"
            >
              {p}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}


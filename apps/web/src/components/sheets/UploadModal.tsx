import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { uploadSheet } from '../../api/sheets'
import type { UploadConflict } from '../../api/sheets'

export const BASE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

export function uiToKeyFields(base: string, suffix: string): { key_root: string; key_mode: string } {
  if (!base) return { key_root: '', key_mode: 'major' }
  const s = suffix.trim()
  const isMinor = /m$/i.test(s)
  const accidental = s.replace(/m$/i, '')
  return {
    key_root: base + accidental,
    key_mode: isMinor ? 'minor' : 'major',
  }
}

export function formatKey(root: string, mode: string) {
  return mode === 'minor' ? `${root}m` : root
}

interface PageEntry {
  id: string
  file: File | null
}

interface UploadModalProps {
  folderId: string | null
  initialTitle?: string
  initialSubtitle?: string
  initialBaseNote?: string
  initialSuffix?: string
  initialPageNumber?: number
  onClose: () => void
  onSuccess: () => void
}

export function UploadModal({
  folderId,
  initialTitle = '',
  initialSubtitle = '',
  initialBaseNote = 'C',
  initialSuffix = '',
  initialPageNumber = 1,
  onClose,
  onSuccess,
}: UploadModalProps) {
  const [pages, setPages] = useState<PageEntry[]>([{ id: crypto.randomUUID(), file: null }])
  const [title, setTitle] = useState(initialTitle)
  const [subtitle, setSubtitle] = useState(initialSubtitle)
  const [baseNote, setBaseNote] = useState(initialBaseNote)
  const [suffix, setSuffix] = useState(initialSuffix)
  const [conflict, setConflict] = useState<UploadConflict | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  const qc = useQueryClient()
  const fileInputRefs = useRef<Map<string, HTMLInputElement>>(new Map())

  function setPageFile(id: string, file: File | null) {
    setPages(prev => prev.map(p => p.id === id ? { ...p, file } : p))
  }

  function addPage() {
    setPages(prev => [...prev, { id: crypto.randomUUID(), file: null }])
  }

  function removePage(id: string) {
    setPages(prev => prev.filter(p => p.id !== id))
  }

  async function uploadAll(onConflict: 'error' | 'replace' | 'version' = 'error') {
    setError('')
    setUploading(true)
    const { key_root: keyRoot, key_mode: keyMode } = uiToKeyFields(baseNote, suffix)
    const isSingle = pages.length === 1

    for (let i = 0; i < pages.length; i++) {
      const pg = pages[i]
      if (!pg.file) continue
      const fd = new FormData()
      fd.append('file', pg.file)
      fd.append('title', title.trim())
      fd.append('subtitle', subtitle.trim())
      fd.append('key_root', keyRoot)
      fd.append('key_mode', keyMode)
      fd.append('page_number', String(initialPageNumber + i))
      fd.append('page_count', String(pages.length))
      if (folderId) fd.append('folder_id', folderId)
      // 단일 페이지: 충돌 모달 사용, 다중 페이지: version 자동 선택
      fd.append('on_conflict', isSingle ? onConflict : 'version')

      try {
        const result = await uploadSheet(fd)
        if (isSingle && (result as UploadConflict).conflict) {
          setConflict(result as UploadConflict)
          setUploading(false)
          return
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : '업로드 실패'
        setError(pages.length > 1 ? `${initialPageNumber + i}p: ${msg}` : msg)
        setUploading(false)
        return
      }
    }

    qc.invalidateQueries({ queryKey: ['sheets'] })
    qc.invalidateQueries({ queryKey: ['sheets-by-title'] })
    setUploading(false)
    onSuccess()
    onClose()
  }

  function handleSubmit() {
    if (!title.trim()) { setError('악보 제목을 입력하세요.'); return }
    if (pages.every(p => !p.file)) { setError('파일을 하나 이상 선택하세요.'); return }
    uploadAll('error')
  }

  if (conflict) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
        <div className="bg-white border border-neutral-200 rounded-2xl shadow-2xl w-full max-w-sm p-6 flex flex-col gap-4" onClick={e => e.stopPropagation()}>
          <h3 className="text-sm font-bold text-neutral-800">이미 같은 악보가 있습니다</h3>
          <p className="text-xs text-neutral-500">
            {conflict.title_key} / {formatKey(conflict.key_root, conflict.key_mode)} / {conflict.page_number}p
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => { setConflict(null); uploadAll('replace') }}
              className="flex-1 px-3 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer"
            >
              업데이트
            </button>
            <button
              onClick={() => { setConflict(null); uploadAll('version') }}
              className="flex-1 px-3 py-2 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer"
            >
              v2로 추가
            </button>
            <button
              onClick={() => setConflict(null)}
              className="px-3 py-2 text-xs font-semibold text-neutral-400 hover:text-neutral-600 cursor-pointer"
            >
              취소
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200 rounded-2xl shadow-2xl w-full max-w-md flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>

        {/* 헤더 */}
        <div className="p-4 border-b border-neutral-100 flex items-center justify-between shrink-0">
          <h3 className="text-sm font-bold text-neutral-800">악보 업로드</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 고정 필드 (제목, 부제, 키) */}
        <div className="px-4 pt-4 flex flex-col gap-3 shrink-0">
          <div>
            <label className="text-xs font-semibold text-neutral-600 mb-1 block">악보 제목</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="예: 주의 은혜라"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-neutral-600 mb-1 block">
              부제 <span className="text-neutral-400 font-normal">(선택)</span>
            </label>
            <input
              type="text"
              value={subtitle}
              onChange={e => setSubtitle(e.target.value)}
              placeholder="예: You Are My Everything"
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
            />
          </div>

          <div className="flex gap-2">
            <div className="w-24 shrink-0">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">코드</label>
              <select
                value={baseNote}
                onChange={e => setBaseNote(e.target.value)}
                className="w-full border border-neutral-200 rounded-lg px-2 py-2 text-xs outline-none focus:border-primary-400"
              >
                <option value="">없음</option>
                {BASE_NOTES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">변형 (#, b, m 등)</label>
              <input
                type="text"
                value={suffix}
                onChange={e => setSuffix(e.target.value)}
                placeholder="예: #m, b, #, bm"
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400 font-mono"
              />
            </div>
            <div className="shrink-0 pt-5">
              <span className="text-xs font-mono font-bold text-primary-600">
                {uiToKeyFields(baseNote, suffix).key_root || '—'}
                {uiToKeyFields(baseNote, suffix).key_mode === 'minor' ? 'm' : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 페이지 목록 (스크롤) */}
        <div className="px-4 pt-3 shrink-0">
          <label className="text-xs font-semibold text-neutral-600 mb-1.5 block">파일</label>
        </div>
        <div className="px-4 max-h-44 overflow-y-auto flex flex-col gap-1.5 shrink-0">
          {pages.map((pg, i) => (
            <div key={pg.id} className="flex items-center gap-2 bg-neutral-50 border border-neutral-200 rounded-lg px-2.5 py-1.5">
              {/* 파일 선택 버튼 */}
              <button
                type="button"
                onClick={() => fileInputRefs.current.get(pg.id)?.click()}
                className="text-xs text-left truncate flex-1 min-w-0 cursor-pointer"
              >
                {pg.file ? (
                  <span className="text-neutral-700 truncate block">{pg.file.name}</span>
                ) : (
                  <span className="text-neutral-400">파일 선택</span>
                )}
              </button>
              <input
                ref={el => {
                  if (el) fileInputRefs.current.set(pg.id, el)
                  else fileInputRefs.current.delete(pg.id)
                }}
                type="file"
                accept="application/pdf,image/*"
                className="hidden"
                onChange={e => setPageFile(pg.id, e.target.files?.[0] ?? null)}
              />

              {/* 페이지 번호 배지 */}
              <span className="text-[11px] font-mono font-bold text-primary-600 shrink-0 w-7 text-right">
                {initialPageNumber + i}p
              </span>

              {/* 삭제 버튼 (2개 이상일 때) */}
              {pages.length > 1 && (
                <button
                  type="button"
                  onClick={() => removePage(pg.id)}
                  className="text-neutral-300 hover:text-red-400 transition-colors cursor-pointer shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        {/* 페이지 추가 버튼 */}
        <div className="px-4 pt-2 shrink-0">
          <button
            type="button"
            onClick={addPage}
            className="flex items-center gap-1.5 text-xs font-semibold text-primary-600 hover:text-primary-700 cursor-pointer py-1 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            페이지 추가
          </button>
        </div>

        {/* 에러 + 푸터 */}
        <div className="px-4 pb-4 pt-3 flex flex-col gap-2 shrink-0">
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-neutral-500 hover:text-neutral-700 cursor-pointer"
            >
              취소
            </button>
            <button
              onClick={handleSubmit}
              disabled={uploading}
              className="px-4 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? '업로드 중…' : '업로드'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

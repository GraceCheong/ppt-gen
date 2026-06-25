import { useState, useMemo, useEffect, useRef, Fragment } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import {
  Search, Upload, FolderPlus, Trash2, Download, Folder, FileText, FileImage,
  RotateCcw, X, ChevronRight, Home, RefreshCw, ExternalLink,
  LayoutList, LayoutGrid, ChevronUp, ChevronDown, ChevronsUpDown,
  Pencil, Eye, ZoomIn, ZoomOut, ChevronLeft,
} from 'lucide-react'
import {
  searchSheets, listFolders, listTrash, uploadSheet, deleteSheet,
  restoreSheet, permanentDeleteSheet, deleteFolder,
  createFolder, downloadSheetFile,
  fetchSheetMe, fetchSyncStatus, triggerSync,
} from '../api/sheets'
import { getServerUrl } from '../api/serverConfig'
import type { SheetFile, SheetFolder, UploadConflict, SyncStatus } from '../api/sheets'

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp'])
function isImageExt(ext: string | null | undefined) { return IMAGE_EXTS.has(ext?.toLowerCase() ?? '') }
function isPdfExt(ext: string | null | undefined) { return ext?.toLowerCase() === 'pdf' }

const BASE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

// 'C#', minor → base='C', suffix='#m'
function parseKeyToUI(root: string, mode: string): { base: string; suffix: string } {
  if (!root) return { base: '', suffix: '' }
  const base = root[0].toUpperCase()
  const accidental = root.slice(1) // '#', 'b', or ''
  const suffix = accidental + (mode === 'minor' ? 'm' : '')
  return { base, suffix }
}

// base='C', suffix='#m' → root='C#', mode='minor'
function uiToKeyFields(base: string, suffix: string): { key_root: string; key_mode: string } {
  if (!base) return { key_root: '', key_mode: 'major' }
  const s = suffix.trim()
  const isMinor = /m$/i.test(s)
  const accidental = s.replace(/m$/i, '')
  return {
    key_root: base + accidental,
    key_mode: isMinor ? 'minor' : 'major',
  }
}

function formatKey(root: string, mode: string) {
  return mode === 'minor' ? `${root}m` : root
}

function formatDate(iso: string) {
  return iso ? new Date(iso).toLocaleDateString('ko-KR') : ''
}

// ── 업로드 모달 ────────────────────────────────────────────────────────────────

interface UploadModalProps {
  folderId: string | null
  onClose: () => void
  onSuccess: () => void
}

function UploadModal({ folderId, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [baseNote, setBaseNote] = useState('C')
  const [suffix, setSuffix] = useState('')
  const [pageNumber, setPageNumber] = useState(1)
  const [pageCount, setPageCount] = useState<number | ''>('')
  const [conflict, setConflict] = useState<UploadConflict | null>(null)
  const [error, setError] = useState('')

  const qc = useQueryClient()

  async function handleUpload(onConflict: 'error' | 'replace' | 'version' = 'error') {
    if (!file || !title.trim()) {
      setError('파일과 악보 제목을 입력하세요.')
      return
    }
    setError('')
    const { key_root: keyRoot, key_mode: keyMode } = uiToKeyFields(baseNote, suffix)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('title', title.trim())
    fd.append('key_root', keyRoot)
    fd.append('key_mode', keyMode)
    fd.append('page_number', String(pageNumber))
    if (pageCount !== '') fd.append('page_count', String(pageCount))
    if (folderId) fd.append('folder_id', folderId)
    fd.append('on_conflict', onConflict)

    try {
      const result = await uploadSheet(fd)
      if ((result as UploadConflict).conflict) {
        setConflict(result as UploadConflict)
        return
      }
      qc.invalidateQueries({ queryKey: ['sheets'] })
      onSuccess()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '업로드 실패')
    }
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
              onClick={() => { setConflict(null); handleUpload('replace') }}
              className="flex-1 px-3 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer"
            >
              업데이트
            </button>
            <button
              onClick={() => { setConflict(null); handleUpload('version') }}
              className="flex-1 px-3 py-2 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer"
            >
              v{/* existing version + 1 */}2로 추가
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
        <div className="p-4 border-b border-neutral-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-neutral-800">악보 업로드</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-4 flex flex-col gap-3">
          <div>
            <label className="text-xs font-semibold text-neutral-600 mb-1 block">파일</label>
            <input
              type="file"
              accept="application/pdf,image/*"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-xs text-neutral-700 file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 cursor-pointer"
            />
          </div>

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
                {uiToKeyFields(baseNote, suffix).key_mode === 'minor' ? ' m' : ''}
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">Page Number</label>
              <input
                type="number"
                min={1}
                value={pageNumber}
                onChange={e => setPageNumber(Number(e.target.value))}
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">Page Count</label>
              <input
                type="number"
                min={1}
                value={pageCount}
                onChange={e => setPageCount(e.target.value === '' ? '' : Number(e.target.value))}
                placeholder="선택"
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
              />
            </div>
          </div>

          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>

        <div className="px-4 pb-4 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-xs font-semibold text-neutral-500 hover:text-neutral-700 cursor-pointer">취소</button>
          <button
            onClick={() => handleUpload('error')}
            className="px-4 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer"
          >
            업로드
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 악보 수정 모달 ────────────────────────────────────────────────────────────

interface EditSheetModalProps {
  file: SheetFile
  onClose: () => void
  onSuccess: () => void
}

function EditSheetModal({ file, onClose, onSuccess }: EditSheetModalProps) {
  const [title, setTitle] = useState(file.display_title)
  const { base: initBase, suffix: initSuffix } = parseKeyToUI(file.key_root, file.key_mode)
  const [baseNote, setBaseNote] = useState(initBase)
  const [suffix, setSuffix] = useState(initSuffix)
  const [pageNumber, setPageNumber] = useState(file.page_number)
  const [pageCount, setPageCount] = useState<number | ''>(file.page_count ?? '')
  const [isEventOnly, setIsEventOnly] = useState(file.is_event_only ?? false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const qc = useQueryClient()

  async function handleSave() {
    if (!title.trim()) { setError('제목을 입력하세요.'); return }
    setSaving(true); setError('')
    const { key_root: keyRoot, key_mode: keyMode } = uiToKeyFields(baseNote, suffix)
    try {
      const res = await fetch(`/api/sheets/${file.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          display_title: title.trim(),
          key_root: keyRoot,
          key_mode: keyMode,
          page_number: pageNumber,
          page_count: pageCount === '' ? null : pageCount,
          is_event_only: isEventOnly,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `[${res.status}]`)
      }
      qc.invalidateQueries({ queryKey: ['sheets'] })
      onSuccess()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '수정 실패')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200 rounded-2xl shadow-2xl w-full max-w-md flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-neutral-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-neutral-800">악보 정보 수정</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 flex flex-col gap-3">
          <div>
            <label className="text-xs font-semibold text-neutral-600 mb-1 block">악보 제목</label>
            <input
              autoFocus
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
            />
          </div>
          <div className="flex gap-2">
            <div className="w-24 shrink-0">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">코드</label>
              <select value={baseNote} onChange={e => setBaseNote(e.target.value)}
                className="w-full border border-neutral-200 rounded-lg px-2 py-2 text-xs outline-none focus:border-primary-400">
                <option value="">없음</option>
                {BASE_NOTES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">변형 (#, b, m 등)</label>
              <input
                type="text" value={suffix} onChange={e => setSuffix(e.target.value)}
                placeholder="예: #m, b, #, bm"
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400 font-mono"
              />
            </div>
            <div className="shrink-0 pt-5">
              <span className="text-xs font-mono font-bold text-primary-600">
                {uiToKeyFields(baseNote, suffix).key_root || '—'}
                {uiToKeyFields(baseNote, suffix).key_mode === 'minor' ? ' m' : ''}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">Page Number</label>
              <input type="number" min={1} value={pageNumber} onChange={e => setPageNumber(Number(e.target.value))}
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-neutral-600 mb-1 block">Page Count</label>
              <input type="number" min={1} value={pageCount}
                onChange={e => setPageCount(e.target.value === '' ? '' : Number(e.target.value))}
                placeholder="선택"
                className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400" />
            </div>
          </div>
          <label className="flex items-center gap-2.5 px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg cursor-pointer hover:bg-amber-100 transition-colors">
            <input
              type="checkbox"
              checked={isEventOnly}
              onChange={e => setIsEventOnly(e.target.checked)}
              className="w-3.5 h-3.5 accent-amber-500 cursor-pointer"
            />
            <span className="text-xs font-semibold text-amber-800">이벤트 전용 악보</span>
            <span className="text-[10px] text-amber-600 ml-auto">특별 행사·절기용</span>
          </label>

          <div className="bg-neutral-50 rounded-lg px-3 py-2 text-[10px] text-neutral-400 space-y-0.5">
            <p>파일: {file.original_filename}</p>
            <p>업로더: {file.uploaded_by} · {formatDate(file.uploaded_at)}</p>
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
        <div className="px-4 pb-4 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-xs font-semibold text-neutral-500 hover:text-neutral-700 cursor-pointer">취소</button>
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors cursor-pointer">
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 미리보기 모달 ─────────────────────────────────────────────────────────────

interface PreviewModalProps {
  file: SheetFile
  versions: SheetFile[]  // 같은 song_title_key + key + page 의 모든 버전 (version 오름차순)
  onClose: () => void
  onEdit: () => void
}

function PreviewModal({ file, versions, onClose, onEdit }: PreviewModalProps) {
  const [idx, setIdx] = useState(() => {
    const i = versions.findIndex(v => v.id === file.id)
    return i >= 0 ? i : versions.length - 1
  })
  const current = versions[idx] ?? file
  const previewUrl = `/api/sheets/${current.id}/preview`
  const isPdf = current.extension === 'pdf'
  const isImage = isImageExt(current.extension)
  const hasVersions = versions.length > 1

  // 키 기준 그룹핑 (네비게이션 바용)
  const keyMap = new Map<string, { file: SheetFile; globalIdx: number }[]>()
  const keyOrder: string[] = []
  versions.forEach((v, gi) => {
    const k = v.key_root ? formatKey(v.key_root, v.key_mode) : '—'
    if (!keyMap.has(k)) { keyMap.set(k, []); keyOrder.push(k) }
    keyMap.get(k)!.push({ file: v, globalIdx: gi })
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/60 backdrop-blur-sm px-4 py-6" onClick={onClose}>
      {/* 고정 크기: 뷰포트의 90% 높이 */}
      <div className="bg-white border border-neutral-200 rounded-2xl shadow-2xl w-full max-w-3xl h-[90vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="p-4 border-b border-neutral-100 flex items-center justify-between shrink-0 gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-4 h-4 text-neutral-400 shrink-0" />
            <span className="text-sm font-bold text-neutral-800 truncate">{current.display_title}</span>
            {current.key_root && (
              <span className="font-mono text-[10px] bg-primary-50 text-primary-600 px-1.5 py-0.5 rounded font-semibold shrink-0">
                {formatKey(current.key_root, current.key_mode)}
              </span>
            )}
            {current.page_number > 1 && (
              <span className="text-[10px] text-neutral-400 shrink-0">{current.page_number}p</span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={onEdit}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer">
              <Pencil className="w-3 h-3" />수정
            </button>
            <button onClick={() => downloadSheetFile(current.id)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer">
              <Download className="w-3 h-3" />다운로드
            </button>
            <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer p-1">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 키 + 버전 네비게이션 바 (화살표 없이 pill만) */}
        {hasVersions && (
          <div className="px-3 py-2 border-b border-neutral-100 flex items-center gap-1.5 shrink-0 bg-neutral-50 flex-wrap">
            {keyOrder.map(k => {
              const items = keyMap.get(k)!
              return (
                <div key={k} className="flex items-center gap-0.5">
                  {items.map(({ file: v, globalIdx: gi }, vi) => {
                    const label = items.length > 1 ? `${k} v${vi + 1}` : k
                    return (
                      <button
                        key={v.id}
                        onClick={() => setIdx(gi)}
                        className={`px-2 py-0.5 rounded text-[11px] font-semibold font-mono transition-colors cursor-pointer ${
                          gi === idx ? 'bg-primary-600 text-white' : 'bg-neutral-200 text-neutral-600 hover:bg-neutral-300'
                        }`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>
        )}

        {/* 미리보기 — 양쪽 큰 화살표 오버레이 포함 */}
        <div className="relative flex-1 overflow-auto bg-neutral-50">
          {/* 왼쪽 화살표 */}
          {hasVersions && idx > 0 && (
            <button
              onClick={() => setIdx(i => i - 1)}
              className="absolute left-3 top-1/2 -translate-y-1/2 z-10 w-12 h-12 flex items-center justify-center rounded-full bg-black/40 text-white hover:bg-black/60 transition-colors cursor-pointer shadow-lg"
            >
              <ChevronLeft className="w-7 h-7" />
            </button>
          )}
          {/* 오른쪽 화살표 */}
          {hasVersions && idx < versions.length - 1 && (
            <button
              onClick={() => setIdx(i => i + 1)}
              className="absolute right-3 top-1/2 -translate-y-1/2 z-10 w-12 h-12 flex items-center justify-center rounded-full bg-black/40 text-white hover:bg-black/60 transition-colors cursor-pointer shadow-lg"
            >
              <ChevronRight className="w-7 h-7" />
            </button>
          )}
          {isPdf ? (
            <iframe src={previewUrl} className="w-full h-full" title={current.display_title} />
          ) : isImage ? (
            <img src={previewUrl} alt={current.display_title} className="w-full h-full object-contain p-4" />
          ) : (
            <div className="flex items-center justify-center h-full text-neutral-400 text-sm">
              이 형식은 미리보기를 지원하지 않습니다
            </div>
          )}
        </div>
        <div className="px-4 py-2 border-t border-neutral-100 flex gap-3 text-[10px] text-neutral-400 shrink-0">
          <span>파일: {current.original_filename}</span>
          <span>크기: {(current.size_bytes / 1024).toFixed(0)}KB</span>
          <span>업로더: {current.uploaded_by}</span>
          <span>{formatDate(current.uploaded_at)}</span>
        </div>
      </div>
    </div>
  )
}

// ── 새 폴더 모달 ──────────────────────────────────────────────────────────────

interface NewFolderModalProps {
  parentId: string | null
  onClose: () => void
  onSuccess: () => void
}

function NewFolderModal({ parentId, onClose, onSuccess }: NewFolderModalProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  async function handleCreate() {
    if (!name.trim()) { setError('폴더 이름을 입력하세요.'); return }
    try {
      await createFolder(name.trim(), parentId)
      qc.invalidateQueries({ queryKey: ['sheets-folders'] })
      onSuccess()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '폴더 생성 실패')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 backdrop-blur-xs px-4" onClick={onClose}>
      <div className="bg-white border border-neutral-200 rounded-2xl shadow-2xl w-full max-w-sm p-5 flex flex-col gap-3" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-bold text-neutral-800">새 폴더</h3>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleCreate()}
          placeholder="폴더 이름"
          className="border border-neutral-200 rounded-lg px-3 py-2 text-xs outline-none focus:border-primary-400"
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 text-xs font-semibold text-neutral-500 hover:text-neutral-700 cursor-pointer">취소</button>
          <button onClick={handleCreate} className="px-3 py-2 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 cursor-pointer">만들기</button>
        </div>
      </div>
    </div>
  )
}

// ── 정렬 헤더 셀 ───────────────────────────────────────────────────────────────

interface SortThProps {
  label: string
  colKey: SortKey
  current: SortKey
  dir: SortDir
  onSort: (k: SortKey) => void
  className?: string
}

function SortTh({ label, colKey, current, dir, onSort, className }: SortThProps) {
  const active = current === colKey
  return (
    <th className={className}>
      <button
        onClick={() => onSort(colKey)}
        className="flex items-center gap-1 hover:text-neutral-700 transition-colors cursor-pointer select-none"
      >
        {label}
        {active
          ? dir === 'asc'
            ? <ChevronUp className="w-3 h-3 text-primary-500" />
            : <ChevronDown className="w-3 h-3 text-primary-500" />
          : <ChevronsUpDown className="w-3 h-3 text-neutral-300" />
        }
      </button>
    </th>
  )
}

// ── 정렬 ───────────────────────────────────────────────────────────────────────

type SortKey = 'display_title' | 'key_root' | 'page_number' | 'version' | 'extension' | 'uploaded_at' | 'uploaded_by'
type SortDir = 'asc' | 'desc'

function sortFiles(files: SheetFile[], key: SortKey, dir: SortDir): SheetFile[] {
  return [...files].sort((a, b) => {
    let av: string | number = a[key] ?? ''
    let bv: string | number = b[key] ?? ''
    if (key === 'page_number' || key === 'version') {
      av = Number(av); bv = Number(bv)
    } else {
      av = String(av).toLowerCase(); bv = String(bv).toLowerCase()
    }
    if (av < bv) return dir === 'asc' ? -1 : 1
    if (av > bv) return dir === 'asc' ? 1 : -1
    return 0
  })
}

// ── 메인 페이지 ────────────────────────────────────────────────────────────────

export function DrivePage() {
  const { mode } = useAuthStore()
  const isUser = mode === 'user'

  const [q, setQ] = useState('')
  const [filterKey, setFilterKey] = useState('')
  const [filterMode, setFilterMode] = useState('')
  const [filterExt, setFilterExt] = useState('')
  const [filterEventOnly, setFilterEventOnly] = useState(false)
  const [filterHasKey, setFilterHasKey] = useState<'all' | 'yes' | 'no'>('all')
  const [showFilters, setShowFilters] = useState(false)
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
  const [breadcrumb, setBreadcrumb] = useState<{ id: string | null; name: string }[]>([
    { id: null, name: '홈' },
  ])
  const [showTrash, setShowTrash] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list')
  const [sortKey, setSortKey] = useState<SortKey>('display_title')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [editingFile, setEditingFile] = useState<SheetFile | null>(null)
  const [previewFile, setPreviewFile] = useState<SheetFile | null>(null)
  const [previewVersions, setPreviewVersions] = useState<SheetFile[]>([])
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [gridSize, setGridSize] = useState(160)
  const [serverUrl, setServerUrl] = useState('')
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => { getServerUrl().then(setServerUrl) }, [])


  function toggleGroup(key: string) {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function openPreview(file: SheetFile, allGroupFiles?: SheetFile[]) {
    // 같은 곡(song_title_key) 전체를 키→페이지→버전 순으로 정렬
    const all = (allGroupFiles ?? files.filter(f => f.song_title_key === file.song_title_key))
      .slice()
      .sort((a, b) => {
        const ka = (a.key_root ?? '').toLowerCase()
        const kb = (b.key_root ?? '').toLowerCase()
        if (ka !== kb) return ka.localeCompare(kb)
        if (a.key_mode !== b.key_mode) return a.key_mode === 'major' ? -1 : 1
        if (a.page_number !== b.page_number) return a.page_number - b.page_number
        return a.version - b.version
      })
    setPreviewVersions(all.length > 0 ? all : [file])
    setPreviewFile(file)
  }
  const qc = useQueryClient()

  function handleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const { data: meData } = useQuery({
    queryKey: ['sheet-me'],
    queryFn: fetchSheetMe,
    enabled: isUser,
  })
  const isSuper = meData?.is_super ?? false

  const { data: syncStatus } = useQuery<SyncStatus>({
    queryKey: ['sheet-sync-status'],
    queryFn: fetchSyncStatus,
    enabled: isUser,
    staleTime: 60_000,
  })

  async function handleSync() {
    if (syncing) return
    setSyncing(true)
    try {
      await triggerSync()
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['sheets'] })
        qc.invalidateQueries({ queryKey: ['sheets-folders'] })
      }, 3000) // 백그라운드 동기화 완료 대기 후 갱신
    } catch (e) {
      alert(e instanceof Error ? e.message : '동기화 실패')
    } finally {
      setTimeout(() => setSyncing(false), 3000)
    }
  }

  const { data: folders = [] } = useQuery({
    queryKey: ['sheets-folders', currentFolderId],
    queryFn: () => listFolders(currentFolderId),
    enabled: isUser && !showTrash,
  })

  const { data: files = [] } = useQuery({
    queryKey: ['sheets', q, currentFolderId, filterKey, filterMode, filterExt, filterEventOnly, filterHasKey],
    queryFn: () => searchSheets({
      q,
      folder_id: currentFolderId ?? undefined,
      key_root: filterKey || undefined,
      key_mode: filterMode || undefined,
      extension: filterExt || undefined,
      is_event_only: filterEventOnly ? true : undefined,
      has_key: filterHasKey === 'yes' ? true : filterHasKey === 'no' ? false : undefined,
    }),
    enabled: isUser && !showTrash,
  })

  const { data: trashItems = [] } = useQuery({
    queryKey: ['sheets-trash', q],
    queryFn: () => listTrash(q),
    enabled: isUser && showTrash,
  })

  const sortedFiles = useMemo(() => sortFiles(files, sortKey, sortDir), [files, sortKey, sortDir])

  // song_title_key 기준 그룹핑 → 그 안에서 normalized_title+key+page 기준 서브그룹
  const groupedFiles = useMemo(() => {
    const order: string[] = []
    const map = new Map<string, SheetFile[]>()
    for (const f of sortedFiles) {
      const k = f.song_title_key
      if (!map.has(k)) { map.set(k, []); order.push(k) }
      map.get(k)!.push(f)
    }
    return order.map(k => {
      const allFiles = map.get(k)!
      const subMap = new Map<string, SheetFile[]>()
      const subOrder: string[] = []
      for (const f of allFiles) {
        const sk = `${f.normalized_title}|${f.key_root}|${f.key_mode}|${f.page_number}`
        if (!subMap.has(sk)) { subMap.set(sk, []); subOrder.push(sk) }
        subMap.get(sk)!.push(f)
      }
      const subGroups = subOrder.map(sk => {
        const vers = subMap.get(sk)!.sort((a, b) => a.version - b.version)
        return { subKey: sk, versions: vers, latest: vers[vers.length - 1] }
      })
      return { key: k, files: allFiles, subGroups }
    })
  }, [sortedFiles])

  if (mode === 'loading') return null
  if (!isUser) return <Navigate to="/app" replace />

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSheet(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sheets'] }),
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => restoreSheet(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sheets'] })
      qc.invalidateQueries({ queryKey: ['sheets-trash'] })
    },
  })

  const purgeFileMutation = useMutation({
    mutationFn: (id: string) => permanentDeleteSheet(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sheets-trash'] }),
  })

  const deleteFolderMutation = useMutation({
    mutationFn: (id: string) => deleteFolder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sheets-folders'] }),
  })


  function navigateToFolder(folder: SheetFolder) {
    setCurrentFolderId(folder.id)
    setBreadcrumb(prev => [...prev, { id: folder.id, name: folder.name }])
  }

  function navigateToBreadcrumb(index: number) {
    const item = breadcrumb[index]
    setCurrentFolderId(item.id)
    setBreadcrumb(prev => prev.slice(0, index + 1))
  }

  return (
    <div className="h-full flex flex-col p-5 gap-4 overflow-y-auto">
      {/* 상단 툴바 */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-0 bg-white border border-neutral-200 rounded-xl px-3 py-2">
          <Search className="w-4 h-4 text-neutral-400 shrink-0" />
          <input
            type="text"
            placeholder="악보 검색..."
            value={q}
            onChange={e => setQ(e.target.value)}
            className="flex-1 text-xs outline-none bg-transparent text-neutral-800 placeholder:text-neutral-400"
          />
          {(filterKey || filterMode || filterExt || filterEventOnly || filterHasKey !== 'all') && (
            <span className="px-1.5 py-0.5 rounded-md bg-primary-100 text-primary-700 text-xs font-semibold">
              필터 활성
            </span>
          )}
        </div>
        <button
          onClick={() => setShowFilters(f => !f)}
          title="검색 필터"
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl transition-colors cursor-pointer ${showFilters ? 'bg-primary-100 text-primary-700' : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'}`}
        >
          <Search className="w-3.5 h-3.5" />
          <span>필터</span>
        </button>
        {!showTrash && (
          <>
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>업로드</span>
            </button>
            <button
              onClick={() => setShowNewFolder(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-xl hover:bg-neutral-200 transition-colors cursor-pointer"
            >
              <FolderPlus className="w-3.5 h-3.5" />
              <span>새 폴더</span>
            </button>
          </>
        )}
        <button
          onClick={() => setShowTrash(t => !t)}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl transition-colors cursor-pointer ${
            showTrash
              ? 'bg-danger-100 text-danger-700'
              : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
          }`}
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>휴지통</span>
        </button>

        {/* Google Drive 동기화 */}
        {syncStatus?.enabled && syncStatus?.configured && (
          <button
            onClick={handleSync}
            disabled={syncing}
            title="Google Drive와 동기화"
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-xl hover:bg-neutral-200 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? '동기화 중...' : 'Drive 동기화'}</span>
          </button>
        )}
        {syncStatus?.enabled && syncStatus?.folder_id && (
          <a
            href={`https://drive.google.com/drive/folders/${syncStatus.folder_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-2 text-xs text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer"
            title="Google Drive 폴더 열기"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}

        {/* 모두 펼치기/접기 */}
        {!showTrash && groupedFiles.some(g => g.subGroups.length > 1) && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setExpandedGroups(new Set(groupedFiles.filter(g => g.subGroups.length > 1).map(g => g.key)))}
              className="text-xs text-neutral-500 hover:text-neutral-700 px-2 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors cursor-pointer"
            >
              모두 펼치기
            </button>
            <button
              onClick={() => setExpandedGroups(new Set())}
              className="text-xs text-neutral-500 hover:text-neutral-700 px-2 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors cursor-pointer"
            >
              모두 접기
            </button>
          </div>
        )}

        {/* 그리드 줌 슬라이더 */}
        {!showTrash && viewMode === 'grid' && (
          <div className="flex items-center gap-2">
            <ZoomOut className="w-3.5 h-3.5 text-neutral-400" />
            <input
              type="range" min={80} max={300} step={20} value={gridSize}
              onChange={e => setGridSize(Number(e.target.value))}
              className="w-24 h-1 accent-primary-500 cursor-pointer"
            />
            <ZoomIn className="w-3.5 h-3.5 text-neutral-400" />
          </div>
        )}

        {/* 뷰 모드 토글 */}
        {!showTrash && (
          <div className="flex items-center bg-neutral-100 rounded-xl p-0.5">
            <button
              onClick={() => setViewMode('list')}
              title="목록 뷰"
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${viewMode === 'list' ? 'bg-white shadow-sm text-neutral-700' : 'text-neutral-400 hover:text-neutral-600'}`}
            >
              <LayoutList className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              title="그리드 뷰"
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${viewMode === 'grid' ? 'bg-white shadow-sm text-neutral-700' : 'text-neutral-400 hover:text-neutral-600'}`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* 검색 필터 패널 */}
      {showFilters && !showTrash && (
        <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-3 flex flex-wrap gap-3 items-end text-xs">
          <div className="flex flex-col gap-1">
            <label className="text-neutral-500 font-medium">키 (조)</label>
            <select
              value={filterKey}
              onChange={e => setFilterKey(e.target.value)}
              className="border border-neutral-200 rounded-lg px-2 py-1.5 bg-white text-neutral-800 outline-none"
            >
              <option value="">전체</option>
              {BASE_NOTES.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-neutral-500 font-medium">장/단조</label>
            <select
              value={filterMode}
              onChange={e => setFilterMode(e.target.value)}
              className="border border-neutral-200 rounded-lg px-2 py-1.5 bg-white text-neutral-800 outline-none"
            >
              <option value="">전체</option>
              <option value="major">장조</option>
              <option value="minor">단조</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-neutral-500 font-medium">형식</label>
            <select
              value={filterExt}
              onChange={e => setFilterExt(e.target.value)}
              className="border border-neutral-200 rounded-lg px-2 py-1.5 bg-white text-neutral-800 outline-none"
            >
              <option value="">전체</option>
              <option value="pdf">PDF</option>
              <option value="png">PNG</option>
              <option value="jpg">JPG</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-neutral-500 font-medium">키 등록</label>
            <select
              value={filterHasKey}
              onChange={e => setFilterHasKey(e.target.value as 'all' | 'yes' | 'no')}
              className="border border-neutral-200 rounded-lg px-2 py-1.5 bg-white text-neutral-800 outline-none"
            >
              <option value="all">전체</option>
              <option value="yes">키 있음</option>
              <option value="no">키 없음</option>
            </select>
          </div>
          <label className="flex items-center gap-2 cursor-pointer select-none pb-1.5">
            <input
              type="checkbox"
              checked={filterEventOnly}
              onChange={e => setFilterEventOnly(e.target.checked)}
              className="w-3.5 h-3.5 accent-amber-500"
            />
            <span className="text-neutral-700">이벤트 전용만</span>
          </label>
          {(filterKey || filterMode || filterExt || filterEventOnly || filterHasKey !== 'all') && (
            <button
              onClick={() => { setFilterKey(''); setFilterMode(''); setFilterExt(''); setFilterEventOnly(false); setFilterHasKey('all') }}
              className="text-xs text-danger-600 hover:text-danger-800 font-medium underline pb-1.5 cursor-pointer"
            >
              필터 초기화
            </button>
          )}
        </div>
      )}

      {/* Breadcrumb */}
      {!showTrash && (
        <div className="flex items-center gap-1 text-xs text-neutral-500 flex-wrap">
          {breadcrumb.map((item, idx) => (
            <span key={idx} className="flex items-center gap-1">
              {idx > 0 && <ChevronRight className="w-3 h-3 text-neutral-300" />}
              <button
                onClick={() => navigateToBreadcrumb(idx)}
                className={`flex items-center gap-1 hover:text-primary-600 transition-colors cursor-pointer ${
                  idx === breadcrumb.length - 1 ? 'text-neutral-800 font-semibold' : ''
                }`}
              >
                {idx === 0 && <Home className="w-3 h-3" />}
                <span>{item.name}</span>
                {idx === breadcrumb.length - 1 && (folders.length + files.length) > 0 && (
                  <span className="text-neutral-400 font-normal">
                    ({folders.length > 0 ? `폴더 ${folders.length} · ` : ''}파일 {files.length})
                  </span>
                )}
              </button>
            </span>
          ))}
        </div>
      )}

      {/* 폴더/파일 목록 — 목록 뷰 */}
      {!showTrash && viewMode === 'list' && (
        <div className="bg-white border border-neutral-200 rounded-2xl overflow-hidden flex flex-col">
          <div className="overflow-x-auto overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/60 text-neutral-500 font-semibold">
                <th className="px-2 py-3 w-6"></th>
                <SortTh label="제목" colKey="display_title" current={sortKey} dir={sortDir} onSort={handleSort} className="px-4 py-3 text-left" />
                <SortTh label="Key" colKey="key_root" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden sm:table-cell" />
                <SortTh label="Page" colKey="page_number" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden md:table-cell" />
                <SortTh label="Ver" colKey="version" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden md:table-cell" />
                <SortTh label="형식" colKey="extension" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden lg:table-cell" />
                <SortTh label="업로드일" colKey="uploaded_at" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden lg:table-cell" />
                <SortTh label="업로더" colKey="uploaded_by" current={sortKey} dir={sortDir} onSort={handleSort} className="px-3 py-3 text-left hidden lg:table-cell" />
                <th className="px-3 py-3 text-right">액션</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {folders.map(folder => (
                <tr key={folder.id} className="hover:bg-neutral-50/60 transition-colors">
                  <td className="px-2 py-3 w-6"></td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigateToFolder(folder)}
                      className="flex items-center gap-2 text-neutral-700 hover:text-primary-600 font-semibold cursor-pointer"
                    >
                      <Folder className="w-4 h-4 text-yellow-500 shrink-0" />
                      {folder.name}
                    </button>
                  </td>
                  <td className="px-3 py-3 hidden sm:table-cell text-neutral-400">—</td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-400">—</td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-400">—</td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">폴더</td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">{formatDate(folder.created_at)}</td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">{folder.created_by}</td>
                  <td className="px-3 py-3 text-right">
                    <button
                      onClick={() => deleteFolderMutation.mutate(folder.id)}
                      className="text-neutral-400 hover:text-danger-500 transition-colors cursor-pointer p-1"
                      title="휴지통으로 이동"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {groupedFiles.map(({ key: groupKey, files: groupAllFiles, subGroups }) => {
                const isExpanded = expandedGroups.has(groupKey)
                // 여러 독립 배열(다른 제목/키/페이지)이 있을 때만 그룹 토글 표시
                const hasMultiple = subGroups.length > 1
                const rep = subGroups[0].latest
                const repVersions = subGroups[0].versions
                const keys = [...new Set(subGroups.map(sg => sg.latest.key_root ? formatKey(sg.latest.key_root, sg.latest.key_mode) : ''))]
                return (
                <Fragment key={groupKey}>
                {/* 그룹 대표 행 */}
                <tr key={groupKey} className="hover:bg-neutral-50/60 transition-colors border-b border-neutral-50">
                  <td className="px-2 py-3 w-6">
                    {hasMultiple ? (
                      <button
                        onClick={() => toggleGroup(groupKey)}
                        className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer p-0.5"
                        title={isExpanded ? '접기' : '펼치기'}
                      >
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    ) : <span className="w-3.5 h-3.5 block" />}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {hasMultiple ? (
                        <button
                          onClick={() => toggleGroup(groupKey)}
                          className="flex items-center gap-2 text-left hover:text-primary-600 transition-colors cursor-pointer group"
                        >
                          <FileText className="w-4 h-4 text-neutral-400 shrink-0 group-hover:text-primary-400" />
                          <span className="text-neutral-800 font-semibold">{rep.display_title.replace(/ (피아노|보컬|드럼|단선|Intro|반주용|피아노\+보컬|보컬\+피아노|피아노\+드럼).*/i, '').trim() || rep.display_title}</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => openPreview(rep, groupAllFiles)}
                          className="flex items-center gap-2 text-left hover:text-primary-600 transition-colors cursor-pointer group"
                        >
                          <FileText className="w-4 h-4 text-neutral-400 shrink-0 group-hover:text-primary-400" />
                          <span className="text-neutral-800 font-medium">{rep.display_title}</span>
                        </button>
                      )}
                      {rep.is_event_only && <span className="shrink-0 text-[10px] font-semibold bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">이벤트</span>}
                      {hasMultiple && (
                        <span className="text-[10px] text-neutral-400 font-medium">{subGroups.length}종</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3 hidden sm:table-cell">
                    <div className="flex gap-1 flex-wrap">
                      {keys.map(k => k ? (
                        <span key={k} className="font-mono text-[10px] bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded">{k}</span>
                      ) : (
                        <span key="none" className="text-neutral-300 text-[10px]">—</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-600">
                    {!hasMultiple ? `${rep.page_number}p` : ''}
                  </td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-500">
                    {!hasMultiple && repVersions.length > 1 && (
                      <span className="text-[10px] font-mono bg-neutral-100 px-1.5 py-0.5 rounded">v{rep.version} ({repVersions.length})</span>
                    )}
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-500 uppercase text-[10px]">
                    {!hasMultiple ? rep.extension : ''}
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">
                    {!hasMultiple ? formatDate(rep.uploaded_at) : ''}
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400 truncate max-w-[80px]">
                    {!hasMultiple ? rep.uploaded_by : ''}
                  </td>
                  <td className="px-3 py-3 text-right">
                    {!hasMultiple && (
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => openPreview(rep, groupAllFiles)} className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer p-1" title="미리보기"><Eye className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setEditingFile(rep)} className="text-neutral-400 hover:text-primary-500 transition-colors cursor-pointer p-1" title="수정"><Pencil className="w-3.5 h-3.5" /></button>
                        <button onClick={() => downloadSheetFile(rep.id)} className="text-neutral-400 hover:text-primary-500 transition-colors cursor-pointer p-1" title="다운로드"><Download className="w-3.5 h-3.5" /></button>
                        <button onClick={() => deleteMutation.mutate(rep.id)} className="text-neutral-400 hover:text-danger-500 transition-colors cursor-pointer p-1" title="휴지통으로 이동"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    )}
                  </td>
                </tr>
                {/* 펼친 경우: 서브그룹별 최신 버전 1행씩 */}
                {isExpanded && subGroups.map(sg => (
                  <tr key={sg.subKey} className="bg-primary-50/30 hover:bg-primary-50/60 transition-colors text-xs">
                    <td></td>
                    <td className="px-4 py-2 pl-10">
                      <button
                        onClick={() => openPreview(sg.latest, groupAllFiles)}
                        className="flex items-center gap-1.5 text-neutral-700 hover:text-primary-600 transition-colors cursor-pointer"
                      >
                        <FileText className="w-3.5 h-3.5 text-neutral-300 shrink-0" />
                        <span className="truncate">{sg.latest.display_title}</span>
                      </button>
                    </td>
                    <td className="px-3 py-2 hidden sm:table-cell">
                      {sg.latest.key_root ? (
                        <span className="font-mono text-[10px] bg-white border border-neutral-200 text-neutral-600 px-1.5 py-0.5 rounded">
                          {formatKey(sg.latest.key_root, sg.latest.key_mode)}
                        </span>
                      ) : <span className="text-neutral-300 text-[10px]">—</span>}
                    </td>
                    <td className="px-3 py-2 hidden md:table-cell text-neutral-500">{sg.latest.page_number}p</td>
                    <td className="px-3 py-2 hidden md:table-cell text-neutral-400">
                      {sg.versions.length > 1 ? (
                        <span className="text-[10px] font-mono bg-neutral-100 px-1 py-0.5 rounded">v{sg.latest.version} ({sg.versions.length})</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 hidden lg:table-cell text-neutral-400 uppercase text-[10px]">{sg.latest.extension}</td>
                    <td className="px-3 py-2 hidden lg:table-cell text-neutral-400">{formatDate(sg.latest.uploaded_at)}</td>
                    <td className="px-3 py-2 hidden lg:table-cell text-neutral-400 truncate max-w-[80px]">{sg.latest.uploaded_by}</td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => openPreview(sg.latest, groupAllFiles)} className="text-neutral-400 hover:text-neutral-600 cursor-pointer p-1" title="미리보기"><Eye className="w-3 h-3" /></button>
                        <button onClick={() => setEditingFile(sg.latest)} className="text-neutral-400 hover:text-primary-500 cursor-pointer p-1" title="수정"><Pencil className="w-3 h-3" /></button>
                        <button onClick={() => downloadSheetFile(sg.latest.id)} className="text-neutral-400 hover:text-primary-500 cursor-pointer p-1" title="다운로드"><Download className="w-3 h-3" /></button>
                        <button onClick={() => deleteMutation.mutate(sg.latest.id)} className="text-neutral-400 hover:text-danger-500 cursor-pointer p-1" title="휴지통으로 이동"><Trash2 className="w-3 h-3" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                </Fragment>
              )})}
              {folders.length === 0 && files.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-neutral-400 text-xs">
                    악보가 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* 폴더/파일 목록 — 그리드 뷰 */}
      {!showTrash && viewMode === 'grid' && (
        <div ref={gridRef} className="flex flex-col gap-3">
          {/* 폴더 행 */}
          {folders.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${gridSize}px, 1fr))`, gap: '0.75rem' }}>
              {folders.map(folder => (
                <button
                  key={folder.id}
                  onClick={() => navigateToFolder(folder)}
                  className="group relative bg-white border border-neutral-200 rounded-2xl p-4 flex flex-col gap-2 hover:border-primary-300 hover:shadow-sm transition-all cursor-pointer text-left"
                >
                  <div className="w-full aspect-video flex items-center justify-center bg-yellow-50 rounded-xl">
                    <Folder className="w-10 h-10 text-yellow-400" />
                  </div>
                  <p className="text-xs font-semibold text-neutral-700 leading-snug line-clamp-2">{folder.name}</p>
                  <p className="text-[10px] text-neutral-400">{formatDate(folder.created_at)}</p>
                  <button
                    onClick={e => { e.stopPropagation(); deleteFolderMutation.mutate(folder.id) }}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 text-neutral-300 hover:text-danger-500 transition-all cursor-pointer"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </button>
              ))}
            </div>
          )}

          {/* 그리드 뷰 — 1곡 1카드. 클릭 시 모든 키+버전 탐색 가능한 PreviewModal 열기 */}
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fill, minmax(${gridSize}px, 1fr))`, gap: '0.75rem' }}>
            {groupedFiles.map(({ key: groupKey, files: groupAllFiles, subGroups }) => {
              // 대표 파일: subGroups의 첫 번째 최신 버전
              const rep = subGroups[0].latest
              const imgSrc = `${serverUrl}/api/sheets/${rep.id}/preview`
              const isImg = isImageExt(rep.extension)
              const isPdfFile = isPdfExt(rep.extension)
              // 이 곡의 모든 키 목록 (중복 제거)
              const keys = [...new Set(groupAllFiles.map(f => f.key_root ? formatKey(f.key_root, f.key_mode) : ''))]
              const totalCount = groupAllFiles.length
              return (
                <div
                  key={groupKey}
                  className="group relative bg-white border border-neutral-200 rounded-2xl overflow-hidden flex flex-col hover:border-primary-300 hover:shadow-sm transition-all cursor-pointer"
                  onClick={() => openPreview(rep, groupAllFiles)}
                >
                  {/* 썸네일 */}
                  <div className="w-full aspect-video flex items-center justify-center relative overflow-hidden bg-neutral-50">
                    {isImg ? (
                      <img src={imgSrc} alt={rep.display_title} loading="lazy" className="w-full h-full object-contain" />
                    ) : isPdfFile ? (
                      <div className="flex flex-col items-center gap-1">
                        <FileText className="w-10 h-10 text-red-300" />
                        <span className="text-[9px] font-bold text-red-300 tracking-widest">PDF</span>
                      </div>
                    ) : (
                      <FileImage className="w-10 h-10 text-neutral-300" />
                    )}
                    {!!rep.is_event_only && (
                      <span className="absolute top-1.5 left-1.5 text-[9px] font-semibold bg-amber-500 text-white px-1 py-0.5 rounded">이벤트</span>
                    )}
                    {totalCount > 1 && (
                      <span className="absolute top-1.5 right-1.5 text-[9px] font-semibold bg-black/50 text-white px-1.5 py-0.5 rounded">{totalCount}개</span>
                    )}
                  </div>
                  {/* 정보 */}
                  <div className="p-3 flex flex-col gap-1.5 flex-1">
                    <p className="text-xs font-semibold text-neutral-800 leading-snug line-clamp-2">{rep.display_title}</p>
                    {/* 키 배지 목록 */}
                    {keys.some(Boolean) && (
                      <div className="flex flex-wrap gap-1">
                        {keys.filter(Boolean).map(k => (
                          <span key={k} className="font-mono text-[9px] bg-primary-50 text-primary-600 px-1.5 py-0.5 rounded font-semibold">{k}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  {/* 호버 액션 */}
                  <div
                    className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-0.5 opacity-0 group-hover:opacity-100 bg-white/95 py-2 border-t border-neutral-100 transition-all"
                    onClick={e => e.stopPropagation()}
                  >
                    <button onClick={() => openPreview(rep, groupAllFiles)} className="flex items-center gap-0.5 text-[10px] font-semibold text-neutral-600 hover:text-neutral-800 cursor-pointer px-2 py-1 rounded hover:bg-neutral-100"><Eye className="w-3 h-3" />보기</button>
                    <button onClick={() => setEditingFile(rep)} className="flex items-center gap-0.5 text-[10px] font-semibold text-primary-600 cursor-pointer px-2 py-1 rounded hover:bg-primary-50"><Pencil className="w-3 h-3" />수정</button>
                    <button onClick={() => downloadSheetFile(rep.id)} className="text-neutral-400 hover:text-neutral-600 cursor-pointer px-2 py-1 rounded hover:bg-neutral-50"><Download className="w-3 h-3" /></button>
                  </div>
                </div>
              )
            })}
          </div>

          {folders.length === 0 && files.length === 0 && (
            <div className="py-12 text-center text-neutral-400 text-xs">악보가 없습니다</div>
          )}
        </div>
      )}

      {/* 휴지통 뷰 */}
      {showTrash && (
        <div className="bg-white border border-neutral-200 rounded-2xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/60 text-neutral-500 font-semibold">
                <th className="px-4 py-3 text-left">제목</th>
                <th className="px-3 py-3 text-left hidden sm:table-cell">Key</th>
                <th className="px-3 py-3 text-left hidden md:table-cell">Page</th>
                <th className="px-3 py-3 text-left hidden md:table-cell">Ver</th>
                <th className="px-3 py-3 text-left hidden lg:table-cell">삭제일</th>
                <th className="px-3 py-3 text-left hidden lg:table-cell">삭제자</th>
                <th className="px-3 py-3 text-right">액션</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {trashItems.map((file: SheetFile) => (
                <tr key={file.id} className="hover:bg-neutral-50/60 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-neutral-300 shrink-0" />
                      <span className="text-neutral-500 truncate">{file.display_title}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 hidden sm:table-cell">
                    <span className="font-mono text-[10px] bg-neutral-100 text-neutral-400 px-1.5 py-0.5 rounded">
                      {formatKey(file.key_root, file.key_mode)}
                    </span>
                  </td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-400">{file.page_number}p</td>
                  <td className="px-3 py-3 hidden md:table-cell text-neutral-400">
                    {file.version > 1 && `v${file.version}`}
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">
                    {file.deleted_at ? formatDate(file.deleted_at) : ''}
                  </td>
                  <td className="px-3 py-3 hidden lg:table-cell text-neutral-400">{file.deleted_by}</td>
                  <td className="px-3 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => restoreMutation.mutate(file.id)}
                        className="text-neutral-400 hover:text-success-500 transition-colors cursor-pointer p-1"
                        title="복구"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                      {isSuper && (
                        <button
                          onClick={() => {
                            if (confirm('완전 삭제하면 복구할 수 없습니다. 계속하시겠습니까?')) {
                              purgeFileMutation.mutate(file.id)
                            }
                          }}
                          className="text-neutral-400 hover:text-danger-500 transition-colors cursor-pointer p-1"
                          title="완전 삭제"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {trashItems.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-neutral-400 text-xs">
                    휴지통이 비어 있습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 모달 */}
      {showUpload && (
        <UploadModal
          folderId={currentFolderId}
          onClose={() => setShowUpload(false)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['sheets'] })}
        />
      )}
      {showNewFolder && (
        <NewFolderModal
          parentId={currentFolderId}
          onClose={() => setShowNewFolder(false)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['sheets-folders'] })}
        />
      )}
      {editingFile && (
        <EditSheetModal
          file={editingFile}
          onClose={() => setEditingFile(null)}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['sheets'] })}
        />
      )}
      {previewFile && (
        <PreviewModal
          file={previewFile}
          versions={previewVersions}
          onClose={() => setPreviewFile(null)}
          onEdit={() => { setEditingFile(previewFile); setPreviewFile(null) }}
        />
      )}
    </div>
  )
}

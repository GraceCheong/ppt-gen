import { useState, useMemo } from 'react'
import { X, Download, Pencil, ChevronLeft, ChevronRight, FileText, FileX, Upload } from 'lucide-react'
import { downloadSheetFile } from '../../api/sheets'
import type { SheetFile } from '../../api/sheets'
import { formatKey, UploadModal } from './UploadModal'

// 음악적 키 순서: C D E F G A B
const KEY_NOTE_ORDER: Record<string, number> = { C: 0, D: 1, E: 2, F: 3, G: 4, A: 5, B: 6 }

function sortedVersions(versions: SheetFile[]): SheetFile[] {
  return [...versions].sort((a, b) => {
    const na = KEY_NOTE_ORDER[a.key_root?.charAt(0) ?? ''] ?? 99
    const nb = KEY_NOTE_ORDER[b.key_root?.charAt(0) ?? ''] ?? 99
    if (na !== nb) return na - nb
    const fa = formatKey(a.key_root, a.key_mode)
    const fb = formatKey(b.key_root, b.key_mode)
    if (fa !== fb) return fa.localeCompare(fb)
    if (a.page_number !== b.page_number) return a.page_number - b.page_number
    return a.version - b.version
  })
}

function keyToUI(keyRoot: string, keyMode: string): { base: string; suffix: string } {
  if (!keyRoot) return { base: 'C', suffix: '' }
  const base = keyRoot.charAt(0)
  const accidental = keyRoot.slice(1)
  const suffix = keyMode === 'minor' ? accidental + 'm' : accidental
  return { base, suffix }
}

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp'])
function isImageExt(ext: string | null | undefined) { return IMAGE_EXTS.has(ext?.toLowerCase() ?? '') }
function isPdfExt(ext: string | null | undefined) { return ext?.toLowerCase() === 'pdf' }
function formatDate(iso: string) { return iso ? new Date(iso).toLocaleDateString('ko-KR') : '' }

export interface PreviewModalProps {
  file: SheetFile
  versions: SheetFile[]
  onClose: () => void
  onEdit?: () => void
}

export function PreviewModal({ file, versions, onClose, onEdit }: PreviewModalProps) {
  const sorted = useMemo(() => sortedVersions(versions), [versions])

  const [idx, setIdx] = useState(() => {
    const i = sortedVersions(versions).findIndex(v => v.id === file.id)
    return i >= 0 ? i : 0
  })
  const [thumbFailed, setThumbFailed] = useState(false)
  const [showUpload, setShowUpload] = useState(false)

  const current = sorted[idx] ?? file
  const currentKeyDisplay = current.key_root ? formatKey(current.key_root, current.key_mode) : '—'

  // 키 그룹: 고유 키 → 해당 키의 첫 번째 idx
  const keyGroups = useMemo(() => {
    const map = new Map<string, number>()
    sorted.forEach((v, i) => {
      const k = v.key_root ? formatKey(v.key_root, v.key_mode) : '—'
      if (!map.has(k)) map.set(k, i)
    })
    return [...map.entries()].map(([key, firstIdx]) => ({ key, firstIdx }))
  }, [sorted])

  const previewUrl = `/api/sheets/${current.id}/preview`
  const thumbUrl = `/api/sheets/${current.id}/thumb`
  const isPdf = isPdfExt(current.extension)
  const isImage = isImageExt(current.extension)

  function navigate(delta: number) {
    setIdx(i => Math.max(0, Math.min(sorted.length - 1, i + delta)))
    setThumbFailed(false)
  }

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/60 backdrop-blur-sm px-2 py-3 sm:px-4 sm:py-6" onClick={onClose}>
        <div className="bg-white border border-neutral-200 rounded-xl sm:rounded-2xl shadow-2xl w-full max-w-3xl h-[95vh] sm:h-[90vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>

          {/* 헤더 */}
          <div className="p-4 border-b border-neutral-100 flex items-center justify-between shrink-0 gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="w-4 h-4 text-neutral-400 shrink-0" />
              <span className="text-sm font-bold text-neutral-800 truncate">{current.display_title}</span>
              {current.key_root && (
                <span className="font-mono text-[10px] bg-primary-50 text-primary-600 px-1.5 py-0.5 rounded font-semibold shrink-0">
                  {currentKeyDisplay}
                </span>
              )}
              {current.page_number > 1 && (
                <span className="text-[10px] text-neutral-400 shrink-0">{current.page_number}p</span>
              )}
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              {onEdit && (
                <button onClick={onEdit}
                  className="flex items-center justify-center gap-1 px-2.5 py-1.5 sm:px-3 sm:py-1.5 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer"
                  title="수정"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">수정</span>
                </button>
              )}
              <button onClick={() => setShowUpload(true)}
                className="flex items-center justify-center gap-1 px-2.5 py-1.5 sm:px-3 sm:py-1.5 text-xs font-semibold bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer"
                title="업로드"
              >
                <Upload className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">업로드</span>
              </button>
              <button onClick={() => downloadSheetFile(current.id)}
                className="flex items-center justify-center gap-1 px-2.5 py-1.5 sm:px-3 sm:py-1.5 text-xs font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors cursor-pointer"
                title="다운로드"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">다운로드</span>
              </button>
              <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600 cursor-pointer p-1" title="닫기">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>


          {/* 키 버튼 바 — 키당 하나의 버튼, 1p/2p는 좌우 화살표로 탐색 */}
          {keyGroups.length > 0 && (
            <div className="px-3 py-2 border-b border-neutral-100 flex items-center gap-1.5 shrink-0 bg-neutral-50">
              {keyGroups.map(({ key, firstIdx }) => (
                <button
                  key={key}
                  onClick={() => { setIdx(firstIdx); setThumbFailed(false) }}
                  className={`px-2.5 py-0.5 rounded text-[11px] font-semibold font-mono transition-colors cursor-pointer ${
                    key === currentKeyDisplay
                      ? 'bg-primary-600 text-white'
                      : 'bg-neutral-200 text-neutral-600 hover:bg-neutral-300'
                  }`}
                >
                  {key}
                </button>
              ))}
              {/* 현재 페이지 표시 (복수 페이지일 때) */}
              {(() => {
                const keyFiles = sorted.filter(v =>
                  (v.key_root ? formatKey(v.key_root, v.key_mode) : '—') === currentKeyDisplay
                )
                if (keyFiles.length <= 1) return null
                const pageIdx = keyFiles.findIndex(v => v.id === current.id) + 1
                return (
                  <span className="ml-auto text-[10px] text-neutral-400 font-mono">
                    {pageIdx} / {keyFiles.length}p
                  </span>
                )
              })()}
            </div>
          )}

          {/* 미리보기 — 좌우 화살표가 키와 페이지를 선형으로 탐색 */}
          <div className="relative flex-1 overflow-auto bg-neutral-50 flex items-center justify-center">
            {idx > 0 && (
              <button
                onClick={() => navigate(-1)}
                className="absolute left-3 top-1/2 -translate-y-1/2 z-10 w-12 h-12 flex items-center justify-center rounded-full bg-black/40 text-white hover:bg-black/60 transition-colors cursor-pointer shadow-lg"
              >
                <ChevronLeft className="w-7 h-7" />
              </button>
            )}
            {idx < sorted.length - 1 && (
              <button
                onClick={() => navigate(1)}
                className="absolute right-3 top-1/2 -translate-y-1/2 z-10 w-12 h-12 flex items-center justify-center rounded-full bg-black/40 text-white hover:bg-black/60 transition-colors cursor-pointer shadow-lg"
              >
                <ChevronRight className="w-7 h-7" />
              </button>
            )}

            {isPdf ? (
              thumbFailed ? (
                <div className="flex flex-col items-center gap-4 text-neutral-500 p-8 text-center">
                  <FileX className="w-12 h-12 text-neutral-300" />
                  <p className="text-sm font-semibold">미리보기를 불러올 수 없습니다</p>
                  <button
                    onClick={() => downloadSheetFile(current.id)}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    PDF 다운로드해서 열기
                  </button>
                </div>
              ) : (
                <div className="w-full h-full flex flex-col items-center gap-3 p-4 overflow-auto">
                  <img
                    key={current.id}
                    src={thumbUrl}
                    alt={current.display_title}
                    className="max-w-full object-contain rounded shadow-md"
                    onError={() => setThumbFailed(true)}
                  />
                  <button
                    onClick={() => downloadSheetFile(current.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-neutral-500 bg-neutral-100 rounded-lg hover:bg-neutral-200 transition-colors cursor-pointer shrink-0"
                  >
                    <Download className="w-3.5 h-3.5" />
                    전체 PDF 다운로드
                  </button>
                </div>
              )
            ) : isImage ? (
              <img
                key={current.id}
                src={previewUrl}
                alt={current.display_title}
                className="max-w-full max-h-full object-contain p-4"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-neutral-400 text-sm">
                이 형식은 미리보기를 지원하지 않습니다
              </div>
            )}
          </div>

          <div className="px-4 py-2 border-t border-neutral-100 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-neutral-400 shrink-0">
            <span className="truncate max-w-[150px] sm:max-w-none" title={current.original_filename}>파일: {current.original_filename}</span>
            <span>크기: {(current.size_bytes / 1024).toFixed(0)}KB</span>
            <span className="truncate max-w-[100px] sm:max-w-none">업로더: {current.uploaded_by}</span>
            <span>{formatDate(current.uploaded_at)}</span>
          </div>
        </div>
      </div>

      {showUpload && <UploadForCurrent current={current} onClose={() => setShowUpload(false)} />}
    </>
  )
}

function UploadForCurrent({ current, onClose }: { current: SheetFile; onClose: () => void }) {
  const { base, suffix } = keyToUI(current.key_root, current.key_mode)
  return (
    <UploadModal
      folderId={current.folder_id}
      initialTitle={current.display_title}
      initialSubtitle={current.subtitle ?? ''}
      initialBaseNote={base}
      initialSuffix={suffix}
      initialPageNumber={current.page_number}
      onClose={onClose}
      onSuccess={onClose}
    />
  )
}

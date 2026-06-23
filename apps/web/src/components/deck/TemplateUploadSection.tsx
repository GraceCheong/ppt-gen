import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadTemplate, type UploadResult } from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TIPS } from '../../constants/tooltips'
import { Upload, AlertTriangle, XCircle, CheckCircle2, ChevronDown } from 'lucide-react'

const ISSUE_LABELS: Record<string, string> = {
  lyrics_layout_missing: '"가사" 레이아웃 없음 — 슬라이드 마스터에 이름이 "가사"인 레이아웃이 필요합니다.',
  lyrics_placeholder_count: '"가사" 레이아웃에 텍스트 placeholder가 2개 이상 필요합니다 (큰 것: 가사, 작은 것: 곡 제목).',
  title_layout_missing: '"제목" 레이아웃 없음 — 슬라이드 마스터에 이름이 "제목"인 레이아웃이 필요합니다.',
}

const WARNING_LABELS: Record<string, string> = {
  home_layout_missing: '"홈" 레이아웃 없음 — 홈/빈 슬라이드로 사용됩니다. 없으면 첫 번째 레이아웃으로 대체됩니다.',
  worship_layout_missing: '"예배를 시작하며" 레이아웃 없음 — 예배 오프닝 슬라이드입니다. 없으면 홈 레이아웃으로 대체됩니다.',
  prayer_layout_missing: '"기도" 레이아웃 없음 — 마무리 기도 슬라이드입니다. 없으면 홈 레이아웃으로 대체됩니다.',
}

function IncompatiblePanel({ result }: { result: UploadResult }) {
  return (
    <div className="mt-2.5 text-xs border border-danger-200 bg-danger-50/50 rounded-xl p-3.5 space-y-3.5">
      <div className="flex items-center gap-1.5 text-danger-700 font-bold">
        <XCircle className="w-4 h-4 text-danger-500" />
        <span>호환되지 않는 템플릿</span>
      </div>

      <div className="space-y-1.5">
        <p className="text-danger-700 font-semibold">필수 조건 미충족:</p>
        <ul className="space-y-1 pl-1">
          {(result.issues ?? []).map(issue => (
            <li key={issue} className="text-danger-800 flex items-start gap-1">
              <span className="text-danger-500 shrink-0">✕</span>
              <span>{ISSUE_LABELS[issue] ?? issue}</span>
            </li>
          ))}
        </ul>
      </div>

      <details className="group pt-2 border-t border-danger-200/50">
        <summary className="cursor-pointer font-semibold text-danger-700 select-none flex items-center justify-between">
          <span>템플릿 구성 방법 보기</span>
          <ChevronDown className="w-3.5 h-3.5 transition-transform duration-200 group-open:rotate-180" />
        </summary>
        <div className="mt-3 space-y-3 text-neutral-600 leading-relaxed">
          <div>
            <p className="font-semibold mb-1">PowerPoint 슬라이드 마스터에 다음 레이아웃을 추가하세요:</p>
            <p className="text-[11px] text-neutral-400 mb-2.5">보기 → 슬라이드 마스터 → 레이아웃 삽입 후 이름 변경</p>
            <table className="w-full border-collapse text-xs border border-neutral-200 rounded-lg overflow-hidden">
              <thead>
                <tr className="bg-neutral-50 text-neutral-700 border-b border-neutral-200">
                  <th className="text-left p-2 font-bold">레이아웃 이름</th>
                  <th className="text-left p-2 font-bold">필수 여부</th>
                  <th className="text-left p-2 font-bold">placeholder 구성</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                <tr>
                  <td className="p-2 font-mono font-bold text-neutral-800">가사</td>
                  <td className="p-2 text-danger-600 font-semibold">필수</td>
                  <td className="p-2 text-neutral-500">
                    텍스트 박스 2개 — <strong className="text-neutral-700 font-semibold">큰 것: 가사 내용</strong>, <strong className="text-neutral-700 font-semibold">작은 것: 곡 제목</strong>
                  </td>
                </tr>
                <tr>
                  <td className="p-2 font-mono font-bold text-neutral-800">제목</td>
                  <td className="p-2 text-danger-600 font-semibold">필수</td>
                  <td className="p-2 text-neutral-500 font-medium">
                    텍스트 박스 1개 이상 — 곡 제목 표시용
                  </td>
                </tr>
                <tr>
                  <td className="p-2 font-mono font-bold text-neutral-800">홈</td>
                  <td className="p-2 text-warning-600 font-semibold">권장</td>
                  <td className="p-2 text-neutral-500 font-medium">
                    빈 슬라이드 — 시작/마무리/빈 화면용
                  </td>
                </tr>
                <tr>
                  <td className="p-2 font-mono font-bold text-neutral-800">예배를 시작하며</td>
                  <td className="p-2 text-warning-600 font-semibold">권장</td>
                  <td className="p-2 text-neutral-500 font-medium">예배 오프닝 슬라이드</td>
                </tr>
                <tr>
                  <td className="p-2 font-mono font-bold text-neutral-800">기도</td>
                  <td className="p-2 text-warning-600 font-semibold">권장</td>
                  <td className="p-2 text-neutral-500 font-medium">마무리 기도 슬라이드</td>
                </tr>
              </tbody>
            </table>
          </div>

          {(result.layout_names ?? []).length > 0 && (
            <div className="pt-2 border-t border-neutral-100">
              <p className="font-semibold text-neutral-700">현재 파일의 레이아웃 목록:</p>
              <p className="text-neutral-500 text-[11px] mt-1 font-mono break-all">{result.layout_names!.join(', ')}</p>
            </div>
          )}
        </div>
      </details>
    </div>
  )
}

function WarningPanel({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null
  return (
    <div className="mt-2 text-[11px] border border-warning-200 bg-warning-50/50 rounded-xl p-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-warning-700 font-bold">
        <AlertTriangle className="w-3.5 h-3.5 text-warning-500" />
        <span>권장 레이아웃 없음 (생성에는 문제 없음)</span>
      </div>
      <div className="space-y-1 pl-1">
        {warnings.map(w => (
          <p key={w} className="text-warning-800 font-medium">⚠ {WARNING_LABELS[w] ?? w}</p>
        ))}
      </div>
    </div>
  )
}

type Status = 'idle' | 'uploading' | 'success' | 'incompatible' | 'error'

export function TemplateUploadSection() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { setTemplateId } = useProjectStore()

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pptx')) {
      setStatus('error')
      setErrorMsg('.pptx 파일만 업로드할 수 있습니다.')
      return
    }

    setStatus('uploading')
    setUploadResult(null)
    setErrorMsg(null)

    try {
      const result = await uploadTemplate(file)
      setUploadResult(result)

      if (!result.compatible) {
        setStatus('incompatible')
      } else {
        setStatus('success')
        queryClient.invalidateQueries({ queryKey: ['templates'] })
        if (result.template_id) setTemplateId(result.template_id)
        setTimeout(() => setStatus('idle'), 4000)
      }
    } catch (e) {
      setStatus('error')
      setErrorMsg(e instanceof Error ? e.message : '업로드 실패')
    }
  }

  function openPicker() {
    setStatus('idle')
    setUploadResult(null)
    setErrorMsg(null)
    fileInputRef.current?.click()
  }

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pptx"
        className="hidden"
        onChange={e => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />

      <button
        onClick={openPicker}
        disabled={status === 'uploading'}
        title={TIPS.template.upload}
        className="text-[11px] font-semibold text-primary-500 hover:text-primary-600 disabled:text-neutral-400 transition-colors flex items-center gap-1.5 cursor-pointer select-none py-1"
      >
        <Upload className="w-3.5 h-3.5" />
        <span>{status === 'uploading' ? '검증 중...' : '템플릿 추가 업로드 (.pptx)'}</span>
      </button>

      {status === 'success' && (
        <div className="mt-2 text-xs text-success-700 bg-success-50 border border-success-100 rounded-xl p-2.5 flex items-start gap-1.5">
          <CheckCircle2 className="w-4 h-4 text-success-500 shrink-0" />
          <span>
            &quot;{uploadResult?.template_id}&quot; 업로드 완료
            {(uploadResult?.warnings?.length ?? 0) > 0 && ' (일부 권장 레이아웃 없음)'}
          </span>
        </div>
      )}

      {status === 'success' && (uploadResult?.warnings?.length ?? 0) > 0 && (
        <WarningPanel warnings={uploadResult!.warnings!} />
      )}

      {status === 'error' && (
        <div className="mt-2 text-xs text-danger-700 bg-danger-50 border border-danger-100 rounded-xl p-2.5 flex items-start gap-1.5">
          <XCircle className="w-4 h-4 text-danger-500 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {status === 'incompatible' && uploadResult && (
        <IncompatiblePanel result={uploadResult} />
      )}
    </div>
  )
}


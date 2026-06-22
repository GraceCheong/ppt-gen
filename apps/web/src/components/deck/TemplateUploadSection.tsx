import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadTemplate, type UploadResult } from '../../api/templates'
import { useProjectStore } from '../../store/projectStore'
import { TIPS } from '../../constants/tooltips'

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
    <div className="mt-2 text-xs border border-orange-200 bg-orange-50 rounded-lg p-3 space-y-2">
      <p className="font-semibold text-orange-700">호환되지 않는 템플릿</p>

      <div>
        <p className="text-orange-600 font-medium mb-1">필수 조건 미충족:</p>
        <ul className="space-y-1">
          {(result.issues ?? []).map(issue => (
            <li key={issue} className="text-orange-800">✕ {ISSUE_LABELS[issue] ?? issue}</li>
          ))}
        </ul>
      </div>

      <details className="pt-1">
        <summary className="cursor-pointer font-medium text-orange-700 select-none">
          템플릿 구성 방법 보기 ▾
        </summary>
        <div className="mt-2 space-y-3 text-gray-700">
          <div>
            <p className="font-medium mb-1">PowerPoint 슬라이드 마스터에 다음 레이아웃을 추가하세요:</p>
            <p className="text-gray-500 mb-2">보기 → 슬라이드 마스터 → 레이아웃 삽입 후 이름 변경</p>
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-orange-100 text-orange-800">
                  <th className="text-left p-1.5 border border-orange-200">레이아웃 이름</th>
                  <th className="text-left p-1.5 border border-orange-200">필수</th>
                  <th className="text-left p-1.5 border border-orange-200">placeholder 구성</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-orange-100">
                <tr>
                  <td className="p-1.5 border border-orange-200 font-mono font-semibold">가사</td>
                  <td className="p-1.5 border border-orange-200 text-red-600">필수</td>
                  <td className="p-1.5 border border-orange-200">
                    텍스트 박스 2개 — <strong>큰 것: 가사 내용</strong>, <strong>작은 것: 곡 제목</strong>
                  </td>
                </tr>
                <tr>
                  <td className="p-1.5 border border-orange-200 font-mono font-semibold">제목</td>
                  <td className="p-1.5 border border-orange-200 text-red-600">필수</td>
                  <td className="p-1.5 border border-orange-200">
                    텍스트 박스 1개 이상 — 곡 제목 표시용
                  </td>
                </tr>
                <tr>
                  <td className="p-1.5 border border-orange-200 font-mono font-semibold">홈</td>
                  <td className="p-1.5 border border-orange-200 text-yellow-600">권장</td>
                  <td className="p-1.5 border border-orange-200">
                    빈 슬라이드 — 시작/마무리/빈 화면용
                  </td>
                </tr>
                <tr>
                  <td className="p-1.5 border border-orange-200 font-mono font-semibold">예배를 시작하며</td>
                  <td className="p-1.5 border border-orange-200 text-yellow-600">권장</td>
                  <td className="p-1.5 border border-orange-200">예배 오프닝 슬라이드</td>
                </tr>
                <tr>
                  <td className="p-1.5 border border-orange-200 font-mono font-semibold">기도</td>
                  <td className="p-1.5 border border-orange-200 text-yellow-600">권장</td>
                  <td className="p-1.5 border border-orange-200">마무리 기도 슬라이드</td>
                </tr>
              </tbody>
            </table>
          </div>

          {(result.layout_names ?? []).length > 0 && (
            <div>
              <p className="font-medium text-gray-600">현재 파일의 레이아웃 목록:</p>
              <p className="text-gray-500 mt-0.5">{result.layout_names!.join(', ')}</p>
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
    <div className="mt-1 text-xs border border-yellow-200 bg-yellow-50 rounded p-2 space-y-1">
      <p className="font-medium text-yellow-700">권장 레이아웃 없음 (생성에는 문제 없음)</p>
      {warnings.map(w => (
        <p key={w} className="text-yellow-700">⚠ {WARNING_LABELS[w] ?? w}</p>
      ))}
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
        className="text-xs text-blue-500 hover:text-blue-700 disabled:text-gray-400 transition-colors"
      >
        {status === 'uploading' ? '검증 중...' : '+ 템플릿 업로드'}
      </button>

      {status === 'success' && (
        <p className="mt-1 text-xs text-green-600">
          ✓ &quot;{uploadResult?.template_id}&quot; 업로드 완료
          {(uploadResult?.warnings?.length ?? 0) > 0 && ' (일부 권장 레이아웃 없음)'}
        </p>
      )}

      {status === 'success' && (uploadResult?.warnings?.length ?? 0) > 0 && (
        <WarningPanel warnings={uploadResult!.warnings!} />
      )}

      {status === 'error' && (
        <p className="mt-1 text-xs text-red-500">{errorMsg}</p>
      )}

      {status === 'incompatible' && uploadResult && (
        <IncompatiblePanel result={uploadResult} />
      )}
    </div>
  )
}

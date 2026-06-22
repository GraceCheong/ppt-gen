import { useEffect, useState } from 'react'
import { getServerUrl } from '../../api/serverConfig'

interface Props {
  templateId: string | null
}

export function TemplatePreview({ templateId }: Props) {
  const [src, setSrc] = useState<string | null>(null)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    if (!templateId) {
      setSrc(null)
      return
    }
    setHasError(false)
    getServerUrl().then(base => {
      setSrc(`${base}/api/templates/${encodeURIComponent(templateId)}/preview`)
    })
  }, [templateId])

  if (!src) return null

  return (
    <div className="w-full rounded border border-gray-200 overflow-hidden bg-gray-100">
      {hasError ? (
        <div className="aspect-video flex items-center justify-center">
          <span className="text-xs text-gray-400">프리뷰 없음</span>
        </div>
      ) : (
        <img
          key={src}
          src={src}
          alt={templateId ?? ''}
          className="w-full block"
          onError={() => setHasError(true)}
        />
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { getServerUrl } from '../../api/serverConfig'
import { ImageOff } from 'lucide-react'

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
    <div className="w-full rounded-xl border border-neutral-200/60 overflow-hidden bg-neutral-100">
      {hasError ? (
        <div className="aspect-video flex flex-col items-center justify-center gap-2 bg-neutral-50 text-neutral-400 p-4">
          <ImageOff className="w-5 h-5 text-neutral-300" />
          <span className="text-[11px] font-medium">프리뷰 이미지가 없습니다</span>
        </div>
      ) : (
        <img
          key={src}
          src={src}
          alt={templateId ?? ''}
          className="w-full block aspect-video object-cover"
          onError={() => setHasError(true)}
        />
      )}
    </div>
  )
}


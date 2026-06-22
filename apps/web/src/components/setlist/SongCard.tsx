import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { SongEntry } from '../../types/project'
import { TIPS } from '../../constants/tooltips'

interface Props {
  song: SongEntry
  isSelected: boolean
  onSelect: () => void
  onRemove: () => void
  onMoveUp?: () => void
  onMoveDown?: () => void
}

export function SongCard({ song, isSelected, onSelect, onRemove, onMoveUp, onMoveDown }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: song.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer border-b border-gray-100 group select-none
        ${isSelected ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'}`}
      onClick={onSelect}
    >
      {/* 모바일: ▲▼ 순서 버튼 */}
      <div
        className="flex md:hidden flex-col shrink-0"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={() => onMoveUp?.()}
          disabled={!onMoveUp}
          title={TIPS.setlist.songMoveUp}
          className="text-gray-300 hover:text-gray-600 disabled:text-gray-100 disabled:cursor-default leading-none py-0.5 px-1 text-[11px]"
        >
          ▲
        </button>
        <button
          onClick={() => onMoveDown?.()}
          disabled={!onMoveDown}
          title={TIPS.setlist.songMoveDown}
          className="text-gray-300 hover:text-gray-600 disabled:text-gray-100 disabled:cursor-default leading-none py-0.5 px-1 text-[11px]"
        >
          ▼
        </button>
      </div>

      {/* 데스크탑: 드래그 핸들 */}
      <span
        {...attributes}
        {...listeners}
        className="hidden md:block text-gray-300 cursor-grab active:cursor-grabbing text-sm leading-none px-0.5 shrink-0"
        onClick={e => e.stopPropagation()}
        title={TIPS.setlist.songDragHandle}
      >
        ⠿
      </span>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-800 truncate">{song.title || '(제목 없음)'}</div>
        {song.sequence && (
          <div className="text-xs text-gray-400 truncate mt-0.5">{song.sequence}</div>
        )}
      </div>

      <button
        className="opacity-0 group-hover:opacity-100 md:group-hover:opacity-100 text-gray-300 hover:text-red-400 text-xs px-1 shrink-0"
        onClick={e => { e.stopPropagation(); onRemove() }}
        title={TIPS.setlist.songRemove}
      >
        ✕
      </button>
    </div>
  )
}

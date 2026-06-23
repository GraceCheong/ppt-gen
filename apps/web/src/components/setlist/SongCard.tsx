import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { SongEntry } from '../../types/project'
import { TIPS } from '../../constants/tooltips'
import { GripVertical, ChevronUp, ChevronDown, Trash2 } from 'lucide-react'

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
    opacity: isDragging ? 0.3 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2.5 px-4 py-3.5 cursor-pointer border-b border-neutral-100/60 group select-none transition-all duration-150
        ${isSelected 
          ? 'bg-primary-50/40 border-l-4 border-l-primary-500 pl-3 font-semibold' 
          : 'hover:bg-neutral-50/50 border-l-4 border-l-transparent bg-white'}`}
      onClick={onSelect}
    >
      {/* 모바일: ▲▼ 순서 버튼 */}
      <div
        className="flex md:hidden flex-col shrink-0 items-center justify-center -space-y-0.5"
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={() => onMoveUp?.()}
          disabled={!onMoveUp}
          title={TIPS.setlist.songMoveUp}
          className="text-neutral-300 hover:text-neutral-600 disabled:text-neutral-100 disabled:cursor-default p-0.5"
        >
          <ChevronUp className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => onMoveDown?.()}
          disabled={!onMoveDown}
          title={TIPS.setlist.songMoveDown}
          className="text-neutral-300 hover:text-neutral-600 disabled:text-neutral-100 disabled:cursor-default p-0.5"
        >
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 데스크탑: 드래그 핸들 */}
      <span
        {...attributes}
        {...listeners}
        className="hidden md:block text-neutral-300 hover:text-neutral-400 cursor-grab active:cursor-grabbing p-1 shrink-0 transition-colors"
        onClick={e => e.stopPropagation()}
        title={TIPS.setlist.songDragHandle}
      >
        <GripVertical className="w-4 h-4" />
      </span>

      <div className="flex-1 min-w-0">
        <div className={`text-xs font-semibold truncate ${isSelected ? 'text-primary-900' : 'text-neutral-800'}`}>
          {song.title || '(제목 없음)'}
        </div>
        {song.sequence && (
          <div className="text-[10px] text-neutral-400 font-mono mt-1 flex items-center gap-1 select-none">
            <span className="bg-neutral-100 border border-neutral-200/50 rounded px-1.5 py-0.5 text-neutral-500 font-semibold">{song.sequence}</span>
          </div>
        )}
      </div>

      <button
        className="opacity-0 group-hover:opacity-100 md:group-hover:opacity-100 text-neutral-300 hover:text-danger-500 p-1.5 shrink-0 transition-all rounded-lg hover:bg-neutral-100 cursor-pointer"
        onClick={e => { e.stopPropagation(); onRemove() }}
        title={TIPS.setlist.songRemove}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}


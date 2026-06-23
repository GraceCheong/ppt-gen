import { useState } from 'react'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useProjectStore } from '../../store/projectStore'
import { SongCard } from './SongCard'
import { LyricsSearchDialog } from '../lyrics/LyricsSearchDialog'
import type { LyricsCatalogItem } from '../../types/lyrics'
import { TIPS } from '../../constants/tooltips'
import { ListMusic, Search, Keyboard } from 'lucide-react'

export function SetlistPanel() {
  const { songs, selectedSongId, addSong, removeSong, reorderSongs, selectSong } = useProjectStore()
  const [showSearch, setShowSearch] = useState(false)
  const [showAddDirect, setShowAddDirect] = useState(false)
  const [directTitle, setDirectTitle] = useState('')

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  function handleDragEnd(event: import('@dnd-kit/core').DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const from = songs.findIndex(s => s.id === active.id)
    const to = songs.findIndex(s => s.id === over.id)
    if (from !== -1 && to !== -1) reorderSongs(from, to)
  }

  function handleSelectFromDB(item: LyricsCatalogItem) {
    addSong({
      title: item.title,
      sequence: item.sequence ?? '',
      lyrics: item.lyrics ?? '',
    })
  }

  function handleAddDirect() {
    const title = directTitle.trim()
    if (!title) return
    addSong({ title, sequence: '', lyrics: '' })
    setDirectTitle('')
    setShowAddDirect(false)
  }

  return (
    <div className="flex flex-col h-full bg-white select-none">
      {/* 셋리스트 헤더 및 컨트롤 */}
      <div className="px-4 py-3 border-b border-neutral-100 flex flex-col gap-2.5 shrink-0 bg-neutral-50/20">
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
          <ListMusic className="w-3.5 h-3.5 text-neutral-400" />
          <span>예배 셋리스트</span>
        </div>
        
        <div className="flex gap-1.5">
          <button
            className="flex-1 flex items-center justify-center gap-1 text-[11px] font-bold bg-primary-600 hover:bg-primary-700 text-white rounded-lg py-2 shadow-sm shadow-primary-600/5 hover:shadow-md hover:shadow-primary-600/10 transition-all cursor-pointer"
            onClick={() => setShowSearch(true)}
            title={TIPS.setlist.addFromDB}
          >
            <Search className="w-3 h-3" />
            <span>DB 검색 추가</span>
          </button>
          <button
            className="flex-1 flex items-center justify-center gap-1 text-[11px] font-bold border border-neutral-200 hover:border-neutral-300 text-neutral-700 rounded-lg py-2 hover:bg-neutral-50 active:bg-neutral-100 transition-colors cursor-pointer bg-white"
            onClick={() => setShowAddDirect(v => !v)}
            title={TIPS.setlist.addDirect}
          >
            <Keyboard className="w-3 h-3" />
            <span>직접 추가</span>
          </button>
        </div>

        {showAddDirect && (
          <div className="flex gap-1.5 mt-0.5 animate-in fade-in slide-in-from-top-1 duration-150">
            <input
              autoFocus
              type="text"
              placeholder="곡 제목 입력..."
              className="flex-1 border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs outline-none bg-white hover:bg-neutral-50/50 focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 transition-all"
              value={directTitle}
              onChange={e => setDirectTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleAddDirect(); if (e.key === 'Escape') setShowAddDirect(false) }}
            />
            <button 
              onClick={handleAddDirect} 
              title={TIPS.setlist.addConfirm} 
              className="text-xs font-bold bg-neutral-800 hover:bg-neutral-900 text-white rounded-lg px-3 py-1.5 transition-colors cursor-pointer shrink-0"
            >
              추가
            </button>
          </div>
        )}
      </div>

      {/* 리스트 영역 */}
      <div className="flex-1 overflow-y-auto bg-white py-1">
        {songs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center gap-2.5">
            <div className="w-10 h-10 rounded-full bg-neutral-50 border border-neutral-100 flex items-center justify-center">
              <ListMusic className="w-5 h-5 text-neutral-300" />
            </div>
            <div>
              <p className="text-xs font-semibold text-neutral-700">추가된 찬양이 없습니다</p>
              <p className="text-[10px] text-neutral-400 mt-1 leading-normal">
                가사 DB를 검색하거나 직접 입력하여<br />
                예배에 부를 찬양들을 추가해 보세요.
              </p>
            </div>
          </div>
        )}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={songs.map(s => s.id)} strategy={verticalListSortingStrategy}>
            <div className="divide-y divide-neutral-100/50">
              {songs.map((song, index) => (
                <SongCard
                  key={song.id}
                  song={song}
                  isSelected={selectedSongId === song.id}
                  onSelect={() => selectSong(song.id)}
                  onRemove={() => removeSong(song.id)}
                  onMoveUp={index > 0 ? () => reorderSongs(index, index - 1) : undefined}
                  onMoveDown={index < songs.length - 1 ? () => reorderSongs(index, index + 1) : undefined}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>

      {/* 셋리스트 푸터 */}
      <div className="px-4 py-2.5 border-t border-neutral-100 text-[10px] font-bold text-neutral-400 shrink-0 bg-neutral-50/20 flex items-center justify-between">
        <span>총 {songs.length}곡 구성됨</span>
        {songs.length > 0 && <span className="text-[9px] font-normal text-neutral-300">드래그하여 순서 변경 가능</span>}
      </div>

      {showSearch && (
        <LyricsSearchDialog
          onSelect={handleSelectFromDB}
          onClose={() => setShowSearch(false)}
        />
      )}
    </div>
  )
}


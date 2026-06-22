import { useState } from 'react'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useProjectStore } from '../../store/projectStore'
import { SongCard } from './SongCard'
import { LyricsSearchDialog } from '../lyrics/LyricsSearchDialog'
import type { LyricsCatalogItem } from '../../types/lyrics'
import { TIPS } from '../../constants/tooltips'

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
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-100">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">셋리스트</div>
        <div className="flex gap-1.5">
          <button
            className="flex-1 text-xs bg-blue-500 text-white rounded px-2 py-1.5 hover:bg-blue-600 transition-colors"
            onClick={() => setShowSearch(true)}
            title={TIPS.setlist.addFromDB}
          >
            DB에서 추가
          </button>
          <button
            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 hover:bg-gray-50 transition-colors"
            onClick={() => setShowAddDirect(v => !v)}
            title={TIPS.setlist.addDirect}
          >
            직접 입력
          </button>
        </div>
        {showAddDirect && (
          <div className="mt-2 flex gap-1.5">
            <input
              autoFocus
              type="text"
              placeholder="곡 제목"
              className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm outline-none focus:border-blue-400"
              value={directTitle}
              onChange={e => setDirectTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleAddDirect(); if (e.key === 'Escape') setShowAddDirect(false) }}
            />
            <button onClick={handleAddDirect} title={TIPS.setlist.addConfirm} className="text-xs bg-gray-700 text-white rounded px-2 py-1 hover:bg-gray-800">추가</button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {songs.length === 0 && (
          <p className="text-sm text-gray-400 text-center mt-8 px-4">
            곡을 추가해 주세요
          </p>
        )}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={songs.map(s => s.id)} strategy={verticalListSortingStrategy}>
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
          </SortableContext>
        </DndContext>
      </div>

      <div className="px-3 py-2 border-t border-gray-100 text-xs text-gray-400">
        {songs.length}곡
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

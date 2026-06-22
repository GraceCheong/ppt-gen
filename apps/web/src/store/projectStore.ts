import { create } from 'zustand'
import type { SongEntry, PptSettings } from '../types/project'
import { DEFAULT_SETTINGS } from '../types/project'

let _idCounter = 0
function genId(): string {
  return `song_${Date.now()}_${++_idCounter}`
}

interface ProjectState {
  songs: SongEntry[]
  selectedSongId: string | null
  templateId: string | null
  settings: PptSettings

  addSong: (song: Omit<SongEntry, 'id'>) => SongEntry
  updateSong: (id: string, patch: Partial<Omit<SongEntry, 'id'>>) => void
  removeSong: (id: string) => void
  reorderSongs: (from: number, to: number) => void
  selectSong: (id: string | null) => void
  setTemplateId: (id: string | null) => void
  updateSettings: (patch: Partial<PptSettings>) => void
  /** 이력에서 불러올 때: 현재 songs 전체를 교체한다. */
  loadSongs: (songs: SongEntry[]) => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  songs: [],
  selectedSongId: null,
  templateId: null,
  settings: { ...DEFAULT_SETTINGS },

  addSong: (songData) => {
    const song: SongEntry = { id: genId(), ...songData }
    set((state) => ({ songs: [...state.songs, song], selectedSongId: song.id }))
    return song
  },

  updateSong: (id, patch) =>
    set((state) => ({
      songs: state.songs.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    })),

  removeSong: (id) =>
    set((state) => {
      const next = state.songs.filter((s) => s.id !== id)
      const selected =
        state.selectedSongId === id
          ? (next[0]?.id ?? null)
          : state.selectedSongId
      return { songs: next, selectedSongId: selected }
    }),

  reorderSongs: (from, to) =>
    set((state) => {
      const songs = [...state.songs]
      const [moved] = songs.splice(from, 1)
      songs.splice(to, 0, moved)
      return { songs }
    }),

  selectSong: (id) => set({ selectedSongId: id }),

  setTemplateId: (id) => set({ templateId: id }),

  updateSettings: (patch) =>
    set((state) => ({ settings: { ...state.settings, ...patch } })),

  loadSongs: (songs) =>
    set({ songs, selectedSongId: songs[0]?.id ?? null }),
}))

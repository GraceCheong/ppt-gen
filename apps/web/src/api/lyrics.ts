import { apiFetch } from './client'
import type { LyricsCatalogItem } from '../types/lyrics'

export async function searchLyrics(q: string, limit = 10): Promise<LyricsCatalogItem[]> {
  const data = await apiFetch<{ items: LyricsCatalogItem[] }>(
    `/api/lyrics/search?q=${encodeURIComponent(q)}&limit=${limit}`
  )
  return data.items
}

export async function fetchRecentLyrics(limit = 30): Promise<LyricsCatalogItem[]> {
  const data = await apiFetch<{ items: LyricsCatalogItem[] }>(
    `/api/lyrics/recent?limit=${limit}`
  )
  return data.items
}

export async function fetchLyricsByTitle(title: string): Promise<LyricsCatalogItem | null> {
  try {
    return await apiFetch<LyricsCatalogItem>(
      `/api/lyrics/by-title?title=${encodeURIComponent(title)}`
    )
  } catch {
    return null
  }
}

export async function bulkSaveToLyricsDb(
  songs: { title: string; sequence: string; lyrics: string }[]
): Promise<{ saved: number }> {
  return apiFetch<{ ok: boolean; saved: number }>('/api/lyrics/bulk', {
    method: 'POST',
    body: JSON.stringify({ items: songs }),
  })
}

export async function downloadLyrics(
  title: string,
  sequence?: string
): Promise<{ found: boolean; lyrics: string }> {
  return apiFetch<{ found: boolean; lyrics: string; title: string }>('/api/lyrics/download', {
    method: 'POST',
    body: JSON.stringify({ title, sequence: sequence ?? '' }),
  })
}

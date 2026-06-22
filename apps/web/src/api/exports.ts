import { apiFetch } from './client'
import type { SongEntry, PptSettings } from '../types/project'

export async function createSonglistJob(
  songTitles: string[],
  templateId: string | null
): Promise<string> {
  const data = await apiFetch<{ job_id: string }>('/api/exports/songlist-card', {
    method: 'POST',
    body: JSON.stringify({ song_titles: songTitles, template_id: templateId }),
  })
  return data.job_id
}

export async function createPptxJob(
  songs: SongEntry[],
  settings: PptSettings,
  templateId: string | null
): Promise<string> {
  const payload = {
    template_id: templateId,
    songs: songs.map(s => ({
      title: s.title,
      sequence: s.sequence,
      lyrics: s.lyrics,
    })),
    settings: {
      max_lines_per_slide: settings.maxLinesPerSlide,
      max_chars_per_line: settings.maxCharsPerLine,
      lyrics_font_size: settings.lyricsFontSize,
    },
  }
  const data = await apiFetch<{ job_id: string }>('/api/exports/pptx', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return data.job_id
}

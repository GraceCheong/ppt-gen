import { apiFetch } from './client'

export interface WeeklyHistoryItem {
  week_end_date: string
  week_start_date: string
  updated_at_utc: string
  sequence_entries: { title: string; sequence: string }[]
  lyrics_by_title: Record<string, string>
  max_lines_per_slide: number
  max_chars_per_line: number
  lyrics_font_size: string | null
  worship_leader: string
  accompanist: string
  prayer_person: string
}

export async function fetchHistory(yearFrom = 2020): Promise<WeeklyHistoryItem[]> {
  const data = await apiFetch<{ items: WeeklyHistoryItem[] }>(
    `/api/history/weekly?year_from=${yearFrom}`
  )
  return data.items
}

export interface ManualEntry {
  title: string
  sequence: string
}

export async function saveHistoryEntry(
  weekEndDate: string,
  entries: ManualEntry[]
): Promise<{ week_end_date: string }> {
  return apiFetch('/api/history/weekly', {
    method: 'POST',
    body: JSON.stringify({ week_end_date: weekEndDate, sequence_entries: entries }),
  })
}

export async function updateHistoryEntry(
  weekEndDate: string,
  payload: { password: string; sequence_entries: ManualEntry[] }
): Promise<void> {
  await apiFetch(`/api/history/weekly/${weekEndDate}/entries`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function updateHistoryRoles(
  weekEndDate: string,
  payload: { password: string; worship_leader: string; accompanist: string; prayer_person: string }
): Promise<void> {
  await apiFetch(`/api/history/weekly/${weekEndDate}/roles`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

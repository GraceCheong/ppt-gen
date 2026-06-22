export interface SongEntry {
  id: string
  title: string
  sequence: string
  lyrics: string
  /** 가사가 없어도 되는 파트 목록. undefined이면 DEFAULT_NO_LYRICS_PARTS로 판단 */
  noLyricsParts?: string[]
}

/** I, Inter는 기본적으로 가사 불필요 */
export const DEFAULT_NO_LYRICS_PARTS = new Set(['I', 'Inter'])

export function getUniqueParts(sequence: string): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const p of sequence.split('-').filter(Boolean)) {
    if (!seen.has(p)) { seen.add(p); result.push(p) }
  }
  return result
}

export function isPartNoLyrics(song: SongEntry, part: string): boolean {
  if (song.noLyricsParts !== undefined) return song.noLyricsParts.includes(part)
  return DEFAULT_NO_LYRICS_PARTS.has(part)
}

/** 파트가 가사에 존재하는지만 확인 (내용 유무 무관) */
export function partExistsInLyrics(lyrics: string, part: string): boolean {
  return lyrics.split('\n').some(l => l.trim().toLowerCase() === part.toLowerCase())
}

/**
 * 파트의 가사 상태를 반환합니다.
 * - 'missing'     : 파트 이름 줄 자체가 없음
 * - 'empty'       : 파트 이름은 있지만 가사 내용이 없음
 * - 'has-content' : 파트 이름 아래 내용이 있음
 *
 * allParts 는 시퀀스에서 추출한 유니크 파트 목록으로,
 * 다음 파트 헤더를 인식해 구간 끝을 찾는 데 사용합니다.
 */
export function getLyricsSectionStatus(
  lyrics: string,
  part: string,
  allParts: string[],
): 'missing' | 'empty' | 'has-content' {
  const lines = lyrics.split('\n')
  const partLower = part.toLowerCase()
  const allPartsLower = new Set(allParts.map(p => p.toLowerCase()))

  const foundIndex = lines.findIndex(l => l.trim().toLowerCase() === partLower)
  if (foundIndex === -1) return 'missing'

  for (let i = foundIndex + 1; i < lines.length; i++) {
    const trimmed = lines[i].trim()
    if (!trimmed) continue
    if (allPartsLower.has(trimmed.toLowerCase())) return 'empty'
    return 'has-content'
  }

  return 'empty'
}

export interface PptSettings {
  maxLinesPerSlide: number
  maxCharsPerLine: number
  lyricsFontSize: number | null
}

export const DEFAULT_SETTINGS: PptSettings = {
  maxLinesPerSlide: 2,
  maxCharsPerLine: 18,
  lyricsFontSize: null,
}

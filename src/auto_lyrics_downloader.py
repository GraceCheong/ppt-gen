import os
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# 1. Web Crawler Function
# ==========================================

def fetch_lyrics_from_bugs(song_title, log_func=print):
    """
    Crawl lyrics through Bugs search.
    """
    import urllib.parse
    
    query = urllib.parse.quote(song_title)
    search_url = f"https://music.bugs.co.kr/search/track?q={query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. Search for the song on Bugs
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the link to the detail page of the first track
        track_link_elem = soup.select_one('a.trackInfo')
        if not track_link_elem or not track_link_elem.get('href'):
            return None
            
        track_url = track_link_elem.get('href')
        
        # 2. Extract lyrics from the track detail page
        res_track = requests.get(track_url, headers=headers)
        res_track.raise_for_status()
        
        soup_track = BeautifulSoup(res_track.text, 'html.parser')
        
        # Bugs usually preserves lyrics with original line breaks in the <xmp> tag!
        xmp_elem = soup_track.select_one('xmp')
        
        if xmp_elem:
            raw_text = xmp_elem.get_text().strip()
            
            # 1. Split into lines and strip each line
            lines = [line.strip() for line in raw_text.splitlines()]
            
            # 2. Collapse multiple blank lines into at most one blank line
            cleaned_lines = []
            for line in lines:
                if line:
                    cleaned_lines.append(line)
                elif cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
            
            return "\n".join(cleaned_lines).strip()
            
    except Exception as e:
        log_func(f"[오류] 벅스 크롤링 중 오류가 발생했습니다: {e}")
        
    return None

# ==========================================
# 2. Main Execution
# ==========================================

def download_missing_lyrics(song_titles, existing_lyrics=None, log_func=print, delay_seconds=1.5):
    """Download lyrics for songs not in existing_lyrics. Returns {title: text} dict."""
    log_func("====================================")
    log_func("가사 자동 다운로드")
    log_func("====================================")

    existing = existing_lyrics or {}
    song_titles = [t.strip() for t in song_titles if t.strip()]

    if not song_titles:
        log_func("[오류] 다운로드할 곡 제목이 없습니다.")
        return {}

    results = {}
    found_missing = False

    for song_title in song_titles:
        if song_title in existing and existing[song_title].strip():
            log_func(f"[안내] '{song_title}' 가사가 이미 있어 건너뜁니다.")
            continue

        found_missing = True
        log_func(f"[확인] '{song_title}' 가사를 다운로드합니다.")
        lyrics_text = fetch_lyrics_from_bugs(song_title, log_func=log_func)

        if lyrics_text:
            results[song_title] = lyrics_text
            log_func(f"[완료] '{song_title}' 가사를 가져왔습니다.\n")
        else:
            log_func(f"[안내] '{song_title}' 가사를 자동으로 찾지 못했습니다. 직접 입력해 주세요.\n")

        time.sleep(delay_seconds)

    if not found_missing:
        log_func("\n[완료] 모든 곡의 가사가 이미 있습니다.")
    else:
        log_func("\n[완료] 가사 다운로드 작업이 끝났습니다. 가사 내용을 확인하세요.")

    return results

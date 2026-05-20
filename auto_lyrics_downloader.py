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

def read_song_titles_from_sequence_file(sequence_file):
    with open(sequence_file, "r", encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    # Parse sequences in pairs of [Title, Sequence].
    return lines[0::2]


def download_missing_lyrics(song_titles=None, base_dir=None, log_func=print, delay_seconds=1.5):
    log_func("====================================")
    log_func("가사 자동 다운로드")
    log_func("====================================")
    
    script_dir = base_dir or os.path.dirname(os.path.abspath(__file__))

    if song_titles is None:
        sequence_file = os.path.join(script_dir, "sequences.txt")
        if not os.path.exists(sequence_file):
            log_func(f"[오류] '{sequence_file}' 파일이 없습니다.")
            return

        song_titles = read_song_titles_from_sequence_file(sequence_file)
    else:
        song_titles = [title.strip() for title in song_titles if title.strip()]

    if not song_titles:
        log_func("[오류] 다운로드할 곡 제목이 없습니다.")
        return

    found_missing = False
    
    for song_title in song_titles:
        lyrics_file = os.path.join(script_dir, f"{song_title}.txt")
        
        # Attempt download if lyrics file is missing or empty!
        needs_download = False
        
        if not os.path.exists(lyrics_file):
            needs_download = True
            log_func(f"[확인] '{lyrics_file}' 파일이 없어 다운로드합니다.")
        else:
            # Check if file exists but is empty
            with open(lyrics_file, 'r', encoding='utf-8') as chk_f:
                if not chk_f.read().strip():
                    needs_download = True
                    log_func(f"[확인] '{lyrics_file}' 파일이 비어 있어 다운로드합니다.")
                    
        if needs_download:
            found_missing = True
            lyrics_text = fetch_lyrics_from_bugs(song_title, log_func=log_func)
            
            if lyrics_text:
                with open(lyrics_file, "w", encoding="utf-8") as out_f:
                    out_f.write(lyrics_text)
                log_func(f"[완료] '{song_title}' 가사를 '{lyrics_file}'에 저장했습니다.\n")
            else:
                log_func(f"[안내] '{song_title}' 가사를 자동으로 찾지 못했습니다. 직접 입력해 주세요.\n")
                
            # Short delay to prevent server overload and blocks
            time.sleep(delay_seconds) 
        else:
            log_func(f"[안내] '{lyrics_file}' 파일이 이미 준비되어 있어 건너뜁니다.")

    if not found_missing:
        log_func("\n[완료] 모든 곡의 가사 파일이 이미 준비되어 있습니다.")
    else:
        log_func("\n[완료] 가사 다운로드 작업이 끝났습니다. 가사 파일 내용을 확인하세요.")

if __name__ == "__main__":
    download_missing_lyrics()

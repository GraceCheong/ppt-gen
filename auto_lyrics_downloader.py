import os
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# 1. Web Crawler Function
# ==========================================

def fetch_lyrics_from_bugs(song_title):
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
            return xmp_elem.get_text().strip()
            
    except Exception as e:
        print(f"⚠️ 벅스 크롤링 중 오류 발생: {e}")
        
    return None

# ==========================================
# 2. Main Execution
# ==========================================

def download_missing_lyrics():
    print("====================================")
    print("   Lyrics Auto-Downloader")
    print("====================================")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sequence_file = os.path.join(script_dir, "sequences.txt")
    if not os.path.exists(sequence_file):
        print(f"❌ '{sequence_file}' 파일이 없습니다. 먼저 생성해주세요.")
        return

    with open(sequence_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        
    # Parse sequences.txt in pairs of [Title, Sequence]
    found_missing = False
    
    for i in range(0, len(lines), 2):
        song_title = lines[i]
        lyrics_file = os.path.join(script_dir, f"{song_title}.txt")
        
        # Attempt download if lyrics file is missing or empty!
        needs_download = False
        
        if not os.path.exists(lyrics_file):
            needs_download = True
            print(f"🔍 '{lyrics_file}' 파일이 없습니다. 새로 다운로드합니다...")
        else:
            # Check if file exists but is empty
            with open(lyrics_file, 'r', encoding='utf-8') as chk_f:
                if not chk_f.read().strip():
                    needs_download = True
                    print(f"🔍 '{lyrics_file}' 파일이 비어있습니다. 새로 다운로드합니다...")
                    
        if needs_download:
            found_missing = True
            lyrics_text = fetch_lyrics_from_bugs(song_title)
            
            if lyrics_text:
                with open(lyrics_file, "w", encoding="utf-8") as out_f:
                    out_f.write(lyrics_text)
                print(f"✅ '{song_title}' 가사 다운로드 및 '{lyrics_file}' 저장 완료!\n")
            else:
                print(f"❌ '{song_title}' 가사를 자동으로 찾을 수 없습니다. 직접 텍스트 파일을 채워주세요.\n")
                
            # Short delay to prevent server overload and blocks
            time.sleep(1.5) 
        else:
            print(f"⏭️ '{lyrics_file}' 파일이 이미 있고 내용도 있습니다. (스킵)")

    if not found_missing:
        print("\n🎉 모든 곡의 가사 파일이 이미 준비되어 있습니다!")
    else:
        print("\n작업이 완료되었습니다. 확인 후 'python lyrics_to_ppt.py'를 실행하세요.")

if __name__ == "__main__":
    download_missing_lyrics()

# Lyrics PowerPoint Generator 🎶

A robust and fully automated python tool that scrapes, parses, and formats song lyrics into beautiful Microsoft PowerPoint (`.pptx`) slides based on user-provided song sequences.

## 🌟 Features
- **Auto-Downloader**: Automatically crawls Bugs Music to find and save missing lyrics.
- **Dynamic Slide Formatting**: Automatically manages slide chunks (1 or 2 lines per slide) depending on the length of the lyrics to prevent overcrowded "text lumps". 
- **Sequence Mapping**: Rearranges the lyrics dynamically based on sequence tags (e.g., `I-V1-V2-C-Inter-C-Out`).
- **Template Theming**: Uses your custom `template.pptx` file to extract predefined "Title" and "Lyrics" master slides.

---

## 🛠️ How to Use (사용 방법)

### 🇺🇸 English Guide
1. **Prepare Template**: Ensure `template.pptx` is in the same directory. The template must have a layout named "Title" and "Lyrics" in its master slides.
2. **Define Sequence**: Edit `sequences.txt` in the folder. Format it in pairs of lines: the first line for the Song Title, and the second line for the sequence (e.g., `I-V1-C`).
3. **Prepare Lyrics Files**: Create `[Song Title].txt` files and write out the lyrics under section headers (`V1`, `C`, etc.).
   > 💡 **Tip for Beautiful Slides**: The program dynamically splits lines based on their length. For the absolute best and most beautiful slide results, format the raw lyrics nicely in your text file by breaking them structurally beforehand! The better your text file lines look, the better the PPT will look.
4. **Run Downloader (Optional)**: Run `python auto_lyrics_downloader.py`. The tool will read `sequences.txt` and automatically download lyrics for any songs missing `.txt` files in the directory.
5. **Generate PPT**: Run `python lyrics_to_ppt.py`. The tool will read all your files and automatically output a fully assembled `integrated_lyrics.pptx` containing all the ordered slides for your setlist!

### 🇰🇷 한글 사용법
1. **템플릿 준비**: 스크립트와 같은 폴더에 `template.pptx` 파일을 준비합니다. 파일 안에 "제목(Title)" 과 "가사(Lyrics)" 이름을 가진 쓸모있는 레이아웃이 마스터 슬라이드로 지정되어 있어야 합니다.
2. **시퀀스(콘티) 작성**: `sequences.txt` 파일에 곡 제목과 진행 순서(시퀀스)를 위아래 2줄 단위로 작성합니다. (예시: `I-V1-C`)
3. **가사 파일 세팅**: `[곡 제목].txt` 형식으로 가사 파일을 만들고, 각 파트(`V1`, `C` 등) 아래에 가사를 입력합니다.
   > 💡 **예쁜 슬라이드를 위한 꿀팁**: 이 프로그램이 각 줄의 길이를 계산해 최적의 비율로 슬라이드를 자동 분할합니다. 다만 최종 결과물을 훨씬 더 예쁘게 나오게 하고 싶으시다면, 제일 처음 가사 텍스트(`.txt`) 파일 안의 문장들을 본인이 원하는 만큼 적당하고 알맞게 길이를 끊어 내려쓰기(줄바꿈) 해두시는 것이 좋습니다! 원본 텍스트가 잘 정돈되어 있을수록 PPT가 예쁘게 만들어집니다.
4. **자동 다운로더 실행 (선택)**: `python auto_lyrics_downloader.py`를 실행하세요. `sequences.txt`에 적혀있지만 아직 가사(`.txt`) 파일이 없는 곡이 있다면, 벅스(Bugs)에 찾아가 자동으로 가사를 긁어와 저장해 줍니다.
5. **PPT 자동 제작 개시!**: `python lyrics_to_ppt.py` 를 실행하세요. 완성된 PPT 슬라이드가 들어있는 최종본 파일인 `integrated_lyrics.pptx` 가 자동으로 생성됩니다!

---

## 📋 File Structure
- `auto_lyrics_downloader.py`: Web scraper for pulling lyrics from Bugs Music.
- `lyrics_to_ppt.py`: Core algorithm to process logic and generate the final PowerPoint.
- `template.pptx`: The visual theme layout dependency.
- `sequences.txt`: Batch processing queue representing your worship setlist.

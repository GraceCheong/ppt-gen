# 🎵 Auto Lyrics PPT Generator
> **단 클릭(명령어) 몇 번으로, 모든 예배 곡의 가사 PPT를 한 번에 자동 완성하세요!**

코딩을 전혀 모르셔도 괜찮습니다. 준비된 텍스트 파일과 템플릿만 있으면 파이썬(Python) 프로그램이 알아서 **간주, 전주, 글자 크기, 줄바꿈 비율**을 계산하여 가장 깔끔하고 일관된 PPT 파일 1개를 뚝딱 만들어 줍니다.

---

## 🛠️ 한글 사용 가이드 (초보자용)

### 1️⃣ 템플릿 파일 준비 (`template.pptx`)
스크립트가 있는 폴더 안에 평소 사용하시는 **예배 PPT 템플릿 파일**을 넣어주세요.
> *주의사항*: 파워포인트 상단의 [보기] - [슬라이드 마스터]에 들어가서, **"제목"**이라는 이름이 들어간 레이아웃과 **"가사"**라는 이름이 들어간 레이아웃이 꼭 따로 있는지 확인해주세요! 프로그램이 이곳을 똑똑하게 찾아내어 가사를 집어넣습니다.

### 2️⃣ 곡 순서 정하기 (`sequences.txt`)
예배 콘티 순서를 메모장으로 만들어 `sequences.txt` 라는 이름으로 저장해 주세요. 아래처럼 항상 두 줄 단위로 세트가 되게 적어주시면 됩니다:
```text
주를 바라보며
I-A-B-Inter-A-B-B'-Bridge-B''-Out
하늘의 것을 구하게 하소서
I-V1-V2-C-C-Out
```

### 3️⃣ 가사 준비하기 (`[곡 제목].txt`)
콘티에 있는 노래들의 가사 파일을 준비해 주세요. `주를 바라보며.txt` 처럼 파일을 만들고, `V1`, `C` 등의 파트 이름 아래에 엔터를 쳐가며 가사를 적어두면 됩니다.

> 💡 **진짜 중요한 "꿀팁"! (가사 예쁘게 뽑기)**
> 이 프로그램은 가사가 화면에 뭉텅이로 꽉 차서 숨막혀 보이는 것을 방지하기 위해, **"긴 문장"은 단독 1줄 슬라이드로, "짧은 문장"은 2줄 슬라이드로** 예쁘게 묶어주는 스마트한 인공지능이 담겨 있습니다.
> 
> 가장 예쁜 PPT를 만들고 싶으신가요? 
> **애초에 메모장에 가사를 적으실 때, 호흡이 끊어지는 구간에서 "엔터(줄바꿈)"를 적당히 쳐서 예쁘게 저장해 두세요!** 원본 텍스트 파일이 정돈되어 있을수록 프로그램이 읽어들이는 PPT 결과물도 환상적으로 만들어집니다.

### 4️⃣ 가사 자동 다운로드 (귀찮으신 분들을 위한 선택 기능!)
일일이 가사 파일을 만들기 귀찮으신가요? 까만 터미널 창(cmd 기호)에 아래 명령어를 치고 엔터를 쳐보세요!
```bash
python auto_lyrics_downloader.py
```
프로그램이 `sequences.txt` 목록을 읽고, 부족한 노래의 가사 파일을 **벅스(Bugs) 사이트에서 알아서 찾아내어 자동으로 텍스트 파일로 저장** 해줍니다!

### 5️⃣ PPT 만들기 (최종 결과물 뽑기)
자, 이제 모든 준비가 끝났습니다. 아래 명령어를 터미널에서 실행하세요!
```bash
python lyrics_to_ppt.py
```
불과 1~2초 뒤에 폴더 안에 짠! 🎁 **`integrated_lyrics.pptx`** 라는 최종 PPT 파일이 완성됩니다. 열어서 바로 예배에 사용하세요!

---

## 🇺🇸 English Guide (For Non-Coders!)

A completely hands-free lyrics generation tool! This software intelligently calculates sentence lengths to prevent overcrowded text blocks and outputs a beautifully formatted `.pptx` presentation.

### Step-by-Step Guide
1. **`template.pptx`**: Ensure this file exists in your folder. Inside PowerPoint's slide master, you must have layouts named "Title" and "Lyrics" respectively.
2. **`sequences.txt`**: This files dictates your setlist order. Format it in pairs: Song name on line 1, and the music progression (e.g., `I-V1-C`) on line 2.
3. **`[Song Name].txt`**: Place your lyric files here formatted under headers like `V1` and `C`.
   > 💡 **Tip for beautiful slides**: The formatting engine uses smart line-length logic. For the most astonishing slide results, format the raw text file beautifully by breaking lines sensibly with 'Enter' beforehand! 
4. **Auto Download**: Run `python auto_lyrics_downloader.py` in your terminal to instantly scrape any randomly missing lyrics off the web.
5. **BUILD!**: Run `python lyrics_to_ppt.py`. Everything will automatically compile into **`integrated_lyrics.pptx`** flawlessly.

# 🎵 Auto Lyrics PPT Generator
> **단 클릭(명령어) 몇 번으로, 모든 예배 곡의 가사 PPT를 한 번에 자동 완성해 보세요!**

코딩을 전혀 몰라도 괜찮아요. 준비된 텍스트 파일과 템플릿만 있으면 파이썬(Python) 프로그램이 알아서 **간주, 전주, 글자 크기, 줄바꿈 비율**을 계산해서 가장 깔끔하고 일관된 PPT 파일 1개를 뚝딱 만들어 줘요.

---

## 🛠️ 한글 사용 가이드

### 1️⃣ 템플릿 파일 준비 (`template.pptx`)
스크립트가 있는 폴더 안에 평소에 사용하는 **예배 PPT 템플릿 파일**을 넣어 주세요.

> ⚠️ 마스터 슬라이드에 들어가서, "제목" 레이아웃과 "가사" 레이아웃이 꼭 따로 있는지 확인해 주세요! <br> 프로그램이 알아서 가사를 쏙 집어넣어요.

### 2️⃣ 곡 순서 정하기 (`sequences.txt`)
예배 콘티 순서를 메모장으로 만들어 `sequences.txt` 라는 이름으로 저장해 주거나, 폴더 안의 파일을 수정해주세요. <br>
아래처럼 항상 두 줄 단위를 세트로 묶어서 적어주면 돼요:

```text
주를 바라보며
I-A-B-Inter-A-B-B'-Bridge-B''-Out
하늘의 것을 구하게 하소서
I-V1-V2-C-C-Out
```

<br>

### 3️⃣ 가사 준비하기 (`[곡 제목].txt`)
콘티에 있는 노래들의 가사 파일을 준비해 주세요. <br>
`주를 바라보며.txt` 처럼 파일을 만들고, `V1`, `C` 등 파트 이름 아래에 엔터를 쳐가며 가사를 적어두면 끝이에요.

> 💡 **진짜 중요한 "꿀팁"! (가사 예쁘게 뽑기)**
> 이 프로그램은 가사가 화면에 뭉텅이로 꽉 차서 답답해 보이는 걸 막아주기 위해, "긴 문장"은 단독 1줄 슬라이드로, "짧은 문장"은 2줄 슬라이드로 예쁘게 묶어주는 스마트한 기능이 들어가 있어요.

<br>

> 예쁜 PPT를 만들고 싶나요? 
> 메모장에 가사를 적을 때, 호흡이 끊어지는 구간에서 "엔터(줄바꿈)"를 적당히 쳐서 예쁘게 저장해 두세요! <br>
> 원본 텍스트 파일이 잘 정돈되어 있을수록 프로그램이 만들어내는 PPT 결과물도 훨씬 예뻐집니다.

### 4️⃣ 가사 자동 다운로드 (귀찮다면 선택하세요!)
일일이 가사 파일을 만들기 귀찮나요? 까만 터미널 창(cmd 기호)에 아래 명령어를 입력하고 엔터를 쳐보세요!

```bash
python auto_lyrics_downloader.py
```

프로그램이 `sequences.txt` 목록을 읽고, 아직 가사(`.txt`) 파일이 없는 노래가 있다면 벅스(Bugs) 사이트에서 알아서 찾아내 텍스트 파일로 저장해 줘요!

### 5️⃣ PPT 만들기 (최종 결과물 뽑기)
자, 이제 모든 준비가 끝났어요. 아래 명령어를 터미널에서 실행해 보세요!
```bash
python lyrics_to_ppt.py
```
불과 1~2초 뒤에 폴더 안에 짠! 🎁 **`integrated_lyrics.pptx`** 라는 최종 PPT 파일이 완성돼요. <br>
이걸 열어서 바로 예배에 사용하면 됩니다!

---

## 🇺🇸 English Guide

### 1️⃣ Prepare the Template (`template.pptx`)
Ensure your usual **Worship PPT Template file** is placed inside the script folder.

> ⚠️ Please go into the Slide Master in PowerPoint and ensure you have specific layouts named **"Title"** and **"Lyrics"**! <br> The program smartly finds them to insert the lyrics.

### 2️⃣ Define Song Sequence (`sequences.txt`)
Create a notepad file named `sequences.txt` to dictate your setlist order, or edit the existing file. <br>
Write them in pairs (two lines per set) like this:

```text
주를 바라보며
I-A-B-Inter-A-B-B'-Bridge-B''-Out
하늘의 것을 구하게 하소서
I-V1-V2-C-C-Out
```

<br>

### 3️⃣ Prepare Lyrics Files (`[Song Title].txt`)
Prepare text files for the songs in your setlist. <br>
Create a file like `주를 바라보며.txt`, and simply type out the lyrics under part names like `V1` or `C`.

> 💡 **Crucial "Pro-Tip"! (How to get beautiful slides)**
> To prevent text from being crammed into an overcrowded lump, this program features a smart function that automatically bundles "Long sentences" into a single-line slide, and "Short sentences" into a two-line slide.

<br>

> Do you want the most beautiful PPT possible?
> When writing lyrics in your notepad, break the lines sensibly using "Enter" (line breaks) where pauses feel natural! <br>
> The cleaner and better-organized your original text file is, the more gorgeous your final PPT will be.

### 4️⃣ Auto Lyric Downloader (Optional, for convenience!)
Are you tired of manually creating lyrics files? Open your black terminal window (cmd), copy the command below, and hit Enter!

```bash
python auto_lyrics_downloader.py
```

The program will read the `sequences.txt` list, search the Bugs Music website for any missing lyrics, and automatically save them as text files for you!

### 5️⃣ Generate PPT (Final Output)
Now, everything is ready. Run the command below in your terminal!
```bash
python lyrics_to_ppt.py
```
After just 1~2 seconds, voilà! 🎁 A final fully assembled file named **`integrated_lyrics.pptx`** will be generated. <br>
Open it and it's ready for your worship service!

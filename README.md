# Auto Lyrics PPT Generator - Windows

예배 콘티와 가사 텍스트 파일을 읽어서 하나의 PowerPoint 파일로 만들어 주는 Windows용 도구입니다.

`LyricsToPPT.exe`를 실행하면 GUI 창이 열리고, 같은 폴더에 있는 `template.pptx`, `sequences.txt`, 가사 `.txt` 파일을 기준으로 PPT를 생성합니다.

## 빠른 시작

1. 이 폴더에 아래 파일들이 있는지 확인합니다.

```text
LyricsToPPT.exe
template.pptx
sequences.txt
각 곡 제목.txt
```

2. `sequences_sample.txt`를 복사해서 `sequences.txt`로 만들거나, 기존 `sequences.txt`를 수정합니다.

3. 곡 제목과 같은 이름의 가사 파일을 준비합니다.

```text
한나의 노래.txt
나의 하나님.txt
함께 지어져 가네.txt
우리 함께 기도해.txt
```

4. `LyricsToPPT.exe`를 더블클릭합니다.

5. 필요한 설정을 확인한 뒤 `Generate PPT` 버튼을 누릅니다.

6. 생성된 `out/integrated_lyrics.pptx` 파일을 PowerPoint에서 엽니다.

## 파일 구성

### `template.pptx`

PPT 생성에 사용할 템플릿 파일입니다. 반드시 `LyricsToPPT.exe`와 같은 폴더에 있어야 합니다.

PowerPoint의 슬라이드 마스터에 아래 레이아웃이 준비되어 있어야 합니다.

```text
Title
Lyrics
```

프로그램은 이 레이아웃을 찾아 제목 슬라이드와 가사 슬라이드를 만듭니다.

### `sequences.txt`

예배 곡 순서와 각 곡의 진행 순서를 적는 파일입니다. 두 줄이 한 곡입니다.

```text
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
```

첫 번째 줄은 곡 제목이고, 두 번째 줄은 사용할 파트 순서입니다.

### 가사 파일

각 곡의 가사는 `[곡 제목].txt` 형식으로 저장합니다.

예를 들어 `sequences.txt`에 `한나의 노래`가 있으면, 같은 폴더에 아래 파일이 필요합니다.

```text
한나의 노래.txt
```

가사 파일 안에는 파트 이름을 먼저 쓰고, 그 아래에 가사를 적습니다. 파트 사이에는 빈 줄을 하나 넣습니다.

```text
V1
가사 첫 번째 줄
가사 두 번째 줄

C
후렴 첫 번째 줄
후렴 두 번째 줄
```

`sequences.txt`에서 `V1`, `C`, `Inter`, `Out`처럼 적은 파트 이름과 가사 파일의 파트 이름이 맞아야 합니다.

## GUI 설정

`LyricsToPPT.exe`를 실행하면 아래 설정을 바꿀 수 있습니다.

### Max lines per slide

한 슬라이드에 들어갈 최대 줄 수입니다. 기본값은 `2`입니다.

### Long Line Threshold

긴 줄로 판단할 글자 수 기준입니다. 기본값은 `18`입니다.

긴 문장이 많으면 프로그램이 한 슬라이드에 너무 많은 줄을 넣지 않도록 조정합니다.

## 결과 파일

`sequences.txt`가 있으면 모든 곡을 합쳐서 `out/` 폴더 안에 아래 파일을 생성합니다.

```text
out/integrated_lyrics.pptx
```

`sequences.txt`가 없으면 프로그램이 단일 곡 모드로 동작하며, 곡 제목과 진행 순서를 직접 입력받습니다. 이 경우 결과 파일은 `out/[곡 제목].pptx`로 저장됩니다.

## 가사 자동 다운로드

가사 파일을 직접 만들기 어렵다면 Python으로 자동 다운로드 스크립트를 실행할 수 있습니다.

먼저 Windows 터미널 또는 PowerShell에서 필요한 패키지를 설치합니다.

```powershell
pip install requests beautifulsoup4
```

그 다음 아래 명령어를 실행합니다.

```powershell
python auto_lyrics_downloader.py
```

스크립트는 `sequences.txt`에 있는 곡 목록을 읽고, 없는 가사 `.txt` 파일을 Bugs에서 찾아 저장합니다.

자동 다운로드 결과는 사이트 검색 결과에 따라 다를 수 있으므로, 생성된 가사 파일은 반드시 한 번 확인하세요.

## Python으로 직접 실행하기

개발용으로 Python 스크립트를 직접 실행할 수도 있습니다.

필요한 패키지를 설치합니다.

```powershell
pip install python-pptx requests beautifulsoup4
```

PPT 생성 GUI를 실행합니다.

```powershell
python lyrics_to_ppt.py
```

## Windows에서 자주 생기는 문제

### `template.pptx`를 찾을 수 없다고 나오는 경우

`template.pptx`가 `LyricsToPPT.exe`와 같은 폴더에 있는지 확인하세요.

### 가사 파일을 찾을 수 없다고 나오는 경우

`sequences.txt`의 곡 제목과 가사 파일명이 완전히 같은지 확인하세요.

예:

```text
sequences.txt: 한나의 노래
가사 파일명: 한나의 노래.txt
```

띄어쓰기까지 같아야 합니다.

### PPT 저장에 실패하는 경우

생성하려는 `out/integrated_lyrics.pptx` 파일이 PowerPoint에서 열려 있으면 저장에 실패할 수 있습니다. 열려 있는 PPT 파일을 닫고 다시 실행하세요.

### Windows 보안 경고가 나오는 경우

처음 실행할 때 Windows SmartScreen 경고가 나올 수 있습니다. 프로젝트에서 직접 빌드한 실행 파일이라면 `추가 정보`를 누른 뒤 실행할 수 있습니다.

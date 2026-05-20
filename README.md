# PO,RR

예배 레파토리와 가사 텍스트 파일을 읽어서 하나의 PowerPoint 파일로 만들어 주는 Windows용 도구입니다.

`LyricsToPPT.exe`를 실행하면 작업 표시줄과 창 제목에는 `PO,RR by a tempo`가 표시되고, 프로그램 화면에는 `PO,RR`가 표시됩니다. 같은 폴더에 있는 `template.pptx`와 가사 `.txt` 파일을 기준으로 파워포인트를 생성하며, 곡 순서와 진행 순서는 `레파토리 입력` 창에 직접 입력합니다.

## 빠른 시작

1. 이 폴더에 아래 파일들이 있는지 확인합니다.

```text
LyricsToPPT.exe
template.pptx
assets/atempo.png
각 곡 제목.txt
```

2. `LyricsToPPT.exe`를 더블클릭합니다.

3. `레파토리 입력` 창에 곡 제목과 진행 순서를 두 줄씩 입력합니다.

```text
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
```

4. `레파토리 인식` 버튼을 누른 뒤 곡 목록에서 가사를 수정할 곡을 선택합니다.

5. 곡 제목과 같은 이름의 가사 파일을 준비하거나, `가사 다운로드` 버튼으로 자동 다운로드합니다. 가사 편집창에서 수정한 내용은 자동으로 저장됩니다.

```text
한나의 노래.txt
나의 하나님.txt
함께 지어져 가네.txt
우리 함께 기도해.txt
```

6. 필요한 설정을 확인한 뒤 `파워포인트 생성` 버튼을 누릅니다.

7. 생성된 `out/integrated_lyrics.pptx` 파일을 PowerPoint에서 엽니다.

## 파일 구성

```text
lyrics_to_ppt.py
auto_lyrics_downloader.py
build_release.py
LyricsToPPT.spec
assets/
  atempo.png
  background.png
docs/
tests/
template.pptx
sequences_sample.txt
```

### `template.pptx`

파워포인트 생성에 사용할 템플릿 파일입니다. 반드시 `LyricsToPPT.exe`와 같은 폴더에 있어야 합니다.

PowerPoint의 슬라이드 마스터에 아래 레이아웃이 준비되어 있어야 합니다.

```text
제목
가사
```

프로그램은 이 레이아웃을 찾아 제목 슬라이드와 가사 슬라이드를 만듭니다.

### `assets/atempo.png`

프로그램 창 아이콘으로 사용하는 이미지 파일입니다. 실행 파일과 함께 배포할 때는 `assets/atempo.png` 경로를 유지합니다.

### `assets/background.png`

프로그램 배경으로 사용하는 이미지 파일입니다. 실행 파일과 함께 배포할 때는 `assets/background.png` 경로를 유지합니다.

### 레파토리 입력

예배 곡 순서와 각 곡의 진행 순서를 실행 창에 직접 입력합니다. 두 줄이 한 곡입니다.

```text
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
```

첫 번째 줄은 곡 제목이고, 두 번째 줄은 사용할 파트 순서입니다. 기존 `sequences.txt` 파일을 사용하고 있었다면 파일 내용을 그대로 복사해서 입력창에 붙여 넣으면 됩니다. 같은 폴더에 `sequences.txt`가 있으면 시작할 때 자동으로 불러옵니다.

### 가사 파일

각 곡의 가사는 `[곡 제목].txt` 형식으로 저장합니다.

예를 들어 `레파토리 입력` 창에 `한나의 노래`가 있으면, 같은 폴더에 아래 파일이 필요합니다.

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

`레파토리 입력` 창에서 `V1`, `C`, `Inter`, `Out`처럼 적은 파트 이름과 가사 파일의 파트 이름이 맞아야 합니다.

## 화면 구성

### 레파토리 인식

`레파토리 입력` 창의 내용을 읽어 오른쪽 곡 목록을 만듭니다. 곡을 선택하면 같은 폴더의 `[곡 제목].txt` 파일을 불러와 바로 수정할 수 있습니다.

가사 파일이 없거나 비어 있으면 가사 편집창에 입력 형식 가이드가 표시됩니다.

### 가사 자동 저장

선택한 곡의 가사는 입력을 잠시 멈추면 `[곡 제목].txt` 파일로 자동 저장됩니다. 다른 곡을 선택하거나 파워포인트를 만들 때도 현재 편집 중인 가사를 먼저 저장합니다.

### 생성 설정

`슬라이드당 줄 수`는 한 슬라이드에 들어갈 최대 줄 수입니다. 기본값은 `2`입니다. 예를 들어 `4`로 설정하면 가사도 4줄 기준으로 나눕니다.

## 결과 파일

입력한 모든 곡을 합쳐서 `out/` 폴더 안에 아래 파일을 생성합니다.

```text
out/integrated_lyrics.pptx
```

## 가사 자동 다운로드

가사 파일을 직접 만들기 어렵다면 실행 창에서 `가사 다운로드` 버튼을 누를 수 있습니다. 버튼은 `레파토리 입력` 창의 곡 제목을 읽고, 없는 가사 `.txt` 파일을 Bugs에서 찾아 저장합니다.

Python으로 직접 실행하는 경우 자동 다운로드 스크립트를 사용할 수도 있습니다.

먼저 Windows 터미널 또는 PowerShell에서 필요한 패키지를 설치합니다.

```powershell
pip install requests beautifulsoup4
```

그 다음 아래 명령어를 실행합니다.

```powershell
python auto_lyrics_downloader.py
```

스크립트는 `sequences.txt`가 있는 경우 해당 곡 목록을 읽고, 없는 가사 `.txt` 파일을 Bugs에서 찾아 저장합니다. 실행 파일에서는 `sequences.txt` 없이 GUI 입력값으로 다운로드할 수 있습니다.

자동 다운로드 결과는 사이트 검색 결과에 따라 다를 수 있으므로, 생성된 가사 파일은 반드시 한 번 확인하세요.

## Python으로 직접 실행하기

개발용으로 Python 스크립트를 직접 실행할 수도 있습니다.

필요한 패키지를 설치합니다.

```powershell
pip install python-pptx requests beautifulsoup4
```

파워포인트 생성 GUI를 실행합니다.

```powershell
python lyrics_to_ppt.py
```

## Windows에서 자주 생기는 문제

### `template.pptx`를 찾을 수 없다고 나오는 경우

`template.pptx`가 `LyricsToPPT.exe`와 같은 폴더에 있는지 확인하세요.

### 가사 파일을 찾을 수 없다고 나오는 경우

`레파토리 입력` 창의 곡 제목과 가사 파일명이 완전히 같은지 확인하세요.

예:

```text
레파토리 입력: 한나의 노래
가사 파일명: 한나의 노래.txt
```

띄어쓰기까지 같아야 합니다.

### 파워포인트 저장에 실패하는 경우

생성하려는 `out/integrated_lyrics.pptx` 파일이 PowerPoint에서 열려 있으면 저장에 실패할 수 있습니다. 열려 있는 파일을 닫고 다시 실행하세요.

### Windows 보안 경고가 나오는 경우

처음 실행할 때 Windows SmartScreen 경고가 나올 수 있습니다. 프로젝트에서 직접 빌드한 실행 파일이라면 `추가 정보`를 누른 뒤 실행할 수 있습니다.

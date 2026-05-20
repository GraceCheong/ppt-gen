# PO,RR

예배 레파토리와 가사를 입력해 하나의 PowerPoint 파일로 만들어 주는 Windows용 도구입니다.

`LyricsToPPT.exe`를 실행하면 작업 표시줄과 창 제목에는 `PO,RR by a tempo`가 표시되고, 프로그램 화면에는 `PO,RR`가 표시됩니다. `assets/template.pptx`를 기준으로 파워포인트를 생성하며, 곡 순서와 진행 순서는 `레파토리 입력` 창에 직접 입력합니다.

## 빠른 시작

1. 이 폴더에 아래 파일들이 있는지 확인합니다.

```text
LyricsToPPT.exe
assets/template.pptx
assets/atempo.png
```

2. `LyricsToPPT.exe`를 더블클릭합니다.

3. `레파토리 입력` 창에 곡 제목과 진행 순서를 두 줄씩 입력합니다.

```text
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
```

4. `레파토리 인식` 버튼을 누른 뒤 곡 목록에서 가사를 입력할 곡을 선택합니다.

5. 가사 편집창에 직접 입력하거나, `가사 다운로드` 버튼으로 자동으로 가져옵니다.

6. 필요한 설정을 확인한 뒤 `파워포인트 생성` 버튼을 누릅니다.

7. 생성된 `out/integrated_lyrics.pptx` 파일을 PowerPoint에서 엽니다.

## 파일 구성

```text
src/
  lyrics_to_ppt.py
  ppt_builder.py
  auto_lyrics_downloader.py
scripts/
  build_release.py
  LyricsToPPT.spec
assets/
  template.pptx
  atempo.png
  background.png
  sequences_sample.txt
tests/
docs/
requirements.txt
```

### `assets/template.pptx`

파워포인트 생성에 사용할 템플릿 파일입니다. 반드시 `assets/` 폴더 안에 있어야 합니다.

PowerPoint의 슬라이드 마스터에 아래 레이아웃이 준비되어 있어야 합니다.

```text
제목
가사
```

프로그램은 이 레이아웃을 찾아 제목 슬라이드와 가사 슬라이드를 만듭니다.

### `assets/atempo.png`

프로그램 창 아이콘으로 사용하는 이미지 파일입니다.

### `assets/background.png`

프로그램 배경으로 사용하는 이미지 파일입니다.

### 레파토리 입력

예배 곡 순서와 각 곡의 진행 순서를 실행 창에 직접 입력합니다. 두 줄이 한 곡입니다.

```text
한나의 노래
I-V1-V2-C-Inter-V2-C-C-Out
나의 하나님
I-V1-V1-C-Inter-V2-C-B-C-C
```

첫 번째 줄은 곡 제목이고, 두 번째 줄은 사용할 파트 순서입니다. `assets/sequences_sample.txt`에 형식 예시가 있습니다.

### 가사 입력

가사는 파일 없이 프로그램 안에서 직접 입력합니다. `레파토리 인식` 후 곡 목록에서 곡을 선택하면 오른쪽 편집창에 가사를 입력할 수 있습니다.

```text
V1
가사 첫 번째 줄
가사 두 번째 줄

C
후렴 첫 번째 줄
후렴 두 번째 줄
```

`레파토리 입력` 창에서 쓴 파트 이름(`V1`, `C`, `Inter`, `Out` 등)과 가사 편집창의 파트 이름이 맞아야 합니다. 입력한 가사는 프로그램이 열려 있는 동안 메모리에 유지됩니다.

## 화면 구성

### 레파토리 인식

`레파토리 입력` 창의 내용을 읽어 오른쪽 곡 목록을 만듭니다. 곡을 선택하면 가사 편집창이 활성화되어 바로 입력할 수 있습니다.

가사가 없으면 가사 편집창에 입력 형식 가이드가 표시됩니다.

### 생성 설정

`슬라이드당 줄 수`는 한 슬라이드에 들어갈 최대 줄 수입니다. 기본값은 `2`입니다. 예를 들어 `4`로 설정하면 가사도 4줄 기준으로 나눕니다.

## 결과 파일

입력한 모든 곡을 합쳐서 `out/` 폴더 안에 아래 파일을 생성합니다.

```text
out/integrated_lyrics.pptx
```

## 가사 자동 다운로드

가사를 직접 입력하기 어렵다면 `가사 다운로드` 버튼을 누를 수 있습니다. `레파토리 입력` 창의 곡 제목을 읽고, 가사가 없는 곡을 Bugs에서 찾아 편집창에 채워 넣습니다.

자동 다운로드 결과는 사이트 검색 결과에 따라 다를 수 있으므로, 내용을 반드시 한 번 확인하세요.

## Python으로 직접 실행하기

개발용으로 Python 스크립트를 직접 실행할 수도 있습니다.

필요한 패키지를 설치합니다.

```powershell
pip install -r requirements.txt
```

파워포인트 생성 GUI를 실행합니다.

```powershell
python src/lyrics_to_ppt.py
```

## Windows에서 자주 생기는 문제

### `template.pptx`를 찾을 수 없다고 나오는 경우

`assets/template.pptx`가 `LyricsToPPT.exe`와 같은 폴더의 `assets` 안에 있는지 확인하세요.

### 파워포인트 저장에 실패하는 경우

생성하려는 `out/integrated_lyrics.pptx` 파일이 PowerPoint에서 열려 있으면 저장에 실패할 수 있습니다. 열려 있는 파일을 닫고 다시 실행하세요.

### Windows 보안 경고가 나오는 경우

처음 실행할 때 Windows SmartScreen 경고가 나올 수 있습니다. 프로젝트에서 직접 빌드한 실행 파일이라면 `추가 정보`를 누른 뒤 실행할 수 있습니다.

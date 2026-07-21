# ForCPA

CPA 업무에 Python과 AI를 활용하는 방법을 학습하고, 실제로 사용할 수 있는 도구를 만드는 저장소입니다.

## 1. DART 핵심감사사항(KAM) 조회 도구

기업명 또는 종목코드로 최신 사업보고서를 찾고, DART 감사보고서에서 다음 내용을 보여주는 웹 도구입니다.

- 감사인(회계법인)
- 보고기간과 DART 접수번호
- 연결·별도 감사보고서 구분
- 핵심감사사항 제목과 선정 이유
- 감사인의 대응 내용
- 해당 DART 감사보고서 원문 링크

### 바로 사용하기

공개 앱: [https://forcpa-dart-kam.streamlit.app](https://forcpa-dart-kam.streamlit.app)

1. 기업명 또는 6자리 종목코드를 입력합니다.
2. **기업 찾기**를 누르고 조회할 기업을 확인합니다.
3. **최신 KAM 조회**를 누릅니다.
4. 감사인과 핵심감사사항 원문을 확인합니다.

## 동작 원리

```text
사용자 브라우저
    ↓
Streamlit Community Cloud (조회 화면과 문서 분석)
    ↓  DART_PROXY_TOKEN으로 인증
Vercel 서울 리전 (DART 요청 중계)
    ↓  DART_API_KEY로 호출
OpenDART API / DART 감사보고서
```

Streamlit Community Cloud에서 DART 직접 연결이 시간 초과되어, DART 요청만 Vercel 서울 리전이 대신 수행합니다. 친구나 일반 사용자는 인증키와 중계 토큰을 입력할 필요가 없습니다.

## 주요 파일

- `src/forcpa/dart/app.py`: Streamlit 조회 화면
- `src/forcpa/dart/api_client.py`: OpenDART 직접·중계 요청 처리
- `src/forcpa/dart/viewer.py`: 감사보고서 첨부와 본문 구간 선택
- `src/forcpa/dart/document_parser.py`: 감사인과 핵심감사사항 추출
- `api/dart_proxy.py`: Vercel 서울 중계 함수
- `vercel.json`: Vercel 서울 리전과 함수 실행 설정
- `tests/test_dart_kam_mvp.py`: 주요 기능과 보안 테스트

## 로컬 실행

PowerShell에서 다음 명령을 실행합니다.

```powershell
cd C:\Python_code\forcpa\ForCPA
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[web]"
Copy-Item .env.example .env
```

`.env` 파일을 열어 본인의 OpenDART 인증키를 입력합니다.

```dotenv
DART_API_KEY=발급받은_인증키
```

그 다음 앱을 실행합니다.

```powershell
& .\.venv\Scripts\python.exe -m streamlit run src\forcpa\dart\app.py
```

이미 `.venv`와 의존성이 설치되어 있다면 가상환경 생성과 설치 명령은 생략할 수 있습니다.

## 현재 클라우드 배포

### Streamlit Community Cloud

- 공개 주소: [https://forcpa-dart-kam.streamlit.app](https://forcpa-dart-kam.streamlit.app)
- 저장소: `jekim0725/ForCPA`
- 브랜치: `main`
- 실행 파일: `src/forcpa/dart/app.py`
- Python: `3.11`

Streamlit의 **App settings → Secrets**에는 중계 주소와 중계 토큰만 저장합니다.

```toml
DART_PROXY_URL = "https://for-cpa-inky.vercel.app/api/dart_proxy"
DART_PROXY_TOKEN = "Vercel에 등록한 것과 같은 임의 문자열"
```

### Vercel 서울 중계 서버

- 중계 주소: `https://for-cpa-inky.vercel.app/api/dart_proxy`
- 리전: 서울(`icn1`)

Vercel 프로젝트 환경변수에는 다음 두 값을 저장합니다.

```text
DART_API_KEY=OpenDART에서 발급받은 인증키
DART_PROXY_TOKEN=직접 생성한 긴 임의 문자열
```

`DART_PROXY_TOKEN`은 Streamlit 서버가 우리 Vercel 중계 서버에 접근할 때 사용하는 비밀번호입니다. 중계 함수는 토큰이 일치하는 요청만 받고, 코드에 허용된 OpenDART·DART 경로에만 접근합니다.

실제 인증키, 토큰, `.env` 파일은 GitHub에 커밋하지 않습니다.

## 캐시와 데이터 저장

- 조회 결과는 DART 접수번호별 JSON 캐시로 저장합니다.
- 같은 접수번호를 다시 조회하면 저장된 분석 결과를 재사용합니다.
- 조회할 때마다 최신 사업보고서 접수번호는 DART에서 다시 확인합니다.
- Streamlit Community Cloud의 로컬 파일은 재부팅이나 재배포 때 사라질 수 있습니다.
- 따라서 현재 캐시는 조회 속도를 위한 임시 저장이며, 영구 DB는 아닙니다.

영구적인 조회 이력, 사용자별 저장, 통계 기능이 필요해지면 별도 데이터베이스를 추가할 예정입니다.

## 테스트

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 설계 문서

- [간단 설계](docs/dart-kam-mvp-simple.md)
- [상세 PRD](docs/dart-kam-prd.md)

## 저장소 목표

- Python 데이터 처리 능력 복습
- Excel 기반 회계 업무 자동화
- 생성형 AI와 에이전트 개념 학습
- 회계 업무 프로젝트 설계 및 구현
- 학습과 문제 해결 과정을 GitHub에 기록

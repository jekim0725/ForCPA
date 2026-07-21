# ForCPA

CPA 도메인 지식과 AI 활용 역량을 결합하기 위한 학습 및 프로젝트 저장소입니다.

## 목표

- Python 데이터 처리 능력 복습
- Excel 기반 회계 업무 자동화
- 생성형 AI와 에이전트 개념 학습
- 회계 업무 프로젝트 설계 및 구현
- 학습과 문제 해결 과정을 GitHub에 기록

## 프로젝트

### 1. DART 핵심감사사항(KAM) 조회 도구

기업명 또는 종목코드로 최신 사업보고서를 찾고, DART 뷰어의 연결감사보고서 첨부에서 감사인과 핵심감사사항 원문을 조회합니다.

- OpenDART: 기업 고유번호와 최신 사업보고서 접수번호 조회
- DART 뷰어: 연결감사보고서 첨부와 독립된 감사인의 감사보고서 구간 선택
- 로컬 캐시: 접수번호별 결과를 `data/cache/dart/results/`에 JSON으로 저장
- 안전장치: KAM 없음, 파싱 실패, 수동 확인 필요 상태 구분

#### 실행 방법

```powershell
cd C:\Python_code\forcpa\ForCPA
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web]"
Copy-Item .env.example .env
# .env 파일에 DART_API_KEY 입력
streamlit run src\forcpa\dart\app.py
```

#### Streamlit Community Cloud 배포

- 저장소: `jekim0725/ForCPA`
- 브랜치: `main`
- 실행 파일: `src/forcpa/dart/app.py`
- Python: `3.11`

배포 화면의 **Advanced settings → Secrets**에 아래 형식으로 인증키를 등록합니다. 실제 인증키나 `.env` 파일은 GitHub에 커밋하지 않습니다.

```toml
DART_API_KEY = "발급받은_인증키"
```

- 간단 설계: [`docs/dart-kam-mvp-simple.md`](docs/dart-kam-mvp-simple.md)
- 상세 PRD: [`docs/dart-kam-prd.md`](docs/dart-kam-prd.md)

#### Vercel 서울 중계 서버 연결

Streamlit Cloud에서 DART 접속이 시간 초과될 때는 `api/dart_proxy.py`를 Vercel 서울 리전에 배포합니다.
Vercel 프로젝트 환경변수에는 다음 두 값을 등록합니다.

```text
DART_API_KEY=OpenDART에서 발급받은 인증키
DART_PROXY_TOKEN=직접 생성한 긴 임의 문자열
```

그 다음 Streamlit Community Cloud의 **Settings → Secrets**를 아래처럼 변경합니다.

```toml
DART_PROXY_URL = "https://Vercel프로젝트주소.vercel.app/api/dart_proxy"
DART_PROXY_TOKEN = "Vercel에 등록한 것과 같은 임의 문자열"
```

이 구성에서는 DART 인증키가 Vercel에만 저장되고, Streamlit 앱은 인증된 중계 요청만 보냅니다.
중계 함수는 코드에 허용된 OpenDART API와 DART 뷰어 경로 이외의 주소에는 접근할 수 없습니다.

## 학습 기록

학습 내용, 구현 과정, 오류와 해결 방법을 날짜별로 기록합니다.

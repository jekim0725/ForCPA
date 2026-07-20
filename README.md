\# ForCPA



CPA 도메인 지식과 AI 활용 역량을 결합하기 위한 학습 및 프로젝트 저장소입니다.



\## 목표



\- Python 데이터 처리 능력 복습

\- Excel 기반 회계 업무 자동화

\- 생성형 AI와 에이전트 개념 학습

\- 회계 업무 프로젝트 설계 및 구현

\- 학습과 문제 해결 과정을 GitHub에 기록



\## 프로젝트



\### 1. 감가상각 재계산 및 검증 도구



고정자산 명세를 입력받아 정액법 감가상각비를 재계산하고,

기장 금액과의 차이 및 입력 오류를 검토합니다.



\### 2. 감사 PBC 자료 검토 도구



감사 요청 자료의 제출 상태를 관리하고,

Excel 자료의 누락과 이상 항목을 검토합니다.



\## 학습 기록



학습 내용, 구현 과정, 오류와 해결 방법을 날짜별로 기록합니다.


## 3. DART 핵심감사사항(KAM) 조회 도구

기업명 또는 종목코드로 최신 사업보고서를 찾고, DART 뷰어의 연결감사보고서 첨부에서 감사인과 핵심감사사항 원문을 조회합니다.

- OpenDART: 기업 고유번호와 최신 사업보고서 접수번호 조회
- DART 뷰어: 연결감사보고서 첨부와 독립된 감사인의 감사보고서 구간 선택
- 로컬 캐시: 접수번호별 결과를 `data/cache/dart/results/`에 JSON으로 저장
- 안전장치: KAM 없음, 파싱 실패, 수동 확인 필요 상태 구분

### 실행 방법

```powershell
cd C:\Python_code\forcpa\ForCPA
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[web]"
Copy-Item .env.example .env
# .env 파일에 DART_API_KEY 입력
streamlit run src\forcpa\dart\app.py
```

- 간단 설계: [`docs/dart-kam-mvp-simple.md`](docs/dart-kam-mvp-simple.md)
- 상세 PRD: [`docs/dart-kam-prd.md`](docs/dart-kam-prd.md)


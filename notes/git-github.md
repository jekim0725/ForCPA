아래 내용을 메모장에 그대로 붙여 넣고 `notes\\git-github.md`로 저장하세요.



:::writing{variant="standard" id="41827"}

\# Git \& GitHub 학습 노트



\## 1. Repository



Repository(저장소)는 프로젝트의 파일과 변경 이력을 저장하는 공간이다.



\- 로컬 저장소: 내 컴퓨터에 있는 저장소

\- 원격 저장소: GitHub에 있는 저장소



현재 사용 중인 저장소:



\- 원격 저장소: `jekim0725/ForCPA`

\- 기본 브랜치: `main`

\- 공개 범위: Public



\---



\## 2. Clone



`clone`은 원격 저장소의 파일과 Git 이력을 내 컴퓨터로 처음 복제하고 연결하는 작업이다.



```powershell

git clone https://github.com/jekim0725/ForCPA.git

```



실행하면 현재 위치에 `ForCPA` 폴더가 만들어진다.



저장소를 처음 내려받을 때는 `clone`을 사용하고, 이후 GitHub의 새로운 변경사항만 받아올 때는 `pull`을 사용한다.



\---



\## 3. Status



`status`는 현재 저장소의 변경 상태를 확인하는 명령어다.



```powershell

git status

```



다음 내용을 확인할 수 있다.



\- 새로 생성된 파일

\- 수정된 파일

\- 삭제된 파일

\- 커밋 대상으로 선택된 파일

\- 아직 선택되지 않은 파일



파일을 커밋하기 전후에 `git status`로 상태를 확인하는 습관을 들인다.



\---



\## 4. Add



`add`는 변경사항 중 다음 커밋에 포함할 파일을 선택하는 작업이다.



특정 파일만 선택:



```powershell

git add README.md

```



여러 파일을 선택:



```powershell

git add README.md notes\\git-github.md

```



현재 폴더와 하위 폴더의 모든 변경사항 선택:



```powershell

git add .

```



`.`은 현재 폴더를 의미한다.



`git add .`는 원하지 않는 파일까지 포함할 수 있으므로 실행 전후에 `git status`를 확인한다.



\---



\## 5. Commit



`commit`은 `git add`로 선택한 변경사항을 로컬 Git 이력에 하나의 기록으로 저장하는 작업이다.



```powershell

git commit -m "docs: define learning roadmap"

```



\- `-m`은 커밋 메시지를 직접 입력한다는 의미다.

\- 커밋은 우선 내 컴퓨터의 로컬 저장소에 기록된다.

\- 커밋했다고 바로 GitHub에 올라가는 것은 아니다.

\- GitHub에 올리려면 `git push`가 필요하다.



좋은 커밋은 하나의 의미 있는 변경만 포함한다.



\---



\## 6. Push



`push`는 로컬 저장소에 생성한 커밋을 GitHub 원격 저장소로 전송하는 작업이다.



```powershell

git push

```



처음 브랜치를 연결하면서 푸시할 때는 다음 명령을 사용할 수 있다.



```powershell

git push -u origin main

```



`push`가 완료되면 GitHub 웹사이트에서 파일과 커밋 기록을 확인할 수 있다.



\---



\## 7. Pull



`pull`은 GitHub 원격 저장소의 새로운 변경사항을 로컬 저장소로 받아오는 작업이다.



```powershell

git pull

```



처음 저장소 전체를 내려받을 때는 `clone`, 이미 연결된 저장소를 최신 상태로 갱신할 때는 `pull`을 사용한다.



\---



\## 8. .gitignore



`.gitignore`는 Git이 추적하지 않아야 할 파일과 폴더를 지정하는 설정 파일이다.



주요 제외 대상:



\- `.env`: API 키와 환경변수

\- `.venv/`: Python 가상환경

\- `\_\_pycache\_\_/`: Python 캐시

\- `\*.pyc`: Python 컴파일 파일

\- `private-data/`: 실제 고객 또는 비공개 데이터

\- `.vscode/`: 개인 편집기 설정

\- `Thumbs.db`: Windows 시스템 파일



`.gitignore`에 등록하는 것만으로 이미 커밋된 파일이 삭제되는 것은 아니다. 민감정보는 처음부터 커밋하지 않아야 한다.



\---



\## 9. 커밋 메시지 태그



`docs:`, `feat:`, `fix:` 등은 Git의 특별한 기능이 아니다.



사람이 커밋의 성격을 쉽게 파악하기 위해 사용하는 관례적인 분류 태그다.



\### docs



README, 학습일지, 사용법 등 문서를 추가하거나 수정할 때 사용한다.



```text

docs: define learning roadmap

docs: add Git and GitHub learning notes

```



\### feat



새로운 기능을 추가할 때 사용한다.



```text

feat: calculate straight-line depreciation

feat: load fixed asset data from Excel

```



\### fix



오류를 수정할 때 사용한다.



```text

fix: handle missing acquisition dates

fix: reject zero useful life

```



\### test



테스트를 추가하거나 수정할 때 사용한다.



```text

test: add depreciation calculation cases

```



\### chore



환경 설정이나 프로젝트 관리 파일을 추가할 때 사용한다.



```text

chore: add Python gitignore

```



\### data



샘플 데이터를 추가하거나 수정할 때 사용할 수 있다.



```text

data: add synthetic fixed asset sample

```



`data:`는 Conventional Commits의 공식 기본 유형은 아니지만, 이번 학습 프로젝트에서는 샘플 데이터 변경을 구분하기 위해 사용할 수 있다.



\---



\## 10. 기본 Git 작업 흐름



```text

파일 생성 또는 수정

→ git status

→ git add

→ git status

→ git commit

→ git push

→ GitHub 웹사이트에서 확인

```



실제 명령 예시:



```powershell

git status

git add README.md

git status

git commit -m "docs: update project description"

git push

```



\---



\## 11. 지금까지 직접 수행한 작업



1\. GitHub에 `ForCPA` Public 저장소를 생성했다.

2\. `git clone`으로 GitHub 저장소를 로컬에 복제했다.

3\. 로컬 저장소와 원격 저장소를 연결했다.

4\. `README.md`를 작성했다.

5\. `git status`로 변경사항을 확인했다.

6\. `git add README.md`로 README를 커밋 대상으로 선택했다.

7\. `docs: define learning roadmap`이라는 첫 커밋을 생성했다.

8\. `git push`로 첫 커밋을 GitHub에 올렸다.

9\. `.gitignore`를 작성했다.

10\. `chore: add Python gitignore`라는 두 번째 커밋을 생성했다.

11\. 두 번째 커밋을 GitHub에 올렸다.



\---



\## 12. 현재까지의 커밋



```text

docs: define learning roadmap

chore: add Python gitignore

```



\---



\## 13. 주의사항



다음 파일은 GitHub에 올리지 않는다.



\- API 키가 들어 있는 `.env`

\- 실제 회사 또는 고객 데이터

\- 개인정보가 포함된 파일

\- 비밀번호와 인증정보

\- Python 가상환경 폴더

\- 불필요한 캐시 파일



커밋 전에는 항상 다음 명령으로 포함될 파일을 확인한다.



```powershell

git status

```



\---



\## 14. 앞으로 배울 개념



\- branch

\- merge

\- pull request

\- conflict

\- remote

\- origin

\- HEAD

\- staging area

\- commit history

\- revert



새로운 Git 개념을 배울 때마다 이 문서에 설명과 직접 실행한 사례를 추가한다.

:::


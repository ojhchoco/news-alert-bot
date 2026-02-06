# Render 무료 배포 가이드

> 뉴스 알림 봇을 Render에 올려서 Cursor/PC 없이 항상 켜 두고, 노션 등에서 URL로 실행할 수 있게 하는 방법입니다.

---

## 1. 배포하면 누가 볼 수 있나요?

**네. Render에 배포하면 생성되는 URL(예: `https://news-alert-bot.onrender.com`)은 인터넷에 공개됩니다.**

- URL을 아는 사람은 브라우저로 접속해 검색 화면을 보고 사용할 수 있습니다.
- 검색 엔진에 노출되지는 않지만, **URL만 알면 누구나 접근 가능**합니다.

### 접근을 막고 싶다면

| 방법 | 설명 |
|------|------|
| **URL 비공개** | URL을 다른 사람에게 알려주지 않으면 실질적으로 본인만 사용 가능. (노션 버튼에만 넣어 두기) |
| **비밀 키(토큰)** | 아래 "비밀 키 또는 Basic 인증 설정" 대로 환경변수만 넣으면 앱이 자동으로 접근을 제한합니다. |
| **HTTP Basic 인증** | 아이디/비밀번호를 한 번 입력해야만 접속 가능. 브라우저 로그인 창이 뜹니다. |

**설정 방법 (둘 중 하나만 사용 권장):**

- **비밀 키 방식**  
  - Render Environment에 `APP_SECRET_KEY` = 원하는 긴 비밀 문자열 추가.  
  - 접속 시 URL에 `?key=비밀키` 를 붙임. 예: `https://news-alert-bot.onrender.com?key=mySecretKey123!`  
  - 노션 버튼 링크에도 위 주소를 넣으면 됨. 키 없이 접속하면 "비밀 키 입력" 폼이 나옴.  
  - API 호출 시 쿼리 `?key=비밀키` 또는 헤더 `X-Api-Key: 비밀키` 사용.

- **Basic 인증 방식**  
  - Render Environment에 `APP_BASIC_USER`(아이디), `APP_BASIC_PASSWORD`(비밀번호) 추가.  
  - 브라우저 접속 시 로그인 창이 뜨고, 입력 후 사용 가능.  
  - API 호출 시 `Authorization: Basic base64(아이디:비밀번호)` 헤더 사용.

- 둘 다 설정하면 비밀 키가 있으면 비밀 키로 통과, 없으면 Basic 요구. 아무것도 없으면 누구나 접근 가능.

---

## 2. Render 무료 배포 절차

### 사전 준비

- **GitHub(또는 GitLab) 계정**
- 이 프로젝트가 **Git 저장소**로 올라가 있어야 함 (`upload.bat`으로 push한 저장소 사용 가능)
- **.env 값**: Render 대시보드에서 환경변수로 입력 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, SLACK_WEBHOOK_URL 등). **.env 파일 자체는 Git에 올리지 말 것.**

### 단계

1. **Render 가입**  
   - https://render.com 접속 → Sign Up (GitHub 계정으로 로그인 권장).

2. **새 Web Service 생성**  
   - Dashboard → **New +** → **Web Service**
   - "Connect a repository"에서 **해당 GitHub 저장소** 선택 (news-alert-bot).
   - 저장소가 없으면 먼저 GitHub에 push.

3. **설정 입력** (아래 순서대로 채우면 됩니다)
   - **Name:** 예: `news-alert-bot` (서비스 이름, URL에 사용됨)
   - **Region:** Singapore 또는 본인과 가까운 지역
   - **Branch:** `main` (또는 사용 중인 기본 브랜치)
   - **Root Directory:** *(비워 두기)* — 프로젝트가 저장소 최상단에 있으면 빈 칸으로 둡니다. 서브폴더에 있다면 그 경로만 입력 (예: `app`).
   - **Runtime:** `Python 3`
   - **Build Command:**  
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**  
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** **Free** 선택

4. **환경변수(Environment Variables)**  
   - **Environment** 탭에서 **Add Environment Variable** 로 아래를 하나씩 추가.  
     (값은 로컬 `.env`에서 복사하되, **비밀값은 채팅/문서에 붙여넣지 말 것.**)
   - 뉴스 검색용: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
   - **Slack 알림을 쓰려면:** `SLACK_WEBHOOK_URL` (Slack Incoming Webhook URL). 없으면 검색은 되지만 Slack 전송은 건너뛰고 안내 메시지만 표시됨.
   - Google News RSS(선택): `GOOGLE_NEWS_HL`, `GOOGLE_NEWS_GL`, `GOOGLE_NEWS_CEID`
   - 리서치 검색 사용 시: `GOOGLE_CSE_ID`, `GOOGLE_API_KEY`
   - 접근 제한(선택): `APP_SECRET_KEY`(비밀 키) 또는 `APP_BASIC_USER` + `APP_BASIC_PASSWORD`(Basic 인증)

   **Google News 언어/지역 (선택, 기본값: 한국어/한국)**  
   뉴스 소스를 Google로 쓸 때만 적용됩니다. 안 넣으면 `hl=ko`, `gl=KR`, `ceid=KR:ko` 로 동작합니다.

   | 변수명 | 의미 | 기본값 | 예시 값 (다른 지역) |
   |--------|------|--------|----------------------|
   | `GOOGLE_NEWS_HL` | 인터페이스/결과 언어 (ISO 639-1) | `ko` | `en`, `ja`, `vi` |
   | `GOOGLE_NEWS_GL` | 국가 코드 (ISO 3166-1) | `KR` | `US`, `JP`, `GB`, `VN` |
   | `GOOGLE_NEWS_CEID` | 국가:언어 조합 | `KR:ko` | `US:en`, `JP:ja`, `VN:vi` |

5. **배포**  
   - **Create Web Service** 클릭.  
   - 첫 배포에 2~5분 정도 걸릴 수 있음.  
   - 완료 후 상단에 **URL**이 생김 (예: `https://news-alert-bot.onrender.com`).

6. **동작 확인**  
   - 해당 URL을 브라우저에서 열어 보기.  
   - `/health` (예: `https://news-alert-bot.onrender.com/health`) 로 헬스 체크 가능.

### 무료 플랜 참고

- 서비스가 **일정 시간 요청이 없으면 sleep** 됨.  
  - 첫 접속 시 깨우는 데 30초~1분 걸릴 수 있음.
- 월 무료 시간 제한이 있음.  
  - 항상 켜 두려면 유료 플랜이 필요하고, “가끔 노션에서만 쓴다”면 무료로도 충분한 경우가 많음.

---

## 3. 노션에서 사용하기

- 노션 페이지에 **Button** 블록 추가 → **링크**에 Render URL 입력 (예: `https://news-alert-bot.onrender.com`).
- 버튼을 누르면 브라우저에서 검색 화면이 열리고, Cursor를 켜지 않아도 동일하게 검색·Slack 전송 가능.

나중에 “URL에 비밀 키 넣어서 본인만 쓰기”를 적용하면, 노션 버튼 링크에는  
`https://news-alert-bot.onrender.com?key=설정한비밀키` 처럼 넣어 두면 됩니다.

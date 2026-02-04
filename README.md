# News Alert Bot

뉴스 알림 봇 프로젝트

## 📌 프로젝트 소개
Claude AI를 활용한 뉴스 알림 시스템

## 🚀 기능
- 뉴스 수집
- AI 분석
- 알림 전송

## 💻 개발 환경
- Python
- FastAPI
- Claude API

## 📝 진행 상황
- [x] GitHub 저장소 생성
- [x] Cursor 연동
- [x] 코드 작성
- [x] 네이버 뉴스 검색 API 연동
- [x] Slack/Email 알림 기능

## 🔧 설정 방법

### 1. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요. **`.env.example`** 파일을 복사해 사용해도 됩니다.

```bash
# 네이버 검색 API (뉴스 검색 시 필수)
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# Slack (선택)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Google News RSS (글로벌 뉴스, API 키 불필요)
GOOGLE_NEWS_HL=ko
GOOGLE_NEWS_GL=KR
GOOGLE_NEWS_CEID=KR:ko

# 연구/정부/국제기구 자료 검색 (Google Custom Search)
GOOGLE_CSE_ID=your_custom_search_engine_id
GOOGLE_API_KEY=your_google_api_key
```

**연구·정부 자료 검색용 CSE 도메인 제안**  
Google Programmable Search Engine에서 "검색할 사이트"에 아래처럼 넣으면 해당 기관 위주로 검색됩니다.

- 국제기구: `*.un.org`, `*.who.int`, `*.oecd.org`, `*.imf.org`, `*.worldbank.org`
- 연구/학술: `*.nature.com`, `*.gov`, `*.go.kr` 등  
자세한 목록은 **`.env.example`** 파일 하단 주석을 참고하세요.

### 2. 네이버 API 키 발급

1. [네이버 개발자 센터](https://developers.naver.com/) 접속
2. 애플리케이션 등록
3. 검색 API 사용 신청
4. Client ID와 Client Secret 발급

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 서버 실행

- **방법 1 (권장)**: 프로젝트 폴더에서 **`run.bat`** 더블클릭 → 검은 창이 뜨고 서버가 켜집니다.
- **방법 2**: 터미널에서 아래 순서대로 실행합니다.

```bash
cd 프로젝트폴더경로
venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**브라우저에서 접속:**  
서버가 켜진 상태에서 주소창에 **`http://localhost:8000`** 또는 **`http://127.0.0.1:8000`** 입력합니다.

#### 사이트가 안 열릴 때

1. **`run.bat` 실행 후 검은 창이 바로 닫히는 경우**  
   - 터미널(PowerShell 또는 CMD)을 열고, 프로젝트 폴더로 이동한 뒤 아래를 **한 줄씩** 실행해 보세요.  
     에러 메시지가 나오면 그 내용을 확인하면 됩니다.
   ```bash
   cd C:\Users\ojhru\Documents\news-alert-bot
   venv\Scripts\activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **“연결할 수 없음” / “연결 거부”**  
   - 서버가 실제로 켜져 있는지 확인하세요. `run.bat` 창이 열려 있고, `Uvicorn running on http://0.0.0.0:8000` 같은 문구가 보여야 합니다.
   - 다른 프로그램이 8000번 포트를 쓰고 있을 수 있습니다. 터미널에서 `--port 8001` 로 바꿔서 실행한 뒤 `http://localhost:8001` 로 접속해 보세요.
3. **가상환경이 없다는 메시지가 나오는 경우**  
   - 같은 폴더에서 `python -m venv venv` 실행 후, `venv\Scripts\activate` → `pip install -r requirements.txt` 실행한 뒤 다시 서버를 실행하세요.

---

### 5. 정부·리서치 자료 검색용 구글 키 (선택)

**“리서치 · 정부 · 국제기구 자료 검색”** 기능을 쓰려면 아래 **두 가지**가 모두 필요합니다.

| 환경변수 | 설명 |
|----------|------|
| **GOOGLE_API_KEY** | Google API 키 (Custom Search API 호출용) |
| **GOOGLE_CSE_ID** | 커스텀 검색 엔진 ID (어떤 사이트를 검색할지 정하는 검색엔진 ID) |

#### 1) Google API 키 발급 (GOOGLE_API_KEY)

1. [Google Cloud Console](https://console.cloud.google.com/) 접속 후 로그인
2. 프로젝트 선택 또는 새 프로젝트 생성
3. **API 및 서비스** → **라이브러리** → **“Custom Search API”** 검색 후 **사용** 클릭
4. **API 및 서비스** → **사용자 인증 정보** → **사용자 인증 정보 만들기** → **API 키** 선택
5. 생성된 API 키를 복사해 `.env`에 `GOOGLE_API_KEY=복사한키` 로 넣습니다.

#### 2) 커스텀 검색 엔진 ID 발급 (GOOGLE_CSE_ID)

1. [Programmable Search Engine (구 Custom Search)](https://programmablesearchengine.google.com/) 접속
2. **새 검색엔진 추가** → “검색할 사이트”에 검색에 포함할 도메인 입력  
   예: `*.go.kr`, `*.gov`, `*.who.int`, `*.oecd.org` (여러 줄로 추가 가능)
3. 검색엔진을 만든 뒤 **설정** → **기본** 탭에서 **검색엔진 ID**를 복사
4. `.env`에 `GOOGLE_CSE_ID=복사한ID` 로 넣습니다.

`.env` 예시는 **`.env.example`** 파일을 참고하고, CSE에 넣을 도메인 목록도 해당 파일 하단 주석에 있습니다.

#### 403 Forbidden이 나올 때 – 해결 체크리스트

리서치 검색 시 **"Custom Search API 접근이 거부되었습니다(403)"** 가 나오면 아래를 **순서대로** 확인하세요.

| 순서 | 확인 항목 | 링크 / 위치 |
|------|-----------|-------------|
| 1 | **Custom Search API 사용 설정** | [API 라이브러리](https://console.cloud.google.com/apis/library) → "Custom Search API" 검색 → **사용** 버튼 클릭 |
| 2 | **API 키 제한** | [사용자 인증 정보](https://console.cloud.google.com/apis/credentials) → 사용 중인 API 키 클릭 → **API 제한사항**에서 **Custom Search API**가 선택돼 있는지 확인 (또는 "키 제한" 없이 사용) |
| 3 | **결제(빌링) 계정 연결** | [결제](https://console.cloud.google.com/billing) → 프로젝트에 **결제 계정이 연결**돼 있는지 확인. 무료 할당량(일 100회)을 쓰더라도 **빌링 연결이 필수**인 경우가 많습니다. |

위 세 가지를 모두 맞춘 뒤 **몇 분 기다렸다가** 다시 리서치 검색을 시도해 보세요.

> **참고:** 뉴스 검색(네이버/Google News)은 위 구글 키 없이 사용할 수 있습니다. 정부·리서치 검색만 쓸 때 위 두 키가 필요합니다.

---

## 📰 기사 선정 기준

- **네이버 API**: 검색은 **제목 + 요약(description)** 기준으로만 이루어집니다. **본문 전체**는 API에서 제공하지 않아 사용하지 않습니다.
- **관련도 필터** (`use_relevance_filter=true`, 기본값): API에서 후보를 더 받아온 뒤, **제목·요약에서 키워드 출현 횟수**로 점수를 매겨 **상위 N개만** 선정합니다. 제목에 키워드가 있을 때 가중치를 더 주어, 주요 이슈가 잘 드러나는 기사가 우선 노출됩니다.
- **정렬** (`sort_by`): `sim`(관련도순, 기본값) 또는 `date`(최신순). 관련도순이면 네이버가 이미 비슷한 기준으로 정렬해 주고, 우리가 다시 제목+요약 점수로 걸러냅니다.

## 📡 API 엔드포인트

### POST /news/search

네이버 뉴스를 검색하고 Slack 알림을 전송합니다.

**요청 예시:**
```json
{
  "keyword": "인공지능",
  "start_date": "2025-01-01",
  "end_date": "2025-01-08",
  "sort_by": "sim",
  "use_relevance_filter": true
}
```

**응답 예시:**
```json
{
  "keyword": "인공지능",
  "period": "2025-01-01 ~ 2025-01-08",
  "news_count": 10,
  "news": [
    {
      "title": "뉴스 제목",
      "link": "https://...",
      "pubDate": "2025-01-08"
    }
  ],
  "slack_sent": true,
  "message": "Slack으로 10개의 뉴스를 전송했습니다"
}
```

**파라미터:**
- `keyword` (필수): 검색 키워드. **여러 개 입력 시 쉼표 또는 줄바꿈으로 구분** (예: `"AI, 인공지능, 일본 경제"`). 키워드별로 검색한 결과가 합쳐지며, 각 기사에 `keyword` 필드로 어떤 키워드로 검색됐는지 표시됩니다.
- `start_date` (선택): 시작 날짜 (YYYY-MM-DD, 기본값: 오늘-7일)
- `end_date` (선택): 종료 날짜 (YYYY-MM-DD, 기본값: 오늘)
- `sort_by` (선택): `sim`(관련도순, 기본값), `date`(최신순)
- `use_relevance_filter` (선택): 제목+요약 기준 관련도로 상위만 선정 (기본값: true)
- `provider` (선택): `naver`(기본값), `google`

### POST /research/search

연구소·정부·국제기구 자료 검색 (Google Custom Search). **키워드는 쉼표/줄바꿈으로 여러 개 입력 가능**하며, 키워드별로 검색한 결과를 합쳐 반환합니다. 각 항목에 `matched_keyword`로 어떤 키워드로 검색됐는지 표시됩니다. `GOOGLE_CSE_ID`, `GOOGLE_API_KEY` 환경변수 필요.

## 🔗 기타 엔드포인트

- `GET /`: 서버 상태 확인
- `GET /health`: 헬스 체크
- `GET /news?keyword=검색어`: 예시 뉴스 조회
- `POST /extract-keywords`: 텍스트에서 중요한 단어 추출
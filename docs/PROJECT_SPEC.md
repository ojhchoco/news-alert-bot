# News Alert Bot – 프로젝트 명세 (재개발/복구용)

> 파일을 잃어버려도 이 명세와 환경만 있으면 웹앱을 다시 만들 수 있도록 정리한 문서입니다.

---

## 1. 프로젝트 개요

- **이름:** News Alert Bot (뉴스 검색 및 Slack 알림 시스템)
- **역할:** 키워드로 뉴스·리서치를 검색하고, 결과를 웹에서 보여주며, 선택적으로 Slack으로 알림 전송
- **기술 스택:** Python 3.9+, FastAPI, Uvicorn, Pydantic, Requests, Jinja2, python-dotenv, pytz

---

## 2. 제공 기능 요약

| 기능 | 설명 |
|------|------|
| **뉴스 검색** | 네이버 뉴스 API 또는 Google News RSS로 뉴스 검색. 시작/종료 날짜, 관련도 필터, 소스(naver/google) 선택 가능. |
| **다중 키워드** | 키워드를 쉼표 또는 줄바꿈으로 여러 개 입력 가능. 키워드별로 검색 후 결과를 합치고, 각 항목에 어떤 키워드로 검색됐는지 표시. |
| **Slack 알림** | 뉴스 검색 결과를 Slack Webhook으로 전송 (선택). |
| **리서치·정부 자료 검색** | Google Custom Search API로 지정 도메인(정부, 국제기구, 연구소 등) 위주 검색. 기간 제한(날짜 범위 또는 d1/w1/m1/y1), 최대 30개까지 페이지네이션. |
| **키워드 추출** | 텍스트에서 빈도 기반으로 상위 N개 키워드 추출 (불용어 제거). |
| **보안** | 에러 메시지·로그에 API 키 등 비밀값이 나오지 않도록 `_redact_secrets()`로 마스킹. |

---

## 3. 디렉터리/파일 구조

```
news-alert-bot/
├── main.py              # FastAPI 앱, API·비즈니스 로직 전부
├── requirements.txt     # Python 패키지 목록
├── .env                 # 환경변수 (실제 값, Git 제외)
├── .env.example         # 환경변수 예시 + CSE 도메인 추천
├── .gitignore           # venv, .env, __pycache__, *.log 등
├── run.bat              # Windows: 가상환경 활성화 후 uvicorn 실행, 브라우저 자동 오픈
├── upload.bat           # Git push (업로드)
├── download.bat         # Git pull (다운로드)
├── templates/
│   └── index.html       # 메인 페이지: 뉴스 검색 폼 + 리서치 검색 폼 + 결과 영역
├── docs/
│   └── PROJECT_SPEC.md  # 본 명세서
└── README.md            # 사용자용 설정·실행·API 설명
```

---

## 4. 환경변수 (.env)

| 변수명 | 필수 | 설명 | 발급/설정 |
|--------|------|------|-----------|
| `NAVER_CLIENT_ID` | 뉴스(네이버) 사용 시 | 네이버 검색 API Client ID | [네이버 개발자센터](https://developers.naver.com/) → 애플리케이션 등록 → 검색 API |
| `NAVER_CLIENT_SECRET` | 뉴스(네이버) 사용 시 | 네이버 검색 API Client Secret | 위와 동일 |
| `SLACK_WEBHOOK_URL` | Slack 알림 사용 시 | Slack Incoming Webhook URL | Slack 앱/채널 설정에서 Webhook URL 복사 |
| `GOOGLE_NEWS_HL` | 선택 | Google News RSS UI 언어 (ko, en, ja, vi 등) | 기본값 ko |
| `GOOGLE_NEWS_GL` | 선택 | Google News 국가 코드 (KR, US 등) | 기본값 KR |
| `GOOGLE_NEWS_CEID` | 선택 | Google News ceid (예: KR:ko) | 기본값 KR:ko |
| `GOOGLE_CSE_ID` | 리서치 검색 사용 시 | Programmable Search Engine 검색엔진 ID | [Programmable Search Engine](https://programmablesearchengine.google.com/) → 검색엔진 생성 → 설정에서 ID 복사 |
| `GOOGLE_API_KEY` | 리서치 검색 사용 시 | Google Cloud API 키 (Custom Search API 호출용) | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → API 키 생성, Custom Search API 사용 설정, **결제 계정 연결 필요** |

- **리서치 검색 403:** Custom Search API는 결제(빌링) 계정이 연결된 프로젝트에서만 사용 가능. 결제 없으면 뉴스 검색만 사용.

---

## 5. CSE(커스텀 검색엔진) 도메인 추천

Programmable Search Engine의 "검색할 사이트"에 한 줄에 하나씩 추가:

```
*.un.org
*.who.int
*.oecd.org
*.imf.org
*.worldbank.org
*.wto.org
*.ilo.org
*.unesco.org
*.go.kr
*.korea.kr
*.assembly.go.kr
*.gov
*.europa.eu
*.nature.com
*.brookings.edu
*.rand.org
```

---

## 6. API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | HTML 메인 페이지 (뉴스 + 리서치 폼) |
| GET | `/health` | 헬스 체크 `{ "status": "healthy", "timestamp": "..." }` |
| GET | `/news?keyword=...` | 예시 뉴스 3개 (가짜 데이터) |
| POST | `/extract-keywords` | Body: `{ "text": "..." }` → 키워드 상위 5개 |
| POST | `/news/search` | 뉴스 검색 + Slack 전송 |
| POST | `/research/search` | 리서치·정부 자료 검색 |

### POST /news/search

- **Request Body:**  
  `keyword`(필수), `start_date`, `end_date`(YYYY-MM-DD), `sort_by`("sim"|"date"), `use_relevance_filter`(bool), `provider`("naver"|"google")  
  - 키워드: 쉼표 또는 줄바꿈으로 여러 개 가능.
- **동작:**  
  - `provider=naver` → 네이버 뉴스 API (제목+요약 관련도 필터 가능).  
  - `provider=google` → Google News RSS, 최대 30건.  
  - 키워드별로 검색 후 결과 합침, 각 기사에 `keyword` 필드로 검색에 사용된 키워드 표시.  
  - 기간 기본값: end=오늘, start=오늘-7일.  
  - Slack Webhook 있으면 결과 전송.
- **Response:**  
  `keyword`, `keywords`, `period`, `news_count`, `news`(배열), `slack_sent`, `message`

**뉴스 검색 결과 개수·기준**

| 소스 | 키워드당 최대 개수 | 기준 |
|------|-------------------|------|
| **네이버** | 30개 | API를 최대 5페이지(페이지당 100건)까지 요청한 뒤, **설정한 기간(start_date~end_date) 안의 기사만** 남기고 관련도/최신순으로 상위 30개 선정. |
| **Google** | 50개(최대 100) | Google News RSS가 주는 순서(보통 최신) 그대로, 상위 50개(필요 시 최대 100개까지 확장 가능). |

- 키워드를 여러 개 넣으면 **키워드별로 검색한 결과를 합칩니다.**  
  예: 키워드 3개 → 네이버 최대 90개(30×3), Google 최대 150개(50×3).
- **기간을 넓게 잡아도 자료가 적다면:** 네이버는 기간 필터가 적용되므로, **개수를 늘리는 쪽(페이지네이션·상한 확대)이 유리**합니다. 기간을 짧게 나눠 여러 번 검색하는 것보다 한 번에 많은 건을 가져와 기간으로 거르는 방식이 효율적입니다. Google RSS는 날짜 파라미터가 없어 “최신 N건”만 가능하므로, 개수 상한만 조정하면 됩니다.

### POST /research/search

- **Request Body:**  
  `keyword`(필수), `language`(en/ko/ja/vi 등), `max_results`(1~30, 기본 30), `start_date`, `end_date`(YYYY-MM-DD), `date_restrict`(d1/w1/m1/y1)  
  - 키워드: 쉼표 또는 줄바꿈으로 여러 개 가능.
- **동작:**  
  - Google Custom Search API 호출.  
  - `start_date`+`end_date` 있으면 `sort=date:r:yyyymmdd:yyyymmdd` 로 기간 제한.  
  - 없으면 `dateRestrict` 사용(d1/w1/m1/y1).  
  - 키워드당 최대 30건까지 페이지네이션(start=1,11,21)으로 수집.  
  - 각 항목에 `matched_keyword` 표시.
- **Response:**  
  `keyword`, `keywords`, `total_results`, `items`(배열), `message`  
- **403 시:**  
  결제 계정 연결 필요하다는 안내 메시지 반환 (키/비밀값은 노출하지 않음).

---

## 7. 주요 데이터 모델 (Pydantic)

- **NewsSearchItem:** title, link, pubDate, keyword(선택)
- **NewsSearchResponse:** keyword, keywords, period, news_count, news, slack_sent, message
- **ResearchSearchItem:** title, link, snippet, matched_keyword
- **ResearchSearchResponse:** keyword, keywords, total_results, items, message

---

## 8. 핵심 로직 요약

- **다중 키워드 파싱:**  
  `parse_keywords(raw)` — 쉼표·줄바꿈으로 split, 공백 제거 후 빈 문자열 제외.
- **뉴스 검색:**  
  - 네이버: `GET https://openapi.naver.com/v1/search/news.json` (query, display, sort, start).  
  - Google: `GET https://news.google.com/rss/search` (q, hl, gl, ceid).  
  - 관련도 필터(네이버): 제목·요약에서 키워드 출현 횟수로 점수, 상위 N개만 반환.
- **리서치 검색:**  
  - `GET https://www.googleapis.com/customsearch/v1` (key, cx, q, num, start, sort 또는 dateRestrict, lr).  
  - start=1, 11, 21 로 페이지네이션해 최대 30건 수집.
- **비밀값 보호:**  
  `_redact_secrets(text)` — key=, cx=, client_secret=, Slack URL 등 마스킹 후 로그/에러에만 사용.  
  사용자에게 돌려주는 HTTPException detail에는 비밀/예외 메시지 넣지 않고 고정 문구만 사용.

---

## 9. 실행 방법

1. **가상환경 생성 및 패키지 설치**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
2. **.env 설정**  
   `.env.example`을 복사해 `.env`로 저장한 뒤, 위 환경변수 표를 참고해 값 채우기.
3. **서버 실행**
   - Windows: `run.bat` 더블클릭 (자동으로 브라우저에서 http://localhost:8000 오픈)
   - 또는: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
4. **접속**  
   브라우저에서 http://localhost:8000

---

## 10. requirements.txt 내용

```
fastapi==0.124.4
uvicorn==0.33.0
pydantic==2.10.6
requests==2.31.0
python-dotenv==1.0.0
jinja2==3.1.4
pytz==2024.1
```

(표준 라이브러리만 사용: re, collections, os, logging, datetime, xml.etree.ElementTree)

---

## 11. 프론트엔드 (templates/index.html) 요약

- **레이아웃:**  
  제목 "뉴스 & 리서치 검색 대시보드" 아래, 2열 그리드: 왼쪽 뉴스 검색 폼, 오른쪽 리서치 검색 폼.  
  결과는 폼 아래 `#results`, `#researchResults` 영역에 동적 렌더링.
- **뉴스 폼:**  
  검색 키워드, 뉴스 소스(네이버/Google), 시작/종료 날짜, [뉴스 검색] 버튼.  
  제출 시 POST `/news/search`, 응답으로 키워드·기간·개수·Slack 결과·뉴스 목록(항목별 keyword 뱃지) 표시.
- **리서치 폼:**  
  검색 키워드, 문서 언어, 최대 결과 수(1~30), 시작/종료 날짜, 또는 기간 제한(전체/d1/w1/m1/y1), [리서치 자료 검색] 버튼.  
  제출 시 POST `/research/search`, 응답으로 키워드·총 결과 수·항목 목록(항목별 matched_keyword 뱃지) 표시.
- **스타일:**  
  Tailwind CSS CDN, primary/secondary 색상, 로딩 스피너, 에러 시 고정 메시지 표시(API 키 등 노출 없음).

---

## 12. Git/배포 관련

- **.gitignore:**  
  venv, .env, .env.local, __pycache__, *.log, app.log, .idea, .vscode 등 포함.  
  `.env`는 절대 커밋하지 않음.
- **upload.bat / download.bat:**  
  프로젝트 폴더 기준으로 `git add -A`, `git commit`, `git push` / `git pull` 실행.  
  PC·노트북 간 동기화용.

---

## 13. 참고 링크

- [Google Cloud Console – 사용자 인증 정보](https://console.cloud.google.com/apis/credentials)
- [Google Cloud Console – API 라이브러리](https://console.cloud.google.com/apis/library)
- [Google Cloud 결제](https://console.cloud.google.com/billing)
- [Programmable Search Engine](https://programmablesearchengine.google.com/)
- [네이버 개발자센터](https://developers.naver.com/)

---

이 명세서와 `requirements.txt`, `.env.example`만 있어도 구조를 복원할 수 있습니다. 실제 코드는 `main.py`와 `templates/index.html`을 위 로직·엔드포인트·모델에 맞춰 다시 구현하면 됩니다.

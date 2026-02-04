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

```bash
uvicorn main:app --reload
```

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
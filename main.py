from fastapi import FastAPI, Query, Body, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from typing import List, Optional, Tuple, Dict, Literal
from pydantic import BaseModel, Field
import re
from collections import Counter
import os
import logging
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import pytz

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

app = FastAPI(title="뉴스 검색 및 Slack 알림 시스템")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory="templates")


class NewsItem(BaseModel):
    title: str
    keyword: str


class NewsResponse(BaseModel):
    keyword: str
    news: List[NewsItem]


class TextRequest(BaseModel):
    text: str


class KeywordResponse(BaseModel):
    keywords: List[str]
    count: int


class NewsSearchItem(BaseModel):
    title: str
    link: str
    pubDate: str


class NewsSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="검색 키워드")
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD)")
    sort_by: Literal["sim", "date"] = Field("sim", description="정렬: sim=관련도순, date=최신순")
    use_relevance_filter: bool = Field(True, description="제목+요약 기준 관련도로 상위만 선정")


class NewsSearchResponse(BaseModel):
    keyword: str
    period: str
    news_count: int
    news: List[NewsSearchItem]
    slack_sent: bool
    message: str


# 불용어 목록 (한국어 조사, 접속사 등)
STOP_WORDS = {
    "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "로", "으로",
    "에서", "에게", "한테", "께", "더", "만", "까지", "부터", "조차", "마저",
    "그", "그것", "이것", "저것", "그런", "이런", "저런", "그렇게", "이렇게", "저렇게",
    "그리고", "또한", "또", "그러나", "하지만", "그런데", "그래서", "그러므로",
    "있다", "없다", "되다", "하다", "이다", "아니다", "같다", "다르다"
}


def get_korea_time() -> datetime:
    """한국 시간을 반환합니다."""
    return datetime.now(KST)


def extract_keywords(text: str, top_n: int = 5) -> List[str]:
    """
    텍스트에서 중요한 단어를 추출합니다.
    """
    # 구두점 제거 및 소문자 변환
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # 공백으로 단어 분리
    words = text.split()
    
    # 불용어 제거 및 길이 2 이상인 단어만 선택
    filtered_words = [
        word for word in words 
        if word not in STOP_WORDS and len(word) >= 2
    ]
    
    # 빈도수 계산
    word_counts = Counter(filtered_words)
    
    # 빈도수 기준으로 상위 N개 추출
    top_words = [word for word, count in word_counts.most_common(top_n)]
    
    return top_words


def validate_api_keys() -> Tuple[str, str]:
    """네이버 API 키를 검증하고 반환합니다."""
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error("네이버 API 키가 설정되지 않았습니다.")
        raise HTTPException(
            status_code=500,
            detail="네이버 API 키가 설정되지 않았습니다. NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 환경변수를 설정해주세요."
        )
    
    return client_id, client_secret


def validate_date_format(date_str: str) -> bool:
    """날짜 형식이 올바른지 검증합니다."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _relevance_score(keyword: str, title: str, description: str) -> int:
    """제목·요약에서 키워드 출현 횟수로 관련도 점수를 계산합니다. 제목 가중치 2배."""
    title_clean = (title or "").strip()
    desc_clean = (description or "").strip()
    kw = keyword.strip()
    if not kw:
        return 0
    # 제목에 키워드가 있으면 가중치 2, 요약은 1
    score = title_clean.count(kw) * 2 + desc_clean.count(kw)
    return score


def get_naver_news(
    keyword: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 10,
    sort_by: str = "sim",
    use_relevance_filter: bool = True,
) -> List[NewsSearchItem]:
    """
    네이버 뉴스 검색 API를 사용하여 뉴스를 가져옵니다.
    - 검색은 네이버 API 기준으로 제목·요약(description)에서만 이루어지며, 본문은 사용하지 않습니다.
    - use_relevance_filter=True이면 API에서 더 많이 받아온 뒤, 제목+요약 기준 관련도 점수로 상위만 선정합니다.
    """
    try:
        client_id, client_secret = validate_api_keys()
        
        # 날짜 검증
        if start_date and not validate_date_format(start_date):
            raise HTTPException(
                status_code=400,
                detail=f"시작 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용해주세요. (입력: {start_date})"
            )
        
        if end_date and not validate_date_format(end_date):
            raise HTTPException(
                status_code=400,
                detail=f"종료 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용해주세요. (입력: {end_date})"
            )
        
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        # 관련도 필터 사용 시 후보를 더 받아서 우리가 상위만 선정
        request_display = min(30, 100) if use_relevance_filter else min(max_results, 100)
        params = {
            "query": keyword,
            "display": request_display,
            "sort": sort_by,  # sim=관련도순, date=최신순
            "start": 1
        }
        
        logger.info(f"네이버 뉴스 API 호출: keyword={keyword}, start_date={start_date}, end_date={end_date}, sort={sort_by}, relevance_filter={use_relevance_filter}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        candidates: List[Tuple[int, NewsSearchItem]] = []
        for item in data.get("items", []):
            title = re.sub(r'<[^>]+>', '', item.get("title", ""))
            description = re.sub(r'<[^>]+>', '', item.get("description", ""))
            
            pub_date = item.get("pubDate", "")
            if pub_date:
                try:
                    date_obj = datetime.strptime(pub_date.split("+")[0].strip(), "%a, %d %b %Y %H:%M:%S")
                    date_obj = date_obj.replace(tzinfo=pytz.UTC).astimezone(KST)
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                except Exception as e:
                    logger.warning(f"날짜 파싱 실패: {pub_date}, 오류: {str(e)}")
                    formatted_date = get_korea_time().strftime("%Y-%m-%d")
            else:
                formatted_date = get_korea_time().strftime("%Y-%m-%d")
            
            news_item = NewsSearchItem(
                title=title,
                link=item.get("link", ""),
                pubDate=formatted_date
            )
            score = _relevance_score(keyword, title, description) if use_relevance_filter else 0
            candidates.append((score, news_item))
        
        if use_relevance_filter:
            candidates.sort(key=lambda x: -x[0])  # 관련도 점수 높은 순
        news_items = [item for _, item in candidates[:max_results]]
        
        logger.info(f"뉴스 검색 완료: {len(news_items)}개 결과 (관련도 필터={use_relevance_filter})")
        return news_items
    
    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error("네이버 뉴스 API 호출 타임아웃")
        raise HTTPException(
            status_code=504,
            detail="네이버 뉴스 API 호출 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f"네이버 뉴스 API HTTP 오류: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="네이버 API 인증에 실패했습니다. API 키를 확인해주세요."
            )
        elif e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="API 호출 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"네이버 뉴스 API 호출 중 오류가 발생했습니다: {str(e)}"
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"네이버 뉴스 API 요청 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"네이버 뉴스 API 호출 중 오류가 발생했습니다: {str(e)}"
        )
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"예상치 못한 오류가 발생했습니다: {str(e)}"
        )


def send_slack_notification(keyword: str, news_items: List[NewsSearchItem], period: str) -> bool:
    """
    Slack Webhook을 통해 알림을 전송합니다.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        return False
    
    try:
        news_text = "\n".join([
            f"{i+1}. <{item.link}|{item.title}> ({item.pubDate})"
            for i, item in enumerate(news_items)
        ])
        
        message = {
            "text": f"📰 뉴스 알림: '{keyword}'",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📰 뉴스 알림: '{keyword}'"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*기간:* {period}\n*검색 결과:* {len(news_items)}개"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*뉴스 목록:*\n{news_text}"
                    }
                }
            ]
        }
        
        logger.info(f"Slack 알림 전송 시도: keyword={keyword}, news_count={len(news_items)}")
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        logger.info("Slack 알림 전송 성공")
        return True
    except requests.exceptions.Timeout:
        logger.error("Slack Webhook 호출 타임아웃")
        return False
    except requests.exceptions.HTTPError as e:
        logger.error(f"Slack Webhook HTTP 오류: {e.response.status_code} - {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Slack Webhook 요청 오류: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Slack 알림 전송 중 예상치 못한 오류: {str(e)}", exc_info=True)
        return False


# 예시 가짜 뉴스 데이터
FAKE_NEWS_DATABASE = {
    "정치": [
        "정치인 비리 폭로, 충격적인 진실 공개",
        "정치권 대규모 부패 스캔들 발생",
        "정치 개혁을 위한 새로운 법안 통과"
    ],
    "경제": [
        "경제 위기로 인한 대규모 실업 발생",
        "경제 성장률 역대 최고치 기록",
        "경제 정책 변경으로 인한 시장 혼란"
    ],
    "기술": [
        "기술 혁신으로 인한 일자리 대량 감소",
        "기술 기업의 독점 심화 우려",
        "기술 발전이 가져올 미래의 변화"
    ],
    "건강": [
        "건강 관리의 새로운 방법 발견",
        "건강 식품의 효과 입증",
        "건강 검진 결과 충격적인 발견"
    ],
    "환경": [
        "환경 오염으로 인한 생태계 파괴",
        "환경 보호를 위한 새로운 정책 발표",
        "환경 문제 해결을 위한 긴급 조치"
    ]
}


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """
    홈페이지 - 뉴스 검색 폼
    """
    logger.info("홈페이지 접속")
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy", "timestamp": get_korea_time().isoformat()}


@app.get("/news", response_model=NewsResponse)
def get_news(keyword: str = Query(..., description="검색할 키워드")):
    """
    검색어를 입력받아 해당 키워드가 포함된 가짜 뉴스 제목 3개를 반환합니다.
    """
    # 키워드가 데이터베이스에 있는 경우 해당 카테고리의 뉴스 반환
    if keyword in FAKE_NEWS_DATABASE:
        news_items = [
            NewsItem(title=title, keyword=keyword)
            for title in FAKE_NEWS_DATABASE[keyword]
        ]
    else:
        # 키워드가 없는 경우 기본 예시 뉴스 생성
        news_items = [
            NewsItem(title=f"{keyword} 관련 충격적인 소식 전해져", keyword=keyword),
            NewsItem(title=f"{keyword}로 인한 파장 계속 확산", keyword=keyword),
            NewsItem(title=f"{keyword}에 대한 새로운 사실 밝혀져", keyword=keyword)
        ]
    
    return NewsResponse(keyword=keyword, news=news_items)


@app.post("/extract-keywords", response_model=KeywordResponse)
def extract_keywords_api(request: TextRequest = Body(...)):
    """
    텍스트를 입력받아 중요한 단어 5개를 추출합니다.
    """
    keywords = extract_keywords(request.text, top_n=5)
    
    return KeywordResponse(
        keywords=keywords,
        count=len(keywords)
    )


@app.post("/news/search", response_model=NewsSearchResponse)
def search_news(request: NewsSearchRequest = Body(...)):
    """
    네이버 뉴스를 검색하고 Slack 알림을 전송합니다.
    """
    try:
        # 날짜 기본값 설정 (한국 시간 기준)
        korea_now = get_korea_time()
        
        if not request.end_date:
            end_date = korea_now.strftime("%Y-%m-%d")
        else:
            end_date = request.end_date
        
        if not request.start_date:
            start_date = (korea_now - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            start_date = request.start_date
        
        # 날짜 검증
        if not validate_date_format(start_date):
            raise HTTPException(
                status_code=400,
                detail=f"시작 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용해주세요. (입력: {start_date})"
            )
        
        if not validate_date_format(end_date):
            raise HTTPException(
                status_code=400,
                detail=f"종료 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용해주세요. (입력: {end_date})"
            )
        
        # 시작 날짜가 종료 날짜보다 늦으면 오류
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise HTTPException(
                status_code=400,
                detail="시작 날짜는 종료 날짜보다 이전이어야 합니다."
            )
        
        logger.info(f"뉴스 검색 요청: keyword={request.keyword}, start_date={start_date}, end_date={end_date}")
        
        # 네이버 뉴스 검색 (제목+요약 기준 관련도 선정 옵션 사용)
        news_items = get_naver_news(
            keyword=request.keyword,
            start_date=start_date,
            end_date=end_date,
            max_results=10,
            sort_by=request.sort_by,
            use_relevance_filter=request.use_relevance_filter,
        )
        
        # Slack 알림 전송
        period = f"{start_date} ~ {end_date}"
        slack_sent = send_slack_notification(request.keyword, news_items, period)
        
        if slack_sent:
            message = f"Slack으로 {len(news_items)}개의 뉴스를 전송했습니다"
        else:
            message = "Slack 전송에 실패했습니다. SLACK_WEBHOOK_URL 환경변수를 확인해주세요."
        
        logger.info(f"뉴스 검색 완료: keyword={request.keyword}, news_count={len(news_items)}, slack_sent={slack_sent}")
        
        return NewsSearchResponse(
            keyword=request.keyword,
            period=period,
            news_count=len(news_items),
            news=news_items,
            slack_sent=slack_sent,
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"뉴스 검색 중 예상치 못한 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"예상치 못한 오류가 발생했습니다: {str(e)}"
        )

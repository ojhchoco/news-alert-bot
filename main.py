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
import xml.etree.ElementTree as ET

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

# Google News RSS 기본 설정 (환경변수로 재정의 가능)
GOOGLE_NEWS_HL = os.getenv("GOOGLE_NEWS_HL", "ko")      # UI 언어
GOOGLE_NEWS_GL = os.getenv("GOOGLE_NEWS_GL", "KR")      # 국가 코드
GOOGLE_NEWS_CEID = os.getenv("GOOGLE_NEWS_CEID", "KR:ko")

# Google Custom Search (연구/정부 자료용)
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")  # 커스텀 검색 엔진 ID
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Google API 키

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
    keyword: Optional[str] = Field(None, description="이 기사가 검색된 키워드 (여러 키워드 검색 시 표시)")


class NewsSearchRequest(BaseModel):
    keyword: str = Field(
        ...,
        min_length=1,
        description="검색 키워드. 여러 개 입력 시 쉼표 또는 줄바꿈으로 구분 (예: AI, 인공지능, 일본 경제)",
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD)")
    sort_by: Literal["sim", "date"] = Field("sim", description="정렬: sim=관련도순, date=최신순 (네이버 전용)")
    use_relevance_filter: bool = Field(True, description="제목+요약 기준 관련도로 상위만 선정 (네이버 전용)")
    provider: Literal["naver", "google"] = Field(
        "naver",
        description="뉴스 제공자: naver=네이버 뉴스, google=Google News RSS",
    )


class NewsSearchResponse(BaseModel):
    keyword: str = ""  # 단일 키워드일 때와 하위 호환
    keywords: List[str] = Field(default_factory=list, description="검색에 사용된 키워드 목록")
    period: str
    news_count: int
    news: List[NewsSearchItem]
    slack_sent: bool
    message: str


class ResearchSearchItem(BaseModel):
    title: str
    link: str
    snippet: str
    matched_keyword: str = Field("", description="이 결과가 검색된 키워드 (여러 키워드 검색 시 표시)")


class ResearchSearchRequest(BaseModel):
    keyword: str = Field(
        ...,
        min_length=1,
        description="검색 키워드. 여러 개 입력 시 쉼표 또는 줄바꿈으로 구분 (예: OECD AI, WHO vaccine)",
    )
    language: Optional[str] = Field(
        None,
        description="검색 언어 코드 (예: en, ko, ja, vi). 지정하지 않으면 Google 기본값 사용",
    )
    max_results: int = Field(
        30,
        ge=1,
        le=30,
        description="가져올 최대 결과 수 (1~30, 페이지네이션으로 수집)",
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD). end_date와 함께 쓰면 해당 기간으로 제한")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD). start_date와 함께 쓰면 해당 기간으로 제한")
    date_restrict: Optional[str] = Field(
        None,
        description="기간 제한(날짜 미지정 시): d1(1일), w1(1주), m1(1개월), y1(1년). 없으면 전체 기간",
    )


class ResearchSearchResponse(BaseModel):
    keyword: str = ""
    keywords: List[str] = Field(default_factory=list, description="검색에 사용된 키워드 목록")
    total_results: int
    items: List[ResearchSearchItem]
    message: str


def _redact_secrets(text: str) -> str:
    """로그/에러 메시지에 API 키·비밀값이 노출되지 않도록 마스킹합니다."""
    if not text:
        return text
    s = text
    # key=... (API 키), cx=... (CSE ID), client_secret=..., URL 내 토큰 등 마스킹
    s = re.sub(r"\bkey=[^&\s]+", "key=***", s, flags=re.IGNORECASE)
    s = re.sub(r"\bcx=[^&\s]+", "cx=***", s, flags=re.IGNORECASE)
    s = re.sub(r"\bclient_secret=[^&\s]+", "client_secret=***", s, flags=re.IGNORECASE)
    s = re.sub(r"X-Naver-Client-Secret[:\s]*[^\s]+", "X-Naver-Client-Secret: ***", s, flags=re.IGNORECASE)
    s = re.sub(r"hooks\.slack\.com/services/[^\s]+", "hooks.slack.com/services/***", s, flags=re.IGNORECASE)
    return s


def parse_keywords(raw: str) -> List[str]:
    """쉼표 또는 줄바꿈으로 구분된 문자열에서 키워드 목록을 추출합니다. 공백 제거 후 빈 항목 제외."""
    if not raw or not raw.strip():
        return []
    parts = re.split(r"[\n,]+", raw)
    return [p.strip() for p in parts if p.strip()]


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


def _fetch_research_page(
    keyword: str,
    language: Optional[str],
    start_index: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date_restrict: Optional[str] = None,
) -> List[ResearchSearchItem]:
    """Google Custom Search API 1회 호출. start_index는 1, 11, 21 등(페이지네이션)."""
    url = "https://www.googleapis.com/customsearch/v1"
    params: Dict[str, str] = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": keyword,
        "num": "10",
        "start": str(start_index),
    }
    if language:
        params["lr"] = f"lang_{language}"
    if start_date and end_date and validate_date_format(start_date) and validate_date_format(end_date):
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt <= end_dt:
            params["sort"] = f"date:r:{start_date.replace('-', '')}:{end_date.replace('-', '')}"
    elif date_restrict:
        params["dateRestrict"] = date_restrict

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    items_data = data.get("items", []) or []
    return [
        ResearchSearchItem(
            title=item.get("title", ""),
            link=item.get("link", ""),
            snippet=item.get("snippet", ""),
            matched_keyword=keyword,
        )
        for item in items_data
    ]


def get_research_results(
    keywords: List[str],
    language: Optional[str] = None,
    max_results_per_keyword: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date_restrict: Optional[str] = None,
) -> List[ResearchSearchItem]:
    """
    Google Custom Search API를 사용하여 연구소/정부/국제기구 등의 자료를 검색합니다.
    여러 키워드를 주면 키워드별로 검색한 뒤 결과를 합쳐 반환하며, 최대 30개까지 페이지네이션으로 수집합니다.
    """
    if not GOOGLE_CSE_ID or not GOOGLE_API_KEY:
        logger.error("Google Custom Search API 키 또는 CSE ID가 설정되지 않았습니다.")
        raise HTTPException(
            status_code=500,
            detail="연구/정부 자료 검색을 사용하려면 GOOGLE_CSE_ID와 GOOGLE_API_KEY 환경변수를 설정해주세요.",
        )

    if not keywords:
        raise HTTPException(
            status_code=400,
            detail="검색 키워드는 비어 있을 수 없습니다.",
        )

    if start_date and end_date and (not validate_date_format(start_date) or not validate_date_format(end_date)):
        raise HTTPException(
            status_code=400,
            detail="시작/종료 날짜는 YYYY-MM-DD 형식이어야 합니다.",
        )
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="시작 날짜는 종료 날짜보다 이전이어야 합니다.")

    try:
        research_items: List[ResearchSearchItem] = []
        for kw in keywords:
            collected: List[ResearchSearchItem] = []
            for start_index in (1, 11, 21):
                if len(collected) >= max_results_per_keyword:
                    break
                logger.info(
                    f"Google Custom Search 호출: keyword={kw}, start={start_index}, date_restrict={date_restrict}, start_date={start_date}, end_date={end_date}"
                )
                page = _fetch_research_page(
                    kw, language, start_index, start_date, end_date, date_restrict
                )
                collected.extend(page)
                if len(page) < 10:
                    break
            research_items.extend(collected[:max_results_per_keyword])

        logger.info(f"Google Custom Search 결과: 총 {len(research_items)}개 (키워드 {len(keywords)}개)")
        return research_items

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error("Google Custom Search 호출 타임아웃")
        raise HTTPException(
            status_code=504,
            detail="연구/정부 자료 검색 API 호출 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        )
    except requests.exceptions.HTTPError as e:
        logger.error("Google Custom Search HTTP 오류: %s - %s", e.response.status_code, _redact_secrets(e.response.text or ""))
        if e.response.status_code == 403:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Custom Search API 접근이 거부되었습니다(403). "
                    "이 API는 무료 할당량(일 100회)을 쓰더라도 프로젝트에 결제(빌링) 계정이 연결되어 있어야 합니다. "
                    "결제 계정이 없거나 사용 중지된 경우 리서치 검색은 사용할 수 없으며, 뉴스 검색(네이버/Google News)만 이용해 주세요."
                ),
            )
        raise HTTPException(
            status_code=500,
            detail="연구/정부 자료 검색 중 HTTP 오류가 발생했습니다. 상태 코드: " + str(e.response.status_code),
        )
    except requests.exceptions.RequestException as e:
        logger.error("Google Custom Search 요청 오류: %s", _redact_secrets(str(e)))
        raise HTTPException(
            status_code=500,
            detail="연구/정부 자료 검색 중 요청 오류가 발생했습니다.",
        )
    except Exception as e:
        logger.error("연구/정부 자료 검색 중 예상치 못한 오류: %s", _redact_secrets(str(e)), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="연구/정부 자료 검색 중 예상치 못한 오류가 발생했습니다.",
        )


def get_google_news(
    keyword: str,
    max_results: int = 30,
) -> List[NewsSearchItem]:
    """
    Google News RSS를 사용하여 글로벌 뉴스를 가져옵니다.
    - 검색은 Google News 기준으로 제목·요약에 대해 이루어집니다.
    - 날짜 필터(start_date/end_date)는 직접 적용하지 않고, Google News의 최신 정렬에 따릅니다.
    """
    try:
        if not keyword.strip():
            raise HTTPException(
                status_code=400,
                detail="검색 키워드는 비어 있을 수 없습니다.",
            )

        url = "https://news.google.com/rss/search"
        params = {
            "q": keyword,
            "hl": GOOGLE_NEWS_HL,
            "gl": GOOGLE_NEWS_GL,
            "ceid": GOOGLE_NEWS_CEID,
        }

        logger.info(
            f"Google News RSS 호출: keyword={keyword}, hl={GOOGLE_NEWS_HL}, gl={GOOGLE_NEWS_GL}, ceid={GOOGLE_NEWS_CEID}"
        )

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        channel = root.find("channel")
        if channel is None:
            logger.warning("Google News RSS: channel 요소를 찾을 수 없습니다.")
            return []

        items = channel.findall("item")
        news_items: List[NewsSearchItem] = []

        for item in items[:max_results]:
            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_date_elem = item.find("pubDate")

            raw_title = title_elem.text if title_elem is not None else ""
            title = re.sub(r"<[^>]+>", "", raw_title or "")

            link = link_elem.text if link_elem is not None else ""

            pub_date_raw = pub_date_elem.text if pub_date_elem is not None else ""
            if pub_date_raw:
                try:
                    # 예: Tue, 04 Feb 2025 10:00:00 GMT
                    date_obj = datetime.strptime(
                        pub_date_raw.strip(), "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    # Google은 보통 GMT 기준, 한국 시간대로 변환
                    date_obj = date_obj.replace(tzinfo=pytz.UTC).astimezone(KST)
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                except Exception as e:
                    logger.warning(
                        f"Google News 날짜 파싱 실패: {pub_date_raw}, 오류: {str(e)}"
                    )
                    formatted_date = get_korea_time().strftime("%Y-%m-%d")
            else:
                formatted_date = get_korea_time().strftime("%Y-%m-%d")

            news_items.append(
                NewsSearchItem(
                    title=title,
                    link=link,
                    pubDate=formatted_date,
                )
            )

        logger.info(f"Google News RSS 검색 완료: {len(news_items)}개 결과")
        return news_items

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error("Google News RSS 호출 타임아웃")
        raise HTTPException(
            status_code=504,
            detail="Google News RSS 호출 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        )
    except requests.exceptions.HTTPError as e:
        logger.error("Google News RSS HTTP 오류: %s - %s", e.response.status_code, _redact_secrets(e.response.text or ""))
        raise HTTPException(
            status_code=500,
            detail="Google News RSS 호출 중 오류가 발생했습니다. 상태 코드: " + str(e.response.status_code),
        )
    except requests.exceptions.RequestException as e:
        logger.error("Google News RSS 요청 오류: %s", _redact_secrets(str(e)))
        raise HTTPException(
            status_code=500,
            detail="Google News RSS 호출 중 오류가 발생했습니다.",
        )
    except Exception as e:
        logger.error("Google News RSS 처리 중 예상치 못한 오류: %s", _redact_secrets(str(e)), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Google News RSS 호출 중 오류가 발생했습니다.",
        )


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
        logger.error("네이버 뉴스 API HTTP 오류: %s - %s", e.response.status_code, _redact_secrets(e.response.text or ""))
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
                detail="네이버 뉴스 API 호출 중 오류가 발생했습니다. 상태 코드: " + str(e.response.status_code),
            )
    except requests.exceptions.RequestException as e:
        logger.error("네이버 뉴스 API 요청 오류: %s", _redact_secrets(str(e)))
        raise HTTPException(
            status_code=500,
            detail="네이버 뉴스 API 호출 중 오류가 발생했습니다.",
        )
    except Exception as e:
        logger.error("예상치 못한 오류 발생: %s", _redact_secrets(str(e)), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="예상치 못한 오류가 발생했습니다.",
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
            f"{i+1}. " + (f"[{item.keyword}] " if getattr(item, 'keyword', None) else "") + f"<{item.link}|{item.title}> ({item.pubDate})"
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
        logger.error("Slack Webhook HTTP 오류: %s - %s", e.response.status_code, _redact_secrets(e.response.text or ""))
        return False
    except requests.exceptions.RequestException as e:
        logger.error("Slack Webhook 요청 오류: %s", _redact_secrets(str(e)))
        return False
    except Exception as e:
        logger.error("Slack 알림 전송 중 예상치 못한 오류: %s", _redact_secrets(str(e)), exc_info=True)
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
    뉴스를 검색하고 Slack 알림을 전송합니다.
    - provider="naver": 네이버 뉴스 검색 API 사용
    - provider="google": Google News RSS 사용
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
        
        keywords = parse_keywords(request.keyword)
        if not keywords:
            raise HTTPException(status_code=400, detail="검색 키워드를 입력해주세요.")
        keyword_display = ", ".join(keywords)

        logger.info(
            f"뉴스 검색 요청: keywords={keywords}, start_date={start_date}, end_date={end_date}, provider={request.provider}"
        )

        # 키워드별로 검색 후 합침 (각 기사에 keyword 태그)
        news_items: List[NewsSearchItem] = []
        for kw in keywords:
            if request.provider == "naver":
                items = get_naver_news(
                    keyword=kw,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=10,
                    sort_by=request.sort_by,
                    use_relevance_filter=request.use_relevance_filter,
                )
            else:
                items = get_google_news(keyword=kw, max_results=30)
            for item in items:
                news_items.append(
                    NewsSearchItem(
                        title=item.title,
                        link=item.link,
                        pubDate=item.pubDate,
                        keyword=kw,
                    )
                )

        period = f"{start_date} ~ {end_date}"
        slack_sent = send_slack_notification(keyword_display, news_items, period)

        if slack_sent:
            message = f"Slack으로 {len(news_items)}개의 뉴스를 전송했습니다"
        else:
            message = "Slack 전송에 실패했습니다. SLACK_WEBHOOK_URL 환경변수를 확인해주세요."

        logger.info(f"뉴스 검색 완료: keywords={keywords}, news_count={len(news_items)}, slack_sent={slack_sent}")

        return NewsSearchResponse(
            keyword=keyword_display,
            keywords=keywords,
            period=period,
            news_count=len(news_items),
            news=news_items,
            slack_sent=slack_sent,
            message=message,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("뉴스 검색 중 예상치 못한 오류: %s", _redact_secrets(str(e)), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="예상치 못한 오류가 발생했습니다."
        )


@app.post("/research/search", response_model=ResearchSearchResponse)
def search_research(request: ResearchSearchRequest = Body(...)):
    """
    연구소/정부/국제기구 등의 자료를 검색합니다.
    키워드는 쉼표/줄바꿈으로 여러 개 입력 가능하며, 키워드별로 검색한 결과를 합쳐 반환합니다.
    """
    try:
        keywords = parse_keywords(request.keyword)
        if not keywords:
            raise HTTPException(status_code=400, detail="검색 키워드를 입력해주세요.")

        logger.info(
            f"연구/정부 자료 검색 요청: keywords={keywords}, language={request.language}, max_results={request.max_results}"
        )

        items = get_research_results(
            keywords=keywords,
            language=request.language,
            max_results_per_keyword=request.max_results,
            start_date=request.start_date,
            end_date=request.end_date,
            date_restrict=request.date_restrict,
        )

        message = (
            f"{len(items)}개의 연구/정부 자료를 검색했습니다 (키워드 {len(keywords)}개)."
            if items
            else "검색 결과가 없습니다."
        )
        keyword_display = ", ".join(keywords)

        return ResearchSearchResponse(
            keyword=keyword_display,
            keywords=keywords,
            total_results=len(items),
            items=items,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("연구/정부 자료 검색 중 예상치 못한 오류: %s", _redact_secrets(str(e)), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="연구/정부 자료 검색 중 예상치 못한 오류가 발생했습니다."
        )

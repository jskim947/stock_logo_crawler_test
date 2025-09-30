# Playwright + aiohttp 구현 가이드

## 1. 의존성 및 설치

### 1.1 requirements.txt
```txt
# 웹 크롤링
playwright>=1.55.0
aiohttp>=3.12.0
fake-useragent>=2.2.0

# 이미지 처리
Pillow>=10.0.0

# 데이터베이스
psycopg2-binary>=2.9.0

# API 서버
fastapi>=0.116.0
uvicorn>=0.35.0

# 설정 관리
python-dotenv>=1.1.0
pydantic>=2.11.0

# 로깅
loguru>=0.7.0

# 기타
aiofiles>=24.0.0

# HTTP 클라이언트
requests>=2.31.0
```

### 1.2 Playwright 브라우저 설치
```bash
# Playwright 브라우저 설치
playwright install chromium

# 또는 Docker에서
RUN playwright install chromium
```

## 2. 환경 설정

### 2.1 .env 파일
```bash
# Playwright 설정
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_VIEWPORT_WIDTH=1920
PLAYWRIGHT_VIEWPORT_HEIGHT=1080
PLAYWRIGHT_TIMEOUT=30000
PLAYWRIGHT_BROWSER_ARGS=--no-sandbox,--disable-blink-features=AutomationControlled

# aiohttp 설정
AIOHTTP_TIMEOUT=30
AIOHTTP_CONNECTION_LIMIT=100
AIOHTTP_CONNECTION_LIMIT_PER_HOST=30
AIOHTTP_KEEPALIVE_TIMEOUT=30

# User-Agent 설정
USE_FAKE_USERAGENT=true
UA_ROTATION_INTERVAL=300
UA_ROTATION_FREQUENCY=10

# 크롤링 설정
MAX_CONCURRENT_REQUESTS=4
EXCLUDED_URL_PATTERNS=country/US--big.svg,placeholder,default

# 데이터베이스
DATABASE_URL=postgresql://user:pass@host:5432/db

# MinIO 설정
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=logos
MINIO_SECURE=false

# logo.dev 설정
LOGO_DEV_TOKEN=your_token_here
LOGO_DEV_DAILY_LIMIT=5000
LOGO_DEV_BASE_URL=https://img.logo.dev

# 이미지 변환
DEFAULT_QUALITY=95
SUPPORTED_SIZES=240,300
SUPPORTED_FORMATS=png,webp
```

## 3. 핵심 구현

### 3.1 Playwright 크롤러
```python
import asyncio
import os
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from loguru import logger

class PlaywrightCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.headless = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        self.viewport = {
            'width': int(os.getenv('PLAYWRIGHT_VIEWPORT_WIDTH', '1920')),
            'height': int(os.getenv('PLAYWRIGHT_VIEWPORT_HEIGHT', '1080'))
        }
        self.timeout = int(os.getenv('PLAYWRIGHT_TIMEOUT', '30000'))
    
    async def crawl_tradingview(self, ticker: str) -> str:
        """TradingView에서 로고 URL 추출"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-web-security'
                ]
            )
            
            context = await browser.new_context(
                user_agent=self.ua.random,
                viewport=self.viewport,
                locale='en-US',
                timezone_id='America/New_York',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            page = await context.new_page()
            
            # 자동화 감지 우회
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            try:
                url = f'https://tradingview.com/symbols/{ticker}/news/'
                await page.goto(url, timeout=self.timeout)
                
                # 로고 이미지 대기 및 추출
                await page.wait_for_selector('img[src*="logo"]', timeout=10000)
                logo_element = await page.query_selector('img[src*="logo"]')
                
                if logo_element:
                    logo_url = await logo_element.get_attribute('src')
                    logger.info(f"Found logo for {ticker}: {logo_url}")
                    return logo_url
                else:
                    logger.warning(f"No logo found for {ticker}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error crawling {ticker}: {e}")
                return None
            finally:
                await browser.close()
```

### 3.2 aiohttp 클라이언트
```python
import aiohttp
import asyncio
from fake_useragent import UserAgent
from loguru import logger

class AiohttpClient:
    def __init__(self):
        self.ua = UserAgent()
        self.timeout = aiohttp.ClientTimeout(
            total=int(os.getenv('AIOHTTP_TIMEOUT', '30')),
            connect=10
        )
        self.connector = aiohttp.TCPConnector(
            limit=int(os.getenv('AIOHTTP_CONNECTION_LIMIT', '100')),
            limit_per_host=int(os.getenv('AIOHTTP_CONNECTION_LIMIT_PER_HOST', '30')),
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=int(os.getenv('AIOHTTP_KEEPALIVE_TIMEOUT', '30'))
        )
    
    async def download_logo(self, url: str) -> bytes:
        """로고 이미지 다운로드"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Referer': 'https://tradingview.com/'
        }
        
        async with aiohttp.ClientSession(
            headers=headers,
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        logger.info(f"Downloaded logo: {len(data)} bytes")
                        return data
                    else:
                        logger.warning(f"Failed to download logo: {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Error downloading logo: {e}")
                return None
    
    async def call_logo_dev(self, api_domain: str) -> bytes:
        """logo.dev API 호출"""
        token = os.getenv('LOGO_DEV_TOKEN')
        if not token:
            logger.error("LOGO_DEV_TOKEN not set")
            return None
        
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        }
        
        url = f"{os.getenv('LOGO_DEV_BASE_URL')}/{api_domain}?token={token}&format=png&size=256&retina=true"
        
        async with aiohttp.ClientSession(
            headers=headers,
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        logger.info(f"Downloaded from logo.dev: {len(data)} bytes")
                        return data
                    else:
                        logger.warning(f"logo.dev API failed: {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Error calling logo.dev: {e}")
                return None
```

### 3.3 통합 크롤러
```python
import asyncio
from typing import Optional
from PIL import Image
import io

class IntegratedCrawler:
    def __init__(self):
        self.playwright_crawler = PlaywrightCrawler()
        self.aiohttp_client = AiohttpClient()
        self.db_connection = None
    
    async def crawl_logo(self, infomax_code: str, ticker: str, api_domain: str = None) -> Optional[bytes]:
        """통합 로고 크롤링"""
        
        # 1. TradingView 크롤링 시도
        logo_url = await self.playwright_crawler.crawl_tradingview(ticker)
        if logo_url:
            logo_data = await self.aiohttp_client.download_logo(logo_url)
            if logo_data:
                return logo_data
        
        # 2. logo.dev API 시도
        if api_domain:
            logo_data = await self.aiohttp_client.call_logo_dev(api_domain)
            if logo_data:
                return logo_data
        
        logger.warning(f"No logo found for {infomax_code}")
        return None
    
    async def process_logo(self, infomax_code: str, ticker: str, api_domain: str = None):
        """로고 처리 및 저장"""
        try:
            # 로고 크롤링
            logo_data = await self.crawl_logo(infomax_code, ticker, api_domain)
            if not logo_data:
                return False
            
            # 이미지 변환
            converted_images = await self.convert_images(logo_data)
            
            # MinIO 업로드
            minio_keys = await self.upload_to_minio(infomax_code, logo_data, converted_images)
            
            # DB 저장
            await self.save_to_database(infomax_code, minio_keys)
            
            logger.info(f"Successfully processed logo for {infomax_code}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing logo for {infomax_code}: {e}")
            return False
    
    async def convert_images(self, svg_data: bytes) -> dict:
        """SVG를 다양한 크기로 변환"""
        sizes = [240, 300]
        formats = ['png', 'webp']
        results = {}
        
        try:
            # SVG를 PIL Image로 변환
            svg_image = Image.open(io.BytesIO(svg_data))
            
            for size in sizes:
                for format_name in formats:
                    # 크기 조정
                    resized = svg_image.resize((size, size), Image.Resampling.LANCZOS)
                    
                    # 포맷 변환
                    buffer = io.BytesIO()
                    if format_name == 'png':
                        resized.save(buffer, format='PNG', optimize=True)
                    elif format_name == 'webp':
                        resized.save(buffer, format='WEBP', quality=95, optimize=True)
                    
                    results[f"{size}_{format_name}"] = buffer.getvalue()
            
            return results
            
        except Exception as e:
            logger.error(f"Error converting images: {e}")
            return {}
```

## 4. 성능 최적화

### 4.1 동시성 제어
```python
import asyncio
from asyncio import Semaphore

class ConcurrentCrawler:
    def __init__(self, max_concurrent: int = 4):
        self.semaphore = Semaphore(max_concurrent)
        self.crawler = IntegratedCrawler()
    
    async def crawl_batch(self, tickers: list):
        """배치 크롤링"""
        tasks = []
        for ticker_info in tickers:
            task = self.crawl_with_semaphore(ticker_info)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def crawl_with_semaphore(self, ticker_info: dict):
        """세마포어로 동시성 제어"""
        async with self.semaphore:
            return await self.crawler.process_logo(
                ticker_info['infomax_code'],
                ticker_info['ticker'],
                ticker_info.get('api_domain')
            )
```

### 4.2 데이터베이스 중복 체크
```python
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseManager:
    def __init__(self):
        self.connection = None
    
    def connect(self):
        """데이터베이스 연결"""
        self.connection = psycopg2.connect(
            os.getenv('DATABASE_URL'),
            cursor_factory=RealDictCursor
        )
    
    def check_duplicate(self, logo_hash: str) -> bool:
        """중복 체크"""
        if not self.connection:
            self.connect()
        
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM logos WHERE logo_hash = %s AND is_deleted = FALSE",
                (logo_hash,)
            )
            return cursor.fetchone() is not None
    
    def check_quota(self, provider: str) -> bool:
        """쿼터 체크"""
        if not self.connection:
            self.connect()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self.connection.cursor() as cursor:
            # 오늘 사용량 조회
            cursor.execute("""
                SELECT used_count FROM ext_api_quota 
                WHERE api_name = %s AND quota_date = %s
            """, (provider, today))
            
            result = cursor.fetchone()
            if result:
                used_count = result['used_count']
            else:
                used_count = 0
            
            # 제한 확인
            limit = int(os.getenv(f'{provider.upper()}_DAILY_LIMIT', '5000'))
            return used_count < limit
    
    def update_quota(self, provider: str):
        """쿼터 사용량 업데이트"""
        if not self.connection:
            self.connect()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO ext_api_quota (api_name, quota_date, used_count, max_count)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT (api_name, quota_date)
                DO UPDATE SET used_count = ext_api_quota.used_count + 1
            """, (provider, today, int(os.getenv(f'{provider.upper()}_DAILY_LIMIT', '5000'))))
            
            self.connection.commit()
```

## 5. 모니터링 및 로깅

### 5.1 로깅 설정
```python
from loguru import logger
import sys

# 로깅 설정
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/crawler_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)
```

### 5.2 성능 메트릭
```python
import time
from dataclasses import dataclass

@dataclass
class CrawlMetrics:
    success_count: int = 0
    failure_count: int = 0
    total_time: float = 0.0
    avg_response_time: float = 0.0
    
    def add_result(self, success: bool, response_time: float):
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.total_time += response_time
        total_requests = self.success_count + self.failure_count
        self.avg_response_time = self.total_time / total_requests if total_requests > 0 else 0

class MetricsCollector:
    def __init__(self):
        self.metrics = CrawlMetrics()
    
    def record_crawl(self, success: bool, response_time: float):
        self.metrics.add_result(success, response_time)
        logger.info(f"Crawl result: success={success}, time={response_time:.2f}s")
    
    def get_summary(self):
        return {
            "success_rate": self.metrics.success_count / (self.metrics.success_count + self.metrics.failure_count) * 100,
            "avg_response_time": self.metrics.avg_response_time,
            "total_requests": self.metrics.success_count + self.metrics.failure_count
        }
```

## 6. Docker 설정

### 6.1 Dockerfile
```dockerfile
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps

# 앱 코드 복사
COPY . /app
WORKDIR /app

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 실행
CMD ["python", "main.py"]
```

### 6.2 docker-compose.yml
```yaml
version: '3.8'

services:
  crawler:
    build: .
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/logos
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - postgres
      - minio
    volumes:
      - ./logs:/app/logs

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=logos
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data


  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"

volumes:
  postgres_data:
  minio_data:
```

## 7. 결론

**Playwright + aiohttp 기반 구현의 장점:**

- ✅ **성능**: Selenium 대비 2-3배 빠른 크롤링
- ✅ **안정성**: 더 안정적인 동적 요소 처리
- ✅ **확장성**: 비동기 처리로 동시성 향상
- ✅ **유지보수**: 간단한 설정 관리
- ✅ **모니터링**: 상세한 로깅 및 메트릭

**핵심 구현 포인트:**
1. Playwright로 TradingView 크롤링
2. aiohttp로 logo.dev API 호출
3. fake_useragent로 차단 방지
4. Pillow로 이미지 변환
5. PostgreSQL로 중복 체크 및 쿼터 관리

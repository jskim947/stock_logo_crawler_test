# 로고 크롤링 시스템 구현 가이드

## 1. 시스템 구성

### 1.1 기술 스택
- **Python**: Playwright(TradingView) + aiohttp(logo.dev)
- **이미지 처리**: Pillow (SVG → PNG/WebP 변환)
- **데이터베이스**: PostgreSQL
- **스토리지**: MinIO (S3 호환)
- **API**: FastAPI
- **진행상황**: 파일 기반 (JSON)
- **기존 API 연동**: HTTP 클라이언트를 통한 외부 API 연동

### 1.2 Docker 구성
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: logo_system
      POSTGRES_USER: logo_user
      POSTGRES_PASSWORD: logo_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"

  crawler:
    build: ./crawler
    environment:
      - DATABASE_URL=postgresql://logo_user:logo_pass@postgres:5432/logo_system
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    depends_on:
      - postgres
      - minio

  api:
    build: ./api
    environment:
      - DATABASE_URL=postgresql://logo_user:logo_pass@postgres:5432/logo_system
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - minio

volumes:
  postgres_data:
```

## 2. 데이터베이스 스키마

### 2.1 테이블 생성
```sql
-- logo_master (마스터 데이터)
CREATE MATERIALIZED VIEW logo_master AS
SELECT 
    infomax_code,
    crawling_ticker,
    api_domain,
    fs_entity_id,
    fs_exchange,
    sprovider
FROM tickers 
WHERE crawling_ticker IS NOT NULL;

-- logos (최신 로고 관리)
CREATE TABLE logos (
    logo_id SERIAL PRIMARY KEY,
    logo_hash VARCHAR(32) NOT NULL UNIQUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- logo_files (파일 메타데이터)
CREATE TABLE logo_files (
    file_id SERIAL PRIMARY KEY,
    logo_id INTEGER REFERENCES logos(logo_id),
    minio_object_key VARCHAR(500) NOT NULL,
    file_format VARCHAR(10) NOT NULL,
    width INTEGER,
    height INTEGER,
    quality VARCHAR(20),
    file_size BIGINT,
    is_original BOOLEAN DEFAULT FALSE,
    upload_type VARCHAR(20) DEFAULT 'converted',
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- logo_deletion_logs (삭제 로그)
CREATE TABLE logo_deletion_logs (
    log_id SERIAL PRIMARY KEY,
    logo_id INTEGER REFERENCES logos(logo_id),
    deletion_type VARCHAR(20) NOT NULL CHECK (deletion_type IN ('soft_delete', 'replacement')),
    reason TEXT,
    performed_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ext_api_quota (API 쿼터 관리)
CREATE TABLE ext_api_quota (
    quota_id SERIAL PRIMARY KEY,
    api_name VARCHAR(50) NOT NULL,
    quota_date DATE NOT NULL,
    used_count INTEGER DEFAULT 0,
    max_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(api_name, quota_date)
);
```

### 2.2 인덱스
```sql
CREATE INDEX idx_logos_hash ON logos(logo_hash);
CREATE INDEX idx_logos_deleted ON logos(is_deleted);
CREATE INDEX idx_logo_files_logo_id ON logo_files(logo_id);
CREATE INDEX idx_logo_files_format ON logo_files(file_format);
CREATE INDEX idx_logo_files_upload_type ON logo_files(upload_type);
CREATE INDEX idx_logo_deletion_logs_logo_id ON logo_deletion_logs(logo_id);
```

## 3. 환경 설정

### 3.1 .env 파일
```bash
# 데이터베이스
DATABASE_URL=postgresql://logo_user:logo_pass@localhost:5432/logo_system

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=logos

# logo.dev API
LOGO_DEV_TOKEN=pk_DbneYGNgTgGeYI7zf8JWdw
LOGO_DEV_API_DOMAIN=img.logo.dev

# Playwright 설정
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_VIEWPORT_WIDTH=1920
PLAYWRIGHT_VIEWPORT_HEIGHT=1080
PLAYWRIGHT_TIMEOUT=30000

# aiohttp 설정
AIOHTTP_TIMEOUT=30
AIOHTTP_CONNECTION_LIMIT=100
AIOHTTP_CONNECTION_LIMIT_PER_HOST=30

# User-Agent 설정
USE_FAKE_USERAGENT=true
UA_ROTATION_INTERVAL=300

# 진행상황 모니터링
PROGRESS_DIR=progress
PROGRESS_CLEANUP_HOURS=24
```

## 4. 크롤러 구현

### 4.1 의존성 설치
```bash
pip install playwright>=1.55.0 aiohttp>=3.12.0 pillow>=10.0.0 fake-useragent>=2.2.0 psycopg2-binary>=2.9.0 fastapi>=0.116.0 uvicorn>=0.35.0 python-dotenv>=1.1.0 pydantic>=2.11.0 loguru>=0.7.0 aiofiles>=24.0.0
playwright install chromium
```

### 4.2 메인 크롤러
```python
import asyncio
import aiohttp
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from PIL import Image
import io

class LogoCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.progress_dir = Path(os.getenv('PROGRESS_DIR', 'progress'))
        self.progress_dir.mkdir(exist_ok=True)
        
    async def crawl_batch(self, tickers: list, job_id: str = None):
        """배치 크롤링 실행"""
        if not job_id:
            job_id = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 진행상황 시작
        self._start_progress(job_id, len(tickers))
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self.ua.random
                )
                
                for i, ticker_info in enumerate(tickers):
                    infomax_code = ticker_info['infomax_code']
                    ticker = ticker_info['ticker']
                    api_domain = ticker_info.get('api_domain')
                    
                    # 진행상황 업데이트
                    self._update_progress(job_id, f"{infomax_code} ({ticker})")
                    
                    try:
                        # TradingView 크롤링 시도
                        success = await self._crawl_tradingview(context, infomax_code, ticker)
                        
                        if not success and api_domain:
                            # logo.dev 크롤링 시도
                            success = await self._crawl_logo_dev(infomax_code, api_domain)
                        
                        if success:
                            self._update_progress(job_id, f"{infomax_code} ({ticker})", success=True)
                        else:
                            self._add_error(job_id, f"Failed to process {infomax_code}", infomax_code)
                            
                    except Exception as e:
                        self._add_error(job_id, str(e), infomax_code)
                
                await browser.close()
            
            # 작업 완료
            self._complete_progress(job_id, success=True)
            return job_id
            
        except Exception as e:
            self._complete_progress(job_id, success=False)
            self._add_error(job_id, str(e))
            raise
    
    async def _crawl_tradingview(self, context, infomax_code: str, ticker: str) -> bool:
        """TradingView 크롤링"""
        try:
            page = await context.new_page()
            
            # 스텔스 모드 설정
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # TradingView 페이지 접근
            url = f"https://www.tradingview.com/symbols/{ticker}/"
            await page.goto(url, timeout=30000)
            
            # 로고 이미지 찾기
            logo_element = await page.query_selector('img[src*="logo"]')
            if not logo_element:
                return False
            
            logo_url = await logo_element.get_attribute('src')
            if not logo_url:
                return False
            
            # 이미지 다운로드
            async with aiohttp.ClientSession() as session:
                async with session.get(logo_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return await self._process_logo(infomax_code, image_data, 'tradingview')
            
            return False
            
        except Exception as e:
            print(f"TradingView crawling error: {e}")
            return False
    
    async def _crawl_logo_dev(self, infomax_code: str, api_domain: str) -> bool:
        """logo.dev API 크롤링"""
        try:
            # 쿼터 체크
            if not await self._check_quota('logo_dev'):
                return False
            
            token = os.getenv('LOGO_DEV_TOKEN')
            api_domain = os.getenv('LOGO_DEV_API_DOMAIN')
            
            url = f"https://{api_domain}/{api_domain}?token={token}&format=png&size=300&fallback=404"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        await self._update_quota('logo_dev')
                        return await self._process_logo(infomax_code, image_data, 'logo_dev')
            
            return False
            
        except Exception as e:
            print(f"logo.dev crawling error: {e}")
            return False
    
    async def _process_logo(self, infomax_code: str, image_data: bytes, source: str) -> bool:
        """로고 처리 및 저장"""
        try:
            # logo_hash 생성
            logo_hash = hashlib.md5(f"{source}_{infomax_code}".encode()).hexdigest()
            
            # 중복 체크
            if await self._check_duplicate(logo_hash):
                return True
            
            # 이미지 변환
            converted_images = await self._convert_images(image_data)
            
            # MinIO 업로드
            minio_keys = await self._upload_to_minio(logo_hash, converted_images)
            
            # 데이터베이스 저장
            await self._save_to_database(logo_hash, minio_keys, source)
            
            return True
            
        except Exception as e:
            print(f"Logo processing error: {e}")
            return False
    
    async def _convert_images(self, image_data: bytes) -> Dict[str, bytes]:
        """이미지 변환 (SVG → PNG/WebP)"""
        converted = {}
        
        try:
            # 원본 이미지 로드
            image = Image.open(io.BytesIO(image_data))
            
            # 표준 사이즈로 변환
            sizes = [240, 300]
            formats = ['PNG', 'WebP']
            
            for size in sizes:
                for format in formats:
                    # 리사이즈
                    resized = image.resize((size, size), Image.Resampling.LANCZOS)
                    
                    # 바이트로 변환
                    output = io.BytesIO()
                    resized.save(output, format=format, quality=95)
                    converted[f"{format.lower()}_{size}"] = output.getvalue()
            
            return converted
            
        except Exception as e:
            print(f"Image conversion error: {e}")
            return {}
    
    def _start_progress(self, job_id: str, total_items: int):
        """진행상황 시작"""
        progress_data = {
            "job_id": job_id,
            "job_type": "crawling",
            "status": "running",
            "total_items": total_items,
            "processed_items": 0,
            "success_count": 0,
            "failure_count": 0,
            "start_time": datetime.now().isoformat(),
            "current_item": None,
            "errors": []
        }
        
        progress_file = self.progress_dir / f"{job_id}.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    def _update_progress(self, job_id: str, current_item: str, success: bool = True):
        """진행상황 업데이트"""
        progress_data = self._get_progress(job_id)
        if not progress_data:
            return
        
        progress_data["processed_items"] += 1
        progress_data["current_item"] = current_item
        
        if success:
            progress_data["success_count"] += 1
        else:
            progress_data["failure_count"] += 1
        
        # 진행률 계산
        progress_percentage = (progress_data["processed_items"] / progress_data["total_items"]) * 100
        progress_data["progress_percentage"] = round(progress_percentage, 2)
        
        # 예상 완료 시간 계산
        if progress_data["processed_items"] > 0:
            elapsed_time = (datetime.now() - datetime.fromisoformat(progress_data["start_time"])).total_seconds()
            avg_time_per_item = elapsed_time / progress_data["processed_items"]
            remaining_items = progress_data["total_items"] - progress_data["processed_items"]
            estimated_remaining_time = remaining_items * avg_time_per_item
            progress_data["estimated_completion_time"] = (datetime.now().timestamp() + estimated_remaining_time)
        
        # 파일 저장
        progress_file = self.progress_dir / f"{job_id}.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    def _complete_progress(self, job_id: str, success: bool = True):
        """작업 완료"""
        progress_data = self._get_progress(job_id)
        if not progress_data:
            return
        
        progress_data["status"] = "completed" if success else "failed"
        progress_data["end_time"] = datetime.now().isoformat()
        progress_data["progress_percentage"] = 100.0
        
        progress_file = self.progress_dir / f"{job_id}.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    def _add_error(self, job_id: str, error_message: str, item: str = None):
        """에러 추가"""
        progress_data = self._get_progress(job_id)
        if not progress_data:
            return
        
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "item": item,
            "message": error_message
        }
        
        progress_data["errors"].append(error_entry)
        
        # 최대 100개 에러만 유지
        if len(progress_data["errors"]) > 100:
            progress_data["errors"] = progress_data["errors"][-100:]
        
        progress_file = self.progress_dir / f"{job_id}.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    def _get_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """진행상황 조회"""
        progress_file = self.progress_dir / f"{job_id}.json"
        if progress_file.exists():
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
```

## 5. FastAPI 구현

### 5.1 의존성 설치
```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary minio
```

### 5.2 API 서버
```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from minio import Minio
import os
from typing import List, Dict, Any, Optional

app = FastAPI()

# 데이터베이스 연결
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

# MinIO 연결
minio_client = Minio(
    os.getenv('MINIO_ENDPOINT'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=False
)

@app.get("/api/v1/logos/{infomax_code}")
async def get_logo(infomax_code: str, format: str = "png", size: int = 300):
    """로고 조회"""
    with engine.connect() as conn:
        # 최신 로고 조회
        query = text("""
            SELECT lf.minio_object_key, lf.file_format, lf.width, lf.height
            FROM logos l
            JOIN logo_files lf ON l.logo_id = lf.logo_id
            WHERE l.logo_hash = (
                SELECT logo_hash FROM logos 
                WHERE logo_hash = md5(concat('tradingview_', :infomax_code))
                OR logo_hash = md5(concat('logo_dev_', :infomax_code))
                ORDER BY created_at DESC LIMIT 1
            )
            AND lf.file_format = :format
            AND lf.width = :size
            AND l.is_deleted = FALSE
            ORDER BY 
                CASE lf.upload_type 
                    WHEN 'manual' THEN 1 
                    WHEN 'crawled' THEN 2 
                    WHEN 'converted' THEN 3 
                END,
                CASE lf.data_source 
                    WHEN 'tradingview' THEN 1 
                    WHEN 'logo_dev' THEN 2 
                END,
                lf.created_at DESC
            LIMIT 1
        """)
        
        result = conn.execute(query, {
            'infomax_code': infomax_code,
            'format': format,
            'size': size
        }).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Logo not found")
        
        # MinIO에서 파일 다운로드
        try:
            response = minio_client.get_object('logos', result.minio_object_key)
            return FileResponse(
                response,
                media_type=f"image/{format}",
                filename=f"{infomax_code}_{size}.{format}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File retrieval error: {e}")

@app.get("/api/v1/progress/{job_id}")
async def get_progress(job_id: str):
    """진행상황 조회"""
    progress_file = Path(f"progress/{job_id}.json")
    if not progress_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.get("/api/v1/progress")
async def get_all_progress():
    """모든 작업 진행상황 조회"""
    progress_dir = Path("progress")
    all_progress = {}
    
    for progress_file in progress_dir.glob("*.json"):
        job_id = progress_file.stem
        with open(progress_file, 'r', encoding='utf-8') as f:
            all_progress[job_id] = json.load(f)
    
    return all_progress

@app.post("/api/v1/crawl/start")
async def start_crawling(tickers: List[Dict[str, str]]):
    """크롤링 시작"""
    crawler = LogoCrawler()
    job_id = asyncio.create_task(crawler.crawl_batch(tickers))
    return {"job_id": job_id, "status": "started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 6. 실행 방법

### 6.1 데이터베이스 초기화
```bash
psql -h localhost -U logo_user -d logo_system -f db_schema_and_ops.md
```

### 6.2 크롤러 실행
```bash
python crawler/main.py
```

### 6.3 API 서버 실행
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6.4 Docker 실행
```bash
docker-compose up -d
```

## 7. API 엔드포인트

### 7.1 사용자 API
#### GET /api/v1/logos/{infomax_code}
- **query**: `format=svg|png|webp`, `width`, `height`, `quality`
- **동작**: 최신 로고 선택 → 미리 변환된 파일 제공

### 7.2 관리자 API
#### POST /api/v1/admin/logos/upload
- **multipart/form-data**: `infomax_code`, `file`, `reason`, `uploaded_by`

#### DELETE /api/v1/admin/logos/{infomax_code}
- **body**: `reason`, `deleted_by`

### 7.3 Export API (대량 압축 다운로드)
#### POST /api/v1/exports/logos
- **body**: `filters{ infomax_codes[], file_format, width, height, upload_type_priority[], data_source_priority[] }`, `limit`, `expiration_hours`
- **응답**: `job_id`, `status=queued`

#### GET /api/v1/exports/logos/{job_id}
- **응답**: `status`, `file_url`, `expires_at`, `count`

### 7.4 Progress API (진행상황 모니터링)
#### GET /api/v1/progress/{job_id}
- **응답**: `job_id`, `job_type`, `status`, `total_items`, `processed_items`, `success_count`, `failure_count`, `progress_percentage`, `current_item`, `start_time`, `estimated_completion_time`, `errors[]`

#### GET /api/v1/progress
- **응답**: 모든 작업 진행상황 조회

#### GET /api/v1/progress/{job_id}/errors
- **query**: `limit=50`
- **응답**: `errors[]`, `total`

#### DELETE /api/v1/progress/{job_id}
- **동작**: 완료된 작업 진행상황 삭제

#### POST /api/v1/progress/cleanup
- **query**: `max_age_hours=24`
- **동작**: 오래된 작업 파일 정리

### 7.5 크롤링 관리
#### POST /api/v1/crawl/start
- **body**: `tickers[]`
- **응답**: `job_id`, `status=started`

### 7.6 정책
- **logo.dev**: 일일 5,000회 제한 준수(소진 시 스킵), `fallback=404` 기본 적용
- **정렬 우선순위**: upload_type(manual>crawled>converted) → data_source(tradingview>logo_dev) → created_at desc

## 8. 스케줄링 시스템

### 8.1 스케줄러 구현
```python
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict

class LogoScheduler:
    def __init__(self):
        self.crawler = LogoCrawler()
        self.db_manager = DatabaseManager()
    
    def schedule_daily_crawl(self):
        """매일 새벽 2시에 로고가 없는 종목 재수집"""
        schedule.every().day.at("02:00").do(self.crawl_missing_logos)
    
    def schedule_weekly_full_crawl(self):
        """매주 일요일 새벽 3시에 전체 재수집"""
        schedule.every().sunday.at("03:00").do(self.crawl_all_logos)
    
    async def crawl_missing_logos(self):
        """로고가 없는 종목들 재수집"""
        # 7일 이상 로고가 없는 종목 조회
        missing_logos = await self.get_missing_logos(days=7)
        
        if missing_logos:
            job_id = f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await self.crawler.crawl_batch(missing_logos, job_id)
            print(f"Scheduled crawl completed: {job_id}")
    
    async def crawl_all_logos(self):
        """전체 종목 재수집"""
        all_tickers = await self.get_all_tickers()
        
        if all_tickers:
            job_id = f"full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await self.crawler.crawl_batch(all_tickers, job_id)
            print(f"Full crawl completed: {job_id}")
    
    async def get_missing_logos(self, days: int = 7) -> List[Dict]:
        """로고가 없는 종목 조회"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = """
        SELECT lm.infomax_code, lm.crawling_ticker, lm.api_domain, lm.fs_regional_id
        FROM logo_master lm
        LEFT JOIN logos l ON l.logo_hash = md5(concat('tradingview_', lm.infomax_code))
            OR l.logo_hash = md5(concat('logo_dev_', lm.infomax_code))
        WHERE (l.logo_id IS NULL OR l.is_deleted = TRUE)
        AND lm.crawling_ticker IS NOT NULL
        ORDER BY lm.fs_regional_id, lm.infomax_code
        """
        
        return await self.db_manager.fetch_all(query)
    
    async def get_all_tickers(self) -> List[Dict]:
        """전체 종목 조회"""
        query = """
        SELECT infomax_code, crawling_ticker, api_domain, fs_regional_id
        FROM logo_master
        WHERE crawling_ticker IS NOT NULL
        ORDER BY fs_regional_id, infomax_code
        """
        
        return await self.db_manager.fetch_all(query)
    
    def run_scheduler(self):
        """스케줄러 실행"""
        self.schedule_daily_crawl()
        self.schedule_weekly_full_crawl()
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크

# 스케줄러 실행
if __name__ == "__main__":
    scheduler = LogoScheduler()
    scheduler.run_scheduler()
```

### 8.2 Docker 스케줄러 서비스
```yaml
# docker-compose.yml에 추가
  scheduler:
    build: ./scheduler
    environment:
      - DATABASE_URL=postgresql://logo_user:logo_pass@postgres:5432/logo_system
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    depends_on:
      - postgres
      - minio
    restart: unless-stopped
```

## 9. 서비스 연동 API

### 9.1 로고 조회 API (서비스용)
```python
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional, List

@app.get("/api/v1/service/logos")
async def get_logo_by_criteria(
    infomax_code: Optional[str] = None,
    fs_regional_id: Optional[str] = None,
    fs_entity_id: Optional[int] = None,
    format: str = "png",
    size: int = 300
):
    """서비스에서 사용할 로고 조회 API"""
    
    # 검색 조건 구성
    where_conditions = []
    params = {"format": format, "size": size}
    
    if infomax_code:
        where_conditions.append("lm.infomax_code = :infomax_code")
        params["infomax_code"] = infomax_code
    
    if fs_regional_id:
        where_conditions.append("lm.fs_regional_id = :fs_regional_id")
        params["fs_regional_id"] = fs_regional_id
    
    if fs_entity_id:
        where_conditions.append("lm.fs_entity_id = :fs_entity_id")
        params["fs_entity_id"] = fs_entity_id
    
    if not where_conditions:
        raise HTTPException(status_code=400, detail="At least one search criteria required")
    
    where_clause = " AND ".join(where_conditions)
    
    query = f"""
    SELECT lf.minio_object_key, lf.file_format, lf.width, lf.height,
           lm.infomax_code, lm.fs_regional_id, lm.fs_entity_id
    FROM logo_master lm
    JOIN logos l ON (
        l.logo_hash = md5(concat('tradingview_', lm.infomax_code))
        OR l.logo_hash = md5(concat('logo_dev_', lm.infomax_code))
    )
    JOIN logo_files lf ON l.logo_id = lf.logo_id
    WHERE {where_clause}
    AND lf.file_format = :format
    AND lf.width = :size
    AND l.is_deleted = FALSE
    ORDER BY 
        CASE lf.upload_type 
            WHEN 'manual' THEN 1 
            WHEN 'crawled' THEN 2 
            WHEN 'converted' THEN 3 
        END,
        CASE lf.data_source 
            WHEN 'tradingview' THEN 1 
            WHEN 'logo_dev' THEN 2 
        END,
        lf.created_at DESC
    LIMIT 1
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), params).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Logo not found")
        
        # MinIO에서 파일 다운로드
        try:
            response = minio_client.get_object('logos', result.minio_object_key)
            return FileResponse(
                response,
                media_type=f"image/{format}",
                filename=f"{result.infomax_code}_{size}.{format}",
                headers={
                    "X-Infomax-Code": result.infomax_code,
                    "X-FS-Regional-ID": result.fs_regional_id or "",
                    "X-FS-Entity-ID": str(result.fs_entity_id or ""),
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File retrieval error: {e}")

@app.get("/api/v1/service/logos/batch")
async def get_logos_batch(
    infomax_codes: List[str] = Query(...),
    format: str = "png",
    size: int = 300
):
    """여러 종목의 로고를 한번에 조회"""
    results = []
    
    for infomax_code in infomax_codes:
        try:
            logo_data = await get_logo_by_criteria(
                infomax_code=infomax_code,
                format=format,
                size=size
            )
            results.append({
                "infomax_code": infomax_code,
                "status": "success",
                "url": f"/api/v1/service/logos?infomax_code={infomax_code}&format={format}&size={size}"
            })
        except HTTPException as e:
            results.append({
                "infomax_code": infomax_code,
                "status": "error",
                "error": e.detail
            })
    
    return {"results": results}

@app.get("/api/v1/service/logos/search")
async def search_logos(
    fs_regional_id: Optional[str] = None,
    fs_entity_id: Optional[int] = None,
    has_logo: bool = True,
    limit: int = 100
):
    """로고 존재 여부 검색"""
    where_conditions = []
    params = {"limit": limit}
    
    if fs_regional_id:
        where_conditions.append("lm.fs_regional_id = :fs_regional_id")
        params["fs_regional_id"] = fs_regional_id
    
    if fs_entity_id:
        where_conditions.append("lm.fs_entity_id = :fs_entity_id")
        params["fs_entity_id"] = fs_entity_id
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    if has_logo:
        # 로고가 있는 종목
        query = f"""
        SELECT lm.infomax_code, lm.fs_regional_id, lm.fs_entity_id,
               l.created_at as logo_created_at,
               lf.file_format, lf.width, lf.height
        FROM logo_master lm
        JOIN logos l ON (
            l.logo_hash = md5(concat('tradingview_', lm.infomax_code))
            OR l.logo_hash = md5(concat('logo_dev_', lm.infomax_code))
        )
        JOIN logo_files lf ON l.logo_id = lf.logo_id
        WHERE {where_clause}
        AND l.is_deleted = FALSE
        ORDER BY l.created_at DESC
        LIMIT :limit
        """
    else:
        # 로고가 없는 종목
        query = f"""
        SELECT lm.infomax_code, lm.fs_regional_id, lm.fs_entity_id
        FROM logo_master lm
        LEFT JOIN logos l ON (
            l.logo_hash = md5(concat('tradingview_', lm.infomax_code))
            OR l.logo_hash = md5(concat('logo_dev_', lm.infomax_code))
        )
        WHERE {where_clause}
        AND (l.logo_id IS NULL OR l.is_deleted = TRUE)
        ORDER BY lm.infomax_code
        LIMIT :limit
        """
    
    with engine.connect() as conn:
        results = conn.execute(text(query), params).fetchall()
        
        return {
            "count": len(results),
            "has_logo": has_logo,
            "results": [dict(row) for row in results]
        }
```

### 9.2 기존 API 연동 구현
```python
# 기존 API 클라이언트 구현
import requests
from typing import Dict, Any, Optional

class ExistingAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    def query_table(self, schema: str, table: str, params: dict = None):
        """테이블 쿼리 실행"""
        try:
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/query"
            
            if params:
                query_params = []
                for key, value in params.items():
                    query_params.append(f"{key}={value}")
                url += "?" + "&".join(query_params)
            
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 기존 API 쿼리 오류: {e}")
            return None
    
    def upsert_data(self, schema: str, table: str, data: dict):
        """데이터 삽입/업데이트"""
        try:
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/upsert"
            
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 기존 API 데이터 입력 오류: {e}")
            return None

# 데이터 입력 순서
def save_logo_data(infomax_code: str, logo_hash: str, file_info: dict):
    """로고 데이터 저장 (올바른 순서)"""
    # 1. logos 테이블에 먼저 입력
    logo_data = {
        "data": {
            "logo_hash": logo_hash,
            "is_deleted": False
        },
        "conflict_columns": ["logo_hash"]
    }
    
    logo_result = existing_api.upsert_data("raw_data", "logos", logo_data)
    if not logo_result:
        return False
    
    logo_id = logo_result["data"]["logo_id"]
    
    # 2. logo_files 테이블에 입력 (logo_id 참조)
    file_data = {
        "data": {
            "logo_id": logo_id,
            "file_format": file_info["format"],
            "data_source": file_info["source"],
            "upload_type": file_info["upload_type"],
            "dimension_width": file_info["width"],
            "dimension_height": file_info["height"],
            "file_size": file_info["size"],
            "minio_object_key": file_info["minio_key"],
            "is_original": file_info.get("is_original", True)
        },
        "conflict_columns": ["file_id"]
    }
    
    file_result = existing_api.upsert_data("raw_data", "logo_files", file_data)
    return file_result is not None
```

### 9.3 로고 관리 API 구현
```python
# 로고 업로드/수정 API 구현
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import hashlib
from PIL import Image
import io

@app.post("/api/v1/logos/upload")
async def upload_logo(
    infomax_code: str = Form(...),
    file: UploadFile = File(...),
    format: str = Form("png"),
    size: int = Form(256),
    data_source: str = Form("manual")
):
    """신규 로고 업로드 (logo_hash 기반 파일명)"""
    try:
        # 1. 파일 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # 2. 이미지 처리
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # 3. 크기 조정
        if size != image.size[0]:
            image = image.resize((size, size), Image.Resampling.LANCZOS)
        
        # 4. logo_hash 생성
        logo_hash = generate_logo_hash(infomax_code)
        
        # 5. MinIO에 업로드
        minio_key = f"{infomax_code}/{logo_hash}_{size}.{format}"
        minio_client.put_object(
            MINIO_BUCKET, 
            minio_key, 
            io.BytesIO(image_data),
            length=len(image_data),
            content_type=f"image/{format}"
        )
        
        # 6. DB에 저장
        success = save_logo_data(infomax_code, logo_hash, {
            "format": format,
            "source": data_source,
            "upload_type": "manual",
            "width": size,
            "height": size,
            "size": len(image_data),
            "minio_key": minio_key,
            "is_original": True
        })
        
        if success:
            return {"status": "success", "message": "Logo uploaded successfully"}
        else:
            return {"status": "error", "message": "Failed to save logo data"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/logos/{infomax_code}")
async def update_logo(
    infomax_code: str,
    file: UploadFile = File(...),
    format: str = Form("png"),
    size: int = Form(256)
):
    """기존 로고 수정"""
    try:
        # 1. 기존 로고 조회
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "infomax_code": infomax_code,
            "limit": 1
        })
        
        if not master_response or not master_response.get('data'):
            raise HTTPException(status_code=404, detail="Logo not found")
        
        # 2. logo_hash 생성
        logo_hash = generate_logo_hash(infomax_code)
        
        # 3. 기존 파일 삭제 (MinIO)
        try:
            minio_client.remove_object(MINIO_BUCKET, f"{infomax_code}/{logo_hash}_{size}.{format}")
        except:
            pass  # 파일이 없어도 계속 진행
        
        # 4. 새 파일 업로드 (upload_logo와 동일한 로직)
        # ... (위 upload_logo와 동일한 처리)
        
        return {"status": "success", "message": "Logo updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/logos/{infomax_code}")
async def delete_logo(infomax_code: str):
    """로고 삭제 (논리적 삭제)"""
    try:
        # 1. logo_hash 생성
        logo_hash = generate_logo_hash(infomax_code)
        
        # 2. logos 테이블에서 is_deleted = true로 업데이트
        logo_data = {
            "data": {
                "logo_hash": logo_hash,
                "is_deleted": True,
                "deleted_at": datetime.now().isoformat(),
                "deleted_by": "api_user"
            },
            "conflict_columns": ["logo_hash"]
        }
        
        result = existing_api.upsert_data("raw_data", "logos", logo_data)
        
        if result:
            return {"status": "success", "message": "Logo deleted successfully"}
        else:
            return {"status": "error", "message": "Failed to delete logo"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 9.4 서비스 연동 예시
```python
# 다른 서비스에서 로고 조회하는 예시
import requests

class LogoServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def get_logo_by_infomax_code(self, infomax_code: str, format: str = "png", size: int = 256):
        """infomax_code로 로고 조회"""
        url = f"{self.base_url}/api/v1/service/logos"
        params = {
            "infomax_code": infomax_code,
            "format": format,
            "size": size
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.content
        else:
            return None
    
    def upload_logo(self, infomax_code: str, file_path: str, format: str = "png", size: int = 256):
        """로고 업로드"""
        url = f"{self.base_url}/api/v1/logos/upload"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'infomax_code': infomax_code,
                'format': format,
                'size': size,
                'data_source': 'manual'
            }
            
            response = requests.post(url, files=files, data=data)
            return response.json()
    
    def update_logo(self, infomax_code: str, file_path: str, format: str = "png", size: int = 256):
        """로고 수정"""
        url = f"{self.base_url}/api/v1/logos/{infomax_code}"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'format': format,
                'size': size
            }
            
            response = requests.put(url, files=files, data=data)
            return response.json()
    
    def delete_logo(self, infomax_code: str):
        """로고 삭제"""
        url = f"{self.base_url}/api/v1/logos/{infomax_code}"
        response = requests.delete(url)
        return response.json()
    
    def get_logo_by_fs_regional_id(self, fs_regional_id: str, format: str = "png", size: int = 256):
        """fs_regional_id로 로고 조회"""
        url = f"{self.base_url}/api/v1/service/logos"
        params = {
            "fs_regional_id": fs_regional_id,
            "format": format,
            "size": size
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.content
        else:
            return None
    
    def search_logos(self, fs_regional_id: str = None, has_logo: bool = True):
        """로고 검색"""
        url = f"{self.base_url}/api/v1/service/logos/search"
        params = {
            "fs_regional_id": fs_regional_id,
            "has_logo": has_logo
        }
        
        response = requests.get(url, params=params)
        return response.json()

# 사용 예시
client = LogoServiceClient("http://localhost:8000")

# infomax_code로 로고 조회
logo_data = client.get_logo_by_infomax_code("NAS:AAPL", "png", 256)

# fs_regional_id로 로고 조회
logo_data = client.get_logo_by_fs_regional_id("P01C89-R", "png", 256)

# 로고가 있는 종목 검색
results = client.search_logos(fs_regional_id="P01C89-R", has_logo=True)
```

## 10. 환경변수

```bash
# 필수 환경변수
DATABASE_URL=postgresql://user:pass@host:port/db
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
LOGO_DEV_TOKEN=pk_xxx
LOGO_DEV_API_DOMAIN=img.logo.dev

# 선택 환경변수
PLAYWRIGHT_HEADLESS=true
AIOHTTP_TIMEOUT=30
USE_FAKE_USERAGENT=true
PROGRESS_DIR=progress

# 스케줄링 설정
SCHEDULE_DAILY_TIME=02:00
SCHEDULE_WEEKLY_TIME=03:00
SCHEDULE_MISSING_DAYS=7
```

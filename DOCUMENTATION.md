# 로고 관리 시스템 문서

주식 로고 수집, 저장, 조회 및 관리 시스템의 전체 문서입니다.

## 목차
1. [시스템 개요](#시스템-개요)
2. [기술 스택](#기술-스택)
3. [데이터베이스 스키마](#데이터베이스-스키마)
4. [크롤링 구현](#크롤링-구현)
5. [API 구현](#api-구현)
6. [환경 설정](#환경-설정)
7. [배포 및 운영](#배포-및-운영)

## 시스템 개요

주식 로고 수집, 저장, 조회 및 관리 기능을 제공하는 시스템입니다. 웹사이트와 logo.dev를 통해 로고를 수집하고, MinIO에 저장하여 FastAPI를 통해 제공합니다.

### 주요 기능
- 웹사이트에서 로고 크롤링
- logo.dev API를 통한 로고 수집
- 이미지 변환 (SVG → PNG/WebP)
- MinIO를 통한 파일 저장
- FastAPI를 통한 REST API 제공
- 진행상황 모니터링

## 기술 스택

### 백엔드
- **Python**: Playwright(웹사이트) + aiohttp(logo.dev)
- **이미지 처리**: Pillow (SVG → PNG/WebP 변환)
- **데이터베이스**: PostgreSQL
- **스토리지**: MinIO (S3 호환)
- **API**: FastAPI
- **진행상황**: 파일 기반 (JSON)
- **기존 API 연동**: HTTP 클라이언트를 통한 외부 API 연동

### 의존성
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
python-dotenv>=1.0.1
pydantic>=2.11.0

# 로깅
loguru>=0.7.0

# 기타
aiofiles>=24.0.0
requests>=2.32.3
```

## 데이터베이스 스키마

### 마스터 테이블: logo_master

```sql
CREATE TABLE logo_master (
    infomax_code VARCHAR(50) PRIMARY KEY,
    terminal_code VARCHAR(50),
    infomax_code_export_name VARCHAR(50),
    terminal_code_export_name VARCHAR(50),
    crawling_ticker VARCHAR(50),
    isin VARCHAR(20),
    gts_exchange VARCHAR(10),
    fs_exchange VARCHAR(10),
    terminal_exchange VARCHAR(10),
    iso_mic VARCHAR(10),
    gts_ticker VARCHAR(20),
    terminal_ticker VARCHAR(20),
    fs_ticker VARCHAR(20),
    fs_regional_id VARCHAR(20),
    english_name VARCHAR(255),
    fs_entity_id VARCHAR(20),
    fs_entity_name VARCHAR(255),
    api_domain VARCHAR(255),
    sprovider VARCHAR(50),
    logo_hash VARCHAR(32) NOT NULL
);

CREATE INDEX idx_logo_master_crawling_ticker ON logo_master(crawling_ticker) WHERE crawling_ticker IS NOT NULL;
CREATE INDEX idx_logo_master_logo_hash ON logo_master(logo_hash);
CREATE INDEX idx_logo_master_sprovider ON logo_master(sprovider) WHERE sprovider IS NOT NULL;
CREATE INDEX idx_logo_master_fs_entity_id ON logo_master(fs_entity_id) WHERE fs_entity_id IS NOT NULL;
```

- **logo_hash 생성 로직**: `MD5(COALESCE(sprovider, fs_entity_id::text, infomax_code::text))`
- **우선순위**: sprovider > fs_entity_id > infomax_code

### 로고 관리 테이블

```sql
CREATE TABLE logos (
    logo_id SERIAL PRIMARY KEY,
    logo_hash VARCHAR(32) NOT NULL UNIQUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE logo_files (
    file_id SERIAL PRIMARY KEY,
    logo_id INTEGER NOT NULL REFERENCES logos(logo_id) ON DELETE CASCADE,
    file_format VARCHAR(20) NOT NULL,
    data_source VARCHAR(20) NOT NULL,
    upload_type VARCHAR(20) NOT NULL,
    uploaded_by VARCHAR(100),
    dimension_width INTEGER,
    dimension_height INTEGER,
    quality INTEGER,
    file_size INTEGER,
    minio_object_key VARCHAR(255) NOT NULL,
    is_original BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT uk_logo_files_minio_object_key UNIQUE (minio_object_key)
);

CREATE TABLE logo_deletion_logs (
    log_id SERIAL PRIMARY KEY,
    infomax_code VARCHAR(50) NOT NULL,
    logo_hash VARCHAR(32) NOT NULL,
    deletion_type VARCHAR(20) NOT NULL,
    deleted_by VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

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

### 제약조건

```sql
ALTER TABLE logo_files 
ADD CONSTRAINT chk_file_format CHECK (file_format IN ('svg', 'png', 'webp', 'jpg', 'jfif'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_data_source CHECK (data_source IN ('website', 'logo_dev', 'manual'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_upload_type CHECK (upload_type IN ('crawled', 'manual', 'converted', 'auto'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_quality CHECK (quality IS NULL OR (quality BETWEEN 1 AND 100));
ALTER TABLE logo_deletion_logs 
ADD CONSTRAINT chk_deletion_type CHECK (deletion_type IN ('soft_delete', 'replacement'));
```

## 크롤링 구현

### Playwright 설정

```python
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

class PlaywrightCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.headless = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        self.viewport = {
            'width': int(os.getenv('PLAYWRIGHT_VIEWPORT_WIDTH', '1920')),
            'height': int(os.getenv('PLAYWRIGHT_VIEWPORT_HEIGHT', '1080'))
        }
        self.timeout = int(os.getenv('PLAYWRIGHT_TIMEOUT', '30000'))
    
    async def crawl_website(self, ticker: str) -> str:
        """웹사이트에서 로고 URL 추출"""
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
                timezone_id='America/New_York'
            )
            
            page = await context.new_page()
            
            # 자동화 감지 우회
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            try:
                base_url = os.getenv('WEBSITE_BASE_URL', 'https://example.com')
                url = f'{base_url}/symbols/{ticker}/news/'
                await page.goto(url, timeout=self.timeout)
                
                # 로고 이미지 대기 및 추출
                await page.wait_for_selector('img[src*="logo"]', timeout=10000)
                logo_element = await page.query_selector('img[src*="logo"]')
                
                if logo_element:
                    logo_url = await logo_element.get_attribute('src')
                    return logo_url
                else:
                    return None
                    
            except Exception as e:
                logger.error(f"Error crawling {ticker}: {e}")
                return None
            finally:
                await browser.close()
```

### aiohttp 클라이언트

```python
import aiohttp

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
            'Referer': os.getenv('WEBSITE_BASE_URL', 'https://example.com') + '/'
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
                        return data
                    else:
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
                        return data
                    else:
                        return None
            except Exception as e:
                logger.error(f"Error calling logo.dev: {e}")
                return None
```

## API 구현

### 주요 엔드포인트

#### 로고 조회
- `GET /api/v1/logos/{infomax_code}` - 로고 조회
- `GET /api/v1/health` - 헬스 체크

#### 크롤링 관리
- `GET /api/v1/crawl/missing` - 미보유 로고 크롤링 트리거
- `POST /api/v1/crawl/single` - 단일 크롤링

#### 진행상황 모니터링
- `GET /api/v1/progress/{job_id}` - 진행상황 조회

### FastAPI 서버 설정

```python
from fastapi import FastAPI, HTTPException, Query, Depends, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Logo Management System",
    description="주식 로고 수집 및 관리 시스템",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 환경 설정

### .env 파일 예시

```bash
# MinIO 설정
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=logos

# 기존 API 연동
EXISTING_API_BASE=http://10.150.2.150:8004

# API 쿼터 관리
LOGO_DEV_DAILY_LIMIT=5000

# 크롤링 설정
LOGO_DEV_TOKEN=your_token_here
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

# 서버 설정
HOST=0.0.0.0
PORT=8005
RELOAD=true

# 이미지 처리 설정
IMAGE_SIZES=240,300

# 크롤링 소스 설정
WEBSITE_BASE_URL=https://example.com
```

## 배포 및 운영

### Docker Compose 설정

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
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"

  api:
    build: .
    environment:
      - DATABASE_URL=postgresql://logo_user:logo_pass@postgres:5432/logo_system
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    ports:
      - "8005:8005"
    depends_on:
      - postgres
      - minio

volumes:
  postgres_data:
  minio_data:
```

### 실행 방법

1. **의존성 설치**
```bash
pip install -r requirements.txt
playwright install chromium
```

2. **환경변수 설정**
```bash
cp .env.example .env
# .env 파일을 편집하여 실제 값으로 설정
```

3. **서버 실행**
```bash
python api_server.py
```

4. **Docker 실행**
```bash
docker-compose up -d
```

### API 문서
- Swagger UI: `http://localhost:8005/docs`
- ReDoc: `http://localhost:8005/redoc`

## 마스터 데이터

### 필드 설명
- **infomax_code**: 종목 고유 식별자
- **crawling_ticker**: 크롤링할 때 조회할 URL에 넣을 티커
- **fs_entity_name**: 기업코드
- **api_domain**: API로 확인할 웹사이트 주소
- **sprovider**: 운용사코드
- **logo_hash**: `md5(COALESCE(sprovider, fs_entity_id::text, infomax_code::text))`

### 기존 API 연동
- **API 엔드포인트**: `http://10.150.2.150:8004/api/schemas/raw_data/tables/logo_master/query`
- **응답 구조**: `{"schema": "raw_data", "table": "logo_master", "data": [...], "columns": [...]}`
- **쿼리 파라미터**: `limit`, `infomax_code`, `fs_regional_id`, `fs_entity_id` 등

### 샘플 데이터
```
infomax_code,crawling_ticker,fs_entity_name,api_domain,sprovider,logo_hash
AMX:AAA,AMEX-AAA,INVESTMENT MANAGERS SERIES TR II ALTERNATIVE ACCESS FIRST PR,,US0225,8485b1610697af8af71a8d8163c225e7
AMX:AAAA,AMEX-AAAA,AMPLIUS AGGRESSIVE ASSET ALLOCATION ETF,,US0557,68bd3a90c020c9656111bec4ab92ed03
AMX:AAAU,AMEX-AAAU,GOLDMAN SACHS PHYSICAL GOLD ETF UNIT,,US0086,85666ce04c4122e26bd12eec4b17e46d
```

## 유틸리티 스크립트

### check_db.py
기존 API를 통해 특정 종목의 로고 데이터를 확인하는 스크립트입니다.

**사용법:**
```bash
python scripts/check_db.py <INFOMAX_CODE> [provider]
```

**예시:**
```bash
# logo_dev 프로바이더로 확인
python scripts/check_db.py AMX:AIM

# website 프로바이더로 확인
python scripts/check_db.py AMX:AIM website
```

**기능:**
- `logo_hash` 계산 (MD5)
- `logos` 테이블에서 데이터 조회
- `logo_files` 테이블에서 파일 정보 조회

### query_db.py
기존 API를 통해 데이터베이스 테이블을 직접 쿼리하는 스크립트입니다.

**사용법:**
```bash
python scripts/query_db.py <schema> <table> <querystring>
```

**예시:**
```bash
# logos 테이블에서 logo_hash로 검색
python scripts/query_db.py raw_data logos "page=1&search_column=logo_hash&search=abcd1234"

# logo_master 뷰에서 infomax_code로 검색
python scripts/query_db.py raw_data logo_master "page=1&search_column=infomax_code&search=AMX:AIM"

# ext_api_quota 테이블에서 오늘 쿼터 사용량 확인
python scripts/query_db.py raw_data ext_api_quota "page=1&search_column=date_utc&search=2025-09-15"
```

### progress_manager.py
진행상황 파일을 관리하는 스크립트입니다.

## 운영 가이드

### 레이트 리밋 정책 (logo.dev)
- 일일 5,000회 호출 제한
- 남은 쿼터가 0이 되면 그날은 logo.dev 단계를 전역적으로 스킵
- 카운팅 방법: 성공·실패를 불문하고 logo.dev 호출 시 1 증가
- 저장 위치: PostgreSQL 테이블 `ext_api_quota`

### 이미지 처리
- 기본 포맷: PNG
- 기본 크기: 256px (요청별 오버라이드 가능, 600px 초과 비권장)
- 모노그램 억제: 없는 경우 404 받도록 `fallback=404` 기본 적용
- 다크/라이트 테마: 배경에 따라 선택 적용

### 모니터링
- 처리율, 오류율, 저장공간, 레이트리밋 상태 모니터링
- 진행상황은 JSON 파일로 관리
- 로그는 `loguru`를 사용하여 구조화된 로깅 제공

### 스크립트 사용 예시

#### 1. 특정 종목의 로고 데이터 확인
```bash
python scripts/check_db.py NAS:AAPL
```

#### 2. 오늘의 API 쿼터 사용량 확인
```bash
python scripts/query_db.py raw_data ext_api_quota "page=1&search_column=date_utc&search=$(date +%Y-%m-%d)"
```

#### 3. 미보유 로고 목록 확인
```bash
python scripts/query_db.py raw_data logo_master_with_status "page=1&search_column=has_any_file&search=false&limit=10"
```

### 주의사항
- 기존 API 서버가 실행 중이어야 합니다
- 네트워크 연결이 필요합니다
- 쿼리 파라미터는 URL 인코딩이 필요할 수 있습니다

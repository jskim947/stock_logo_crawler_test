# 주식 로고 크롤링 시스템 계획서

## 시스템 개요
- **목적**: 주식 종목의 로고 이미지를 자동으로 수집하고 관리
- **기술 스택**: Playwright(TradingView) + aiohttp(logo.dev) + Pillow + PostgreSQL + MinIO + FastAPI
- **주요 기능**: 자동 크롤링, 이미지 변환, 중복 방지, 진행상황 모니터링, REST API

## 데이터 모델
- **logo_master**: 마스터 데이터 (materialized view)
- **logo_master_with_status**: 마스터 데이터 + 파일 보유 상태 (materialized view)
- **logos**: 최신 로고 관리 (logo_hash 기반)
- **logo_files**: 파일 메타데이터 (원본 + 변환된 이미지, minio_object_key unique constraint)
- **ext_api_quota**: API 쿼터 관리 (일일 제한)

## 크롤러 구현
- **TradingView**: Playwright로 브라우저 자동화, CSS 선택자 기반 이미지 추출
- **logo.dev**: aiohttp로 API 호출, 일일 5,000회 제한
- **이미지 변환**: Pillow로 SVG → PNG/WebP (240, 300px)
- **진행상황**: 파일 기반 JSON 저장, 폴링 방식

## API 설계
- **로고 조회**: `GET /api/v1/logos/{infomax_code}?format=png&size=300`
- **로고 검색**: `GET /api/v1/logos/search?q=검색어&limit=10`
- **서비스 연동**: `GET /api/v1/service/logos` (infomax_code, fs_regional_id, fs_entity_id 지원)
- **로고 관리**: 
  - `POST /api/v1/logos/upload` - 신규 로고 업로드 (logo_hash 기반 파일명)
  - `PUT /api/v1/logos/{infomax_code}` - 기존 로고 수정
  - `DELETE /api/v1/logos/{infomax_code}` - 로고 삭제 (논리 삭제)
- **크롤링 관리**:
  - `POST /api/v1/crawl/single` - 단일 종목 크롤링
  - `POST /api/v1/crawl/batch` - 배치 크롤링
  - `POST /api/v1/crawl/missing` - 미보유 로고 크롤링 (조건 필터링 지원)
- **쿼터 관리**: `GET /api/v1/quota/status` - API 사용량 확인
- **통계**: `GET /api/v1/stats` - 시스템 통계
- **진행상황**: 실시간 모니터링 API

## 환경 설정
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
LOGO_DEV_DAILY_LIMIT=5000
EXISTING_API_BASE=http://10.150.2.150:8004
```

## 구현 순서
1. 데이터베이스 스키마 생성
2. 환경 설정
3. 크롤러 구현
4. API 서버 구현
5. 진행상황 모니터링 구현
6. Docker 구성

## 프로젝트 구조

### 📁 루트 디렉토리
- **README.md**: 프로젝트 개요 및 전체 가이드
- **TODO.md**: 프로젝트 진행 상황 및 할 일 목록
- **DATABASE.md**: 데이터베이스 스키마 정의
- **IMPLEMENTATION.md**: 통합 구현 가이드 (API 명세 포함)
- **CRAWLER.md**: 크롤러 구현 상세
- **MASTER_DATA.md**: 마스터 데이터 쿼리 가이드

### 📁 prototype/ 디렉토리 (실행 환경)
- **api_server.py**: 메인 FastAPI 서버
- **crawler.py**: 로고 크롤러 구현
- **test_api.py**: 통합 API 테스트 스위트
- **requirements.txt**: Python 의존성
- **Dockerfile**: Docker 이미지 빌드 설정
- **docker-compose.yml**: Docker Compose 설정
- **env_example.txt**: 환경변수 예시
- **run.bat/run.sh**: 실행 스크립트 (Windows/Linux)
- **README.md**: 프로토타입 사용법

### 📁 prototype/scripts/ 디렉토리
- **check_db.py**: DB 데이터 확인 유틸리티
- **query_db.py**: DB 쿼리 실행 유틸리티
- **README.md**: 스크립트 사용법

### 🚀 빠른 시작
1. **프로토타입 실행**: `cd prototype && docker-compose up -d`
2. **API 테스트**: `docker-compose exec logo-api-prototype python test_api.py`
3. **문서 확인**: http://localhost:8005/docs
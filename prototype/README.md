# 로고 관리 시스템 프로토타입

## 변경 사항 요약 (최근)
- 이미지 사이즈 정책: `.env`의 `IMAGE_SIZES`(예: `240,300`)에 정의된 사이즈만 생성/사용
- 기본값은 240, 300 두 개 사이즈입니다

## 환경변수 추가
```
IMAGE_SIZES=240,300
```

기존 FastAPI 서버를 활용하여 로고 조회/관리 기능을 제공하는 프로토타입 서버입니다.

## 🚀 빠른 시작

### 1. Docker로 실행
```bash
# 프로토타입 디렉토리로 이동
cd prototype

# Docker Compose로 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 2. 로컬 실행 (개발용)
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp env_example.txt .env

# 서버 실행
python api_server.py
```

**주의**: 로컬 실행 시 MinIO 서버가 별도로 필요합니다.

### 3. API 문서 확인
- **Swagger UI**: http://localhost:8005/docs
- **ReDoc**: http://localhost:8005/redoc
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin123)

## 📋 API 엔드포인트

### 로고 관리
- `GET /api/v1/logos/{infomax_code}` - 로고 조회 (logo_hash 기반 파일명)
- `GET /api/v1/service/logos` - 서비스 연동용 로고 조회
- `GET /api/v1/logos/search` - 로고 검색
- `POST /api/v1/logos/upload` - 신규 로고 업로드 (logo_hash 기반 파일명)
- `PUT /api/v1/logos/{infomax_code}` - 기존 로고 수정
- `DELETE /api/v1/logos/{infomax_code}` - 로고 삭제 (논리 삭제)
- `GET /api/v1/progress/{job_id}` - 작업 진행상황 조회
- `GET /api/v1/stats` - 시스템 통계

### 크롤링 기능
- `POST /api/v1/crawl/single` - 단일 로고 크롤링
- `POST /api/v1/crawl/batch` - 배치 로고 크롤링
- `POST /api/v1/crawl/missing` - 미보유 로고 크롤링 (조건 필터링 지원)
  - `fs_exchange`, `country`, `is_active`, `prefix` 필터 지원
  - `has_any_file=false` 조건으로 중복 방지

### 기존 API 연동
- `GET /api/v1/existing/schemas` - 기존 API 스키마 목록
- `GET /api/v1/existing/tables/{schema}` - 기존 API 테이블 목록
- `GET /api/v1/existing/query/{schema}/{table_name}` - 기존 API 테이블 쿼리

### 시스템
- `GET /` - 서버 상태 확인
- `GET /api/v1/health` - 헬스 체크
- `GET /api/v1/quota/status` - API 쿼터 상태 조회

### 디버깅 (개발용)
- `GET /api/v1/debug/test-api` - 기존 API 연결 상태 확인
- `POST /api/v1/debug/test-insert` - 데이터 입력 테스트 (logos, logo_files)

## 🔧 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `MINIO_ENDPOINT` | MinIO 서버 주소 (Docker) | `minio:9000` |
| `MINIO_ACCESS_KEY` | MinIO 액세스 키 | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO 시크릿 키 | `minioadmin123` |
| `MINIO_BUCKET` | MinIO 버킷명 | `logos` |
| `EXISTING_API_BASE` | 기존 API 서버 주소 | `http://10.150.2.150:8004` |
| `LOGO_DEV_TOKEN` | logo.dev API 토큰 | `pk_xxx` |
| `LOGO_DEV_DAILY_LIMIT` | logo.dev 일일 쿼터 한도 | `5000` |
| `PLAYWRIGHT_HEADLESS` | Playwright 헤드리스 모드 | `true` |
| `AIOHTTP_TIMEOUT` | aiohttp 타임아웃 | `30` |
| `USE_FAKE_USERAGENT` | User-Agent 회전 사용 | `true` |
| `PROGRESS_DIR` | 진행상황 파일 디렉토리 | `progress` |
| `IMAGE_SIZES` | 생성할 이미지 사이즈 (쉼표로 구분) | `240,300` |

## 🐳 Docker 명령어

```bash
# 빌드
docker-compose build

# 실행
docker-compose up -d

# 중지
docker-compose down

# 로그 확인
docker-compose logs -f logo-api-prototype

# 컨테이너 재시작
docker-compose restart logo-api-prototype
```

## 📊 사용 예시

### 로고 조회
```bash
# 기본 조회 (300px PNG)
curl "http://localhost:8005/api/v1/logos/NAS:AAPL"

# 특정 크기/형식 조회
curl "http://localhost:8005/api/v1/logos/NAS:AAPL?format=png&size=240"
```

### 서비스 연동
```bash
# infomax_code로 조회
curl "http://localhost:8005/api/v1/service/logos?infomax_code=NAS:AAPL"

# fs_regional_id로 조회
curl "http://localhost:8005/api/v1/service/logos?fs_regional_id=P01C89-R"
```

### 로고 관리
```bash
# 신규 로고 업로드
curl -X POST "http://localhost:8005/api/v1/logos/upload" \
  -F "infomax_code=NAS:AAPL" \
  -F "file=@logo.png" \
  -F "format=png" \
  -F "size=256" \
  -F "data_source=manual"

# 기존 로고 수정
curl -X PUT "http://localhost:8005/api/v1/logos/NAS:AAPL" \
  -F "file=@new_logo.png" \
  -F "format=png" \
  -F "size=256"

# 로고 삭제
curl -X DELETE "http://localhost:8005/api/v1/logos/NAS:AAPL"
```

### 크롤링 기능
```bash
# 단일 로고 크롤링
curl -X POST "http://localhost:8005/api/v1/crawl/single" \
  -H "Content-Type: application/json" \
  -d '{"infomax_code": "NAS:AAPL", "ticker": "NASDAQ-AAPL", "api_domain": "apple.com"}'

# 누락된 로고 자동 크롤링 (기본)
curl "http://localhost:8005/api/v1/crawl/missing?limit=10"

# 마스터 조건 필터 적용 크롤링
curl "http://localhost:8005/api/v1/crawl/missing?fs_exchange=NYSE&limit=50"
curl "http://localhost:8005/api/v1/crawl/missing?country=US&is_active=true&limit=100"
curl "http://localhost:8005/api/v1/crawl/missing?prefix=KRX:&limit=20"

# 배치 크롤링
curl -X POST "http://localhost:8005/api/v1/crawl/batch" \
  -H "Content-Type: application/json" \
  -d '[{"infomax_code": "NAS:AAPL", "ticker": "NASDAQ-AAPL", "api_domain": "apple.com"}]'
```

### 기존 API 연동
```bash
# 스키마 목록 조회
curl "http://localhost:8005/api/v1/existing/schemas"

# 테이블 목록 조회
curl "http://localhost:8005/api/v1/existing/tables/raw_data"

# 테이블 쿼리
curl "http://localhost:8005/api/v1/existing/query/raw_data/logo_master?limit=10"
```

### 쿼터 관리
```bash
# API 쿼터 상태 조회
curl "http://localhost:8005/api/v1/quota/status"

# 응답 예시:
# {
#   "date_utc": "2025-09-15",
#   "logo_dev": {
#     "used": 1250,
#     "limit": 5000,
#     "remaining": 3750,
#     "percentage": 25.0
#   }
# }
```

## 🔍 기존 API 연동

이 프로토타입은 기존 운영 중인 FastAPI 서버(`http://10.150.2.150:8004`)와 연동하여:
- `raw_data.logo_master` (Materialized View) - 마스터 데이터
- `raw_data.logos` - 로고 메타데이터
- `raw_data.logo_files` - 파일 메타데이터
- `raw_data.ext_api_quota` - API 쿼터 관리
- `raw_data.logo_master_with_status` - 미보유 상태 포함 마스터 뷰
- 데이터베이스 스키마 정보 조회
- 테이블 구조 확인
- 기존 데이터 쿼리
- **데이터 입력/업데이트**: `upsert` API를 통한 로고 및 파일 메타데이터 저장

## 🎯 새로운 기능

### 1. 일일 쿼터 관리
- **UTC 기준 일일 5,000건 제한**: `ext_api_quota` 테이블 기반 관리
- **자동 쿼터 체크**: logo.dev 호출 전 자동 검증
- **스마트 스킵**: 쿼터 초과 시 해당 소스만 제외하고 계속 진행
- **실시간 모니터링**: `/api/v1/quota/status`로 사용량 확인

### 2. 마스터 조건 필터 크롤링
- **다양한 필터 지원**: `fs_exchange`, `country`, `is_active`, `prefix` 등
- **미보유 로고만 크롤링**: `has_any_file=false` 조건으로 중복 방지
- **조건별 배치 처리**: 필터에 맞는 종목만 선별적 크롤링

### 3. 로고 관리 API
- **신규 업로드**: 이미지 자동 처리 (리사이즈, 포맷 변환)
- **기존 수정**: 동일한 `logo_hash` 사용으로 데이터 일관성 유지
- **논리적 삭제**: `is_deleted=True` 설정으로 안전한 삭제

### 기존 API 엔드포인트
- `GET /api/schemas/{schema}/tables/{table}/query` - 테이블 쿼리
- `POST /api/schemas/{schema}/tables/{table}/upsert` - 데이터 입력/업데이트
- `GET /api/schemas/{schema}/tables/{table}/schema` - 테이블 스키마 조회

### 데이터 입력 순서
1. **logos 테이블**: 로고 메타데이터 먼저 입력
2. **logo_files 테이블**: 파일 메타데이터 입력 (logo_id 외래키 참조)

## 🚨 주의사항

1. **네트워크**: 10.150.2.150 서버에 접근 가능해야 합니다
2. **기존 API**: 기존 FastAPI 서버(`http://10.150.2.150:8004`)가 실행 중이어야 합니다
3. **포트**: 8005, 9000, 9001 포트가 사용 가능해야 합니다
4. **Docker**: Docker 및 Docker Compose가 설치되어 있어야 합니다
5. **MinIO**: Docker로 자동 실행되며, `logos` 버킷도 자동 생성됩니다
6. **DB 스키마**: `raw_data.logo_master`, `raw_data.logos`, `raw_data.logo_files` 테이블/뷰가 존재해야 합니다
7. **크롤링**: Playwright 브라우저가 Docker 이미지에 포함되어 있습니다
8. **API 토큰**: logo.dev 사용 시 `LOGO_DEV_TOKEN` 환경변수 설정 필요
9. **데이터 제약조건**: 
   - `logo_hash`: 32자 제한 (MD5)
   - `data_source`: "tradingview", "logo.dev" 등 허용된 값
   - `upload_type`: "manual", "auto" 등 허용된 값

## 🔄 나중에 통합 예정

현재는 프로토타입용 독립적인 FastAPI 서버로 운영되며, 향후 메인 시스템과 통합할 예정입니다.

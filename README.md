# 로고 관리 시스템

주식 로고 수집, 저장, 조회 및 관리 기능을 제공하는 시스템입니다. TradingView와 logo.dev를 통해 로고를 수집하고, MinIO에 저장하여 FastAPI를 통해 제공합니다.

## 빠른 시작

1) 의존성 설치
```bash
pip install -r requirements.txt
```

2) 환경변수 준비
```bash
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
```

3) 서버 실행
```bash
python api_server.py
```

4) API 문서
- Swagger UI: `http://localhost:8005/docs`
- ReDoc: `http://localhost:8005/redoc`

## 주요 엔드포인트

- GET `/api/v1/health` 헬스 체크
- GET `/api/v1/logos/{infomax_code}` 로고 조회
- GET `/api/v1/progress/{job_id}` 진행상황 조회
- GET `/api/v1/crawl/missing` 미보유 로고 크롤링 트리거(필터 지원: `prefix`, `fs_exchange`, `country`, `is_active`)
- POST `/api/v1/crawl/single` 단일 크롤링

## NAS:Q 크롤링 테스트

```bash
python test_nasq.py
```
동작: `prefix=NAS:Q` 조건으로 미보유 종목을 수집하여 배치 크롤링을 시작하고 `job_id`로 진행상황을 확인합니다.

## 프로젝트 구조

```
stock_logo_crawler_test/
├── api_server.py          # FastAPI 서버 메인 파일
├── crawler.py             # 로고 크롤링 모듈
├── requirements.txt       # Python 의존성
├── .env.example          # 환경변수 예시
├── docker-compose.yml    # Docker Compose 설정
├── Dockerfile           # Docker 이미지 설정
├── scripts/             # 유틸리티 스크립트
│   ├── check_db.py
│   ├── progress_manager.py
│   └── query_db.py
├── docs/                # 문서
│   ├── README.md
│   ├── DATABASE.md
│   ├── IMPLEMENTATION.md
│   ├── CRAWLER.md
│   └── MASTER_DATA.md
└── test_nasq.py         # 테스트 파일
```

## 환경변수

주요 환경변수는 `.env.example` 파일을 참고하세요:
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- `EXISTING_API_BASE`, `LOGO_DEV_TOKEN`, `LOGO_DEV_DAILY_LIMIT`
- `PLAYWRIGHT_HEADLESS`, `AIOHTTP_TIMEOUT`, `USE_FAKE_USERAGENT`, `PROGRESS_DIR`
- `IMAGE_SIZES`

자세한 내용은 `DOCUMENTATION.md`를 참고하세요.
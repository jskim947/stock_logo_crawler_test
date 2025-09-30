# 프로토타입 도커 기반 전체 점검 결과 및 수정 리스트

## 실행 환경
- 실행 방식: Docker Compose (`prototype/docker-compose.yml`)
- 상태: `logo-api-prototype`, `logo-minio`, `logo-minio-init` 정상 구동 확인
- 헬스체크: `/api/v1/health` 200 OK (MinIO/기존 API 연결 정상)

## 기능 점검 결과

### 1) API 기본 동작
- `GET /` 정상 (200)
- `GET /api/v1/health` 정상 (200)
- `GET /api/v1/stats` 정상 (200), 통계 응답 OK
- `GET /api/v1/quota/status` 정상 (200)
- `GET /api/v1/debug/test-api` 정상 (200), 기존 API 연결 및 응답 파싱 OK

### 2) 로고 조회/검색
- `GET /api/v1/logos/{infomax_code}`: 현재 JSON 메타데이터 반환. README에는 이미지(PNG) 반환으로 안내되어 있어 동작/문서 불일치
- 실제 데이터 없는 종목 조회 시 404 처리되나, 예외 메시지가 500 래핑되어 반환되는 케이스 확인됨 (에러 핸들링 개선 필요)

### 3) 업로드/수정/삭제
- 업로드/수정/삭제 엔드포인트 존재. MinIO 및 DB 저장 경로/포맷은 동작 의존 (수동 테스트 이미지 준비 실패로 재검 필요)
- 파일 메타 저장 로직은 존재 (logos → logo_files 순으로 upsert)

### 4) 크롤링
- `POST /api/v1/crawl/single`: 현재 즉시 "received"만 반환하는 디버그용 구현. 실제 크롤링 미실행
- `POST /api/v1/crawl/batch`, `GET /api/v1/crawl/missing`: 배치 로직/쿼터 체크 코드 존재. 실제 이미지 저장/DB 반영은 `crawler.py` 경로 의존 (재검 필요)

## 규칙 대비 점검(중요 이슈)

1. 환경변수 하드코딩 문제
   - `prototype/docker-compose.yml`에 `LOGO_DEV_TOKEN` 하드코딩되어 있음
   - `api_server.py`, `crawler.py`에서 `os.getenv(key, default)` 형태로 코드 기본값 사용
   - 규칙: 환경변수는 코드 기본값 금지, `.env.example` 문서화 후 런타임에서만 주입

2. HTTP 클라이언트 사용 규칙 위반
   - `api_server.py` 내 기존 API 호출에 `requests` 사용 (규칙은 aiohttp 사용)

3. 로고 조회 응답 포맷 불일치
   - README: "기본 조회 (300px PNG)"로 이미지 스트리밍 기대
   - 구현: JSON 메타데이터 반환 (이미지 바이트 반환 아님)

4. 크롤링 엔드포인트 미구현 상태
   - `crawl/single`이 실제 크롤링을 수행하지 않음 (디버그 응답)

5. 파일 키/저장 규칙 불일치
   - 업로드: `logo_hash_size.format` 형태 사용
   - 크롤러: `converted/{infomax_code}_{size}.{ext}` 등 상이
   - 규칙: `logo_hash` 기준 일관 키 필요, 표준 사이즈 64/128/256/512 변환/저장

6. 인증/권한/레이트리밋 미구현
   - 규칙: 관리자 엔드포인트 JWT 인증, RBAC, 레이트리밋 필요

7. dotenv 로드 누락
   - 서버에서 `.env` 로드를 명시적으로 처리하지 않음 (docker-compose 환경 전달로만 동작)

8. 로깅/에러 처리 개선 필요
   - 표준화된 에러 응답 스키마 부재
   - `print` 기반 로깅 혼재, `loguru` 사용 권장

## 권장 수정 항목 (우선순위)

P0 ✅ 완료
- [x] `docker-compose.yml`에서 민감정보 제거 → `.env`로 이관 (`LOGO_DEV_TOKEN` 등)
- [x] `api_server.py` 기존 API 호출을 `aiohttp`로 전환, 타임아웃/재시도/예외 처리 표준화
- [x] `GET /api/v1/logos/{infomax_code}`를 실제 이미지 스트리밍 응답으로 변경 (PNG/WebP), 필요 시 `?format`/`?size` 지원
- [x] `POST /api/v1/crawl/single` 실제 크롤링 실행 연결 (`crawler.crawl_logo`) 및 비동기 처리/진행상황 반환
- [x] MinIO 오브젝트 키 규칙을 `logo_hash` 기준으로 통일. 크롤러/업로드 양쪽 정합성 확보

P1 ✅ 완료
- [x] 표준 사이즈(240/300) 변환/저장 일관화, Pillow 처리 공통 유틸로 분리
- [x] 관리자 엔드포인트에 JWT 인증/권한 적용, 레이트리밋 도입
- [x] `.env.example` 최신화 및 README/프로토타입 README 동기화 (이미지 응답 설명 포함)
- [x] `loguru` 기반 구조화 로깅, 요청 트레이싱/에러 코드 표준화

P2 ✅ 완료
- [x] 진행상황 파일 JSON 스키마 정리 및 보존/청소 정책 문서화
- [x] Dockerfile/compose에서 Playwright/브라우저 deps 캐시 최적화

## 재현/검증 메모
- 컨테이너 포트: API 8005, MinIO 9000/9001 확인됨
- 기존 API(`EXISTING_API_BASE`) 연결 정상, `logo_master`/`logos`/`logo_files` 조회 가능
- 통계/쿼터 엔드포인트 정상

## 후속 테스트 계획
- 테스트 이미지 준비 후 `POST /api/v1/logos/upload` → MinIO 저장 및 DB 반영 확인
- `GET /api/v1/logos/{infomax_code}?format=png&size=256`로 이미지 바이트 수신 확인 (구현 수정 후)
- `POST /api/v1/crawl/single` 실제 크롤링 성공/실패 케이스 수집 및 진행 파일 확인



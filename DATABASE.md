# 로고 관리 DB 스키마, 생성 쿼리, 용도 및 연계 문서

## 개요
- 본 문서는 `logo_master`를 기준으로 하는 로고 관리 DB 스키마, 생성 쿼리(DDL), 운영시 용도, 처리 방법, 시스템 간 연계 사항을 정리합니다.
- 애플리케이션 설정값은 환경변수에서 주입하며, 코드에 기본값을 하드코딩하지 않습니다.

***

## 1) 마스터: logo_master
- 실제 운영에서는 뷰(Materialized View 권장)로 관리. 아래는 테이블 정의 예시입니다.

```sql
CREATE TABLE logo_master (
    infomax_code VARCHAR(50) PRIMARY KEY,
    terminal_code VARCHAR(50),
    infomax_code_export_name VARCHAR(50),
    terminal_code_export_name VARCHAR(50),
    crawling_ticker VARCHAR(50),
    isin VARCHAR(20),
    gts_exchange VARCHAR(10),
    fs_exchange VARCHAR(10),  -- 종전 "팩셋거래소"와 동일 의미
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

- logo_hash 생성 로직: `MD5(COALESCE(sprovider, fs_entity_id::text, infomax_code::text))`
  - 우선순위: sprovider > fs_entity_id > infomax_code

## 1-1) 마스터 확장: logo_master_with_status
- logo_master + 파일 보유 상태를 포함한 확장 뷰

```sql
CREATE MATERIALIZED VIEW logo_master_with_status AS
SELECT 
    lm.*,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM logo_files lf 
            JOIN logos l ON lf.logo_id = l.logo_id 
            WHERE l.logo_hash = lm.logo_hash 
            AND lf.is_original = true
        ) THEN true 
        ELSE false 
    END as has_any_file
FROM logo_master lm;

CREATE INDEX idx_logo_master_with_status_has_any_file 
ON logo_master_with_status(has_any_file) 
WHERE has_any_file = false;
```

용도:
- 크롤러는 `crawling_ticker`로 TradingView를 조회
- API는 `infomax_code`로 들어온 요청을 `logo_hash`로 매핑
- `api_domain`은 logo.dev API 조회에 사용 (예: 아래 템플릿)

예시 (logo.dev 호출 템플릿):
```
https://img.logo.dev/{api_domain}?token=${LOGO_DEV_TOKEN}&retina=true
```
- `${LOGO_DEV_TOKEN}`은 환경변수로 관리하며 코드에 하드코딩하지 않습니다.

***

## 2) 로고 버전 및 파일

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
    
    -- Unique constraint for upsert operations
    CONSTRAINT uk_logo_files_minio_object_key UNIQUE (minio_object_key)
);

CREATE INDEX idx_logos_hash_deleted ON logos(logo_hash, is_deleted);
CREATE INDEX idx_logo_files_logo_id ON logo_files(logo_id);
CREATE INDEX idx_logo_files_format_size ON logo_files(logo_id, file_format, dimension_width, dimension_height, quality);
CREATE INDEX idx_logo_files_data_source ON logo_files(data_source);
CREATE INDEX idx_logo_files_upload_type ON logo_files(upload_type);

ALTER TABLE logo_files 
ADD CONSTRAINT chk_file_format CHECK (file_format IN ('svg', 'png', 'webp', 'jpg', 'jfif'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_data_source CHECK (data_source IN ('tradingview', 'logo_dev', 'manual'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_upload_type CHECK (upload_type IN ('crawled', 'manual', 'converted', 'auto'));
ALTER TABLE logo_files 
ADD CONSTRAINT chk_quality CHECK (quality IS NULL OR (quality BETWEEN 1 AND 100));
```

용도:
- `logos`: logo_hash별 최신 로고 관리, 삭제 상태 관리
- `logo_files`: 원본/변환 파일 저장, 형식/크기/품질 기준으로 재사용

제약조건:
- `uk_logo_files_minio_object_key`: minio_object_key에 대한 unique constraint
  - upsert 작업 시 중복 방지
  - 같은 MinIO 객체 경로는 하나의 레코드만 존재

처리 방법:
- 새 파일 업로드 시 `logos`의 기존 레코드 업데이트 또는 신규 삽입
- 원본 + 변환 파일은 `upload_type='converted'`로 구분하여 모두 저장
- 미리 변환: SVG → PNG/WebP (64, 128, 256, 512px)로 저장

### 로고 관리 API 지원
- **신규 업로드**: `POST /api/v1/logos/upload` - 파일 업로드 + DB 저장
- **로고 수정**: `PUT /api/v1/logos/{infomax_code}` - 기존 로고 교체
- **로고 삭제**: `DELETE /api/v1/logos/{infomax_code}` - 논리적 삭제 (is_deleted=true)
- **파일 형식**: PNG, WebP, SVG, JPG, JFIF 지원
- **데이터 소스**: tradingview, logo_dev, manual 지원
- **업로드 타입**: crawled, manual, converted, auto 지원

***

## 3) 삭제 감사 로그

```sql
CREATE TABLE logo_deletion_logs (
    log_id SERIAL PRIMARY KEY,
    infomax_code VARCHAR(50) NOT NULL,
    logo_hash VARCHAR(32) NOT NULL,
    deletion_type VARCHAR(20) NOT NULL,
    deleted_by VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_deletion_logs_infomax_code ON logo_deletion_logs(infomax_code);
CREATE INDEX idx_deletion_logs_logo_hash ON logo_deletion_logs(logo_hash);
CREATE INDEX idx_deletion_logs_created_at ON logo_deletion_logs(created_at);
CREATE INDEX idx_deletion_logs_deletion_type ON logo_deletion_logs(deletion_type);

ALTER TABLE logo_deletion_logs 
ADD CONSTRAINT chk_deletion_type CHECK (deletion_type IN ('soft_delete', 'replacement'));
```

용도:
- 수동 삭제, 교체 등의 행위 감사 및 복구 근거 확보

***

## 4) 조회 최적화 및 연계

```sql
-- 최신 로고 단건 조회 (메뉴얼 우선)
SELECT lf.*
FROM logo_master t
JOIN logos l ON t.logo_hash = l.logo_hash
JOIN logo_files lf ON l.logo_id = lf.logo_id
WHERE t.infomax_code = $1
  AND l.is_deleted = FALSE
ORDER BY 
  CASE lf.upload_type WHEN 'manual' THEN 1 WHEN 'crawled' THEN 2 WHEN 'converted' THEN 3 ELSE 4 END,
  CASE lf.data_source WHEN 'tradingview' THEN 1 WHEN 'logo_dev' THEN 2 ELSE 3 END,
  lf.created_at DESC
LIMIT 1;

-- 특정 형식/크기 파일 조회
SELECT lf.*
FROM logo_master t
JOIN logos l ON t.logo_hash = l.logo_hash
JOIN logo_files lf ON l.logo_id = lf.logo_id
WHERE t.infomax_code = $1
  AND l.is_deleted = FALSE
  AND lf.file_format = $2
  AND lf.dimension_width = $3
  AND lf.dimension_height = $4
  AND (lf.quality = $5 OR $5 IS NULL)
ORDER BY lf.created_at DESC
LIMIT 1;
```

연계:
- 크롤러: `logo_master.crawling_ticker` 사용해 TradingView 크롤링
- API: `infomax_code` → `logo_hash` 매핑 후 `logos/logo_files` 조회
- MinIO: `logo_files.minio_object_key`로 저장 객체 참조
- 크롤러 설정: 환경변수 또는 설정 파일로 XPath/wait/sleep/제외 패턴 주입 (예: `SELENIUM_WAIT`, `SELENIUM_SLEEP` 등)
- 입력 소스: 엑셀 파일 대신 데이터베이스 `logo_master`를 직접 조회하여 작업 대상 결정

레이트 리밋 정책 (logo.dev):
- 일일 5,000회 호출 제한. 크롤러는 일자별 카운터를 유지한다.
- 남은 쿼터가 0이 되면 그날은 logo.dev 단계를 전역적으로 스킵하고 다음 소스로 넘어간다.
- 카운팅 방법 예시:
  - 성공·실패를 불문하고 logo.dev 호출 시 1 증가
  - 저장 위치: Redis 키 `logo_dev:quota:YYYYMMDD` 또는 PostgreSQL 테이블 `ext_api_quota`
  - 자정(UTC 또는 운영 타임존) 기준 자동 초기화

PostgreSQL 예시 테이블(옵션):
```sql
CREATE TABLE ext_api_quota (
  date_utc DATE NOT NULL,
  api_name VARCHAR(50) NOT NULL,
  used_count INTEGER NOT NULL DEFAULT 0,
  daily_limit INTEGER NOT NULL,
  PRIMARY KEY (date_utc, api_name)
);
```
운영 가이드:
- `api_name='logo_dev'`, `daily_limit=5000` 설정
- 작업 시작 시 남은 쿼터 계산 후 0이면 logo.dev 스킵
- upsert 방식으로 원자적 쿼터 소모 관리

### 4.1 logo.dev 활용 가이드 (Parameters)
- 참고 문서: [Logo Images Introduction](https://docs.logo.dev/logo-images/introduction)

기본 호출 템플릿
```
https://img.logo.dev/{api_domain}?token=${LOGO_DEV_TOKEN}
```

자주 쓰는 파라미터
- `size`(int, 기본 128): 래스터(`jpg/png`)는 600px 이하 권장
- `format`(jpg 기본): `png` 필요 시 `format=png`
- `theme`(auto 기본): `theme=dark|light` (투명 배경 필요)
- `greyscale`(false 기본): `greyscale=true`로 탈포화
- `retina`(false 기본): `retina=true` 사용 시 2배 해상도로 선명도 개선
- `fallback`(monogram 기본): 모노그램 억제는 `fallback=404` 사용

예시
```
https://img.logo.dev/{api_domain}?token=${LOGO_DEV_TOKEN}&format=png&size=256&retina=true
```

운영 정책
- 기본 포맷: png
- 기본 크기: 256 (요청별 오버라이드 가능, 600 초과 비권장)
- 모노그램 억제: 없는 경우 404 받도록 `fallback=404` 기본 적용
- 다크/라이트 테마: 배경에 따라 선택 적용 (`theme`)

***

## 5) 운영 메모
- 트리거는 사용하지 않음 (요청사항)
- 마스터는 변동 주기/생성 비용을 고려해 Materialized View 권장
- 환경별 접속정보, 버킷명, 경로 prefix 등은 .env/환경변수에서 관리

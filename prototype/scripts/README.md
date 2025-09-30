# 스크립트 디렉토리

이 디렉토리는 로고 관리 시스템의 유틸리티 스크립트들을 포함합니다.

## 📁 파일 목록

### `check_db.py`
기존 API를 통해 특정 종목의 로고 데이터를 확인하는 스크립트입니다.

**사용법:**
```bash
python scripts/check_db.py <INFOMAX_CODE> [provider]
```

**예시:**
```bash
# logo_dev 프로바이더로 확인
python scripts/check_db.py AMX:AIM

# tradingview 프로바이더로 확인
python scripts/check_db.py AMX:AIM tradingview
```

**기능:**
- `logo_hash` 계산 (MD5)
- `logos` 테이블에서 데이터 조회
- `logo_files` 테이블에서 파일 정보 조회

### `query_db.py`
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

**기능:**
- 모든 스키마/테이블 쿼리 가능
- 페이지네이션 지원
- 검색 컬럼 지정 가능
- 쿼리 파라미터 자유 설정

## 🔧 환경 요구사항

- Python 3.7+
- `requests` 라이브러리
- 기존 API 서버 접근 가능 (`http://10.150.2.150:8004`)

## 📝 사용 예시

### 1. 특정 종목의 로고 데이터 확인
```bash
cd prototype
python scripts/check_db.py NAS:AAPL
```

### 2. 오늘의 API 쿼터 사용량 확인
```bash
python scripts/query_db.py raw_data ext_api_quota "page=1&search_column=date_utc&search=$(date +%Y-%m-%d)"
```

### 3. 미보유 로고 목록 확인
```bash
python scripts/query_db.py raw_data logo_master_with_status "page=1&search_column=has_any_file&search=false&limit=10"
```

## ⚠️ 주의사항

- 기존 API 서버가 실행 중이어야 합니다
- 네트워크 연결이 필요합니다
- 쿼리 파라미터는 URL 인코딩이 필요할 수 있습니다

# 진행상황 파일 스키마 및 관리 정책

## JSON 스키마

### 기본 구조
```json
{
  "job_id": "string",
  "status": "string",
  "total": "integer",
  "completed": "integer", 
  "success": "integer",
  "failed": "integer",
  "current": "string",
  "started_at": "string",
  "errors": ["string"],
  "finished_at": "string"
}
```

### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `job_id` | string | ✅ | 작업 고유 식별자 (예: `crawl_20250917_221635`) |
| `status` | string | ✅ | 작업 상태: `running`, `completed`, `failed`, `cancelled` |
| `total` | integer | ✅ | 전체 처리할 아이템 수 (≥0) |
| `completed` | integer | ✅ | 완료된 아이템 수 (0 ≤ completed ≤ total) |
| `success` | integer | ✅ | 성공한 아이템 수 (≥0) |
| `failed` | integer | ✅ | 실패한 아이템 수 (≥0) |
| `current` | string | ❌ | 현재 처리 중인 아이템 (예: `AMX:AIM (AMX-AIM)`) |
| `started_at` | string | ✅ | 작업 시작 시간 (ISO 8601 형식) |
| `errors` | array | ❌ | 에러 메시지 목록 |
| `finished_at` | string | ❌ | 작업 완료 시간 (ISO 8601 형식) |

### 상태별 규칙

#### `running` 상태
- `finished_at` 필드 없음
- `current` 필드에 현재 처리 중인 아이템 표시
- `completed` < `total`

#### `completed` 상태
- `finished_at` 필드 필수
- `completed` = `total`
- `current` 필드는 마지막 처리 아이템

#### `failed` 상태
- `finished_at` 필드 필수
- `errors` 배열에 실패 원인 포함
- `completed` ≤ `total`

#### `cancelled` 상태
- `finished_at` 필드 필수
- `completed` < `total` (일반적으로)

## 파일 명명 규칙

### 크롤링 작업
- 형식: `crawl_YYYYMMDD_HHMMSS.json`
- 예시: `crawl_20250917_221635.json`

### 누락 로고 검색 작업
- 형식: `missing_YYYYMMDD_HHMMSS.json`
- 예시: `missing_20250917_221635.json`

## 보존 정책

### 자동 청소
- **기본 보존 기간**: 30일
- **청소 대상**: 완료/실패/취소된 작업 파일
- **보존 대상**: 실행 중인 작업 파일

### 수동 청소 명령
```bash
# 30일 이전 파일 삭제
python scripts/progress_manager.py --cleanup 30

# 7일 이전 파일 삭제 (더 적극적)
python scripts/progress_manager.py --cleanup 7

# 1년 이전 파일 삭제 (보수적)
python scripts/progress_manager.py --cleanup 365
```

## 모니터링 및 유지보수

### 스키마 검증
```bash
# 모든 파일 검증
python scripts/progress_manager.py --validate

# 특정 디렉토리 검증
python scripts/progress_manager.py --dir /path/to/progress --validate
```

### 통계 확인
```bash
# 진행상황 통계 출력
python scripts/progress_manager.py --stats

# 검증 + 통계 (기본)
python scripts/progress_manager.py
```

### 통계 항목
- 총 작업 수 (완료/실행중/실패)
- 총 아이템 수 (완료/성공/실패)
- 가장 오래된/최근 작업

## 에러 처리

### 일반적인 에러
1. **JSON 파싱 오류**: 파일 손상 → 수동 삭제 권장
2. **스키마 위반**: 필수 필드 누락 → 수동 수정 또는 재생성
3. **데이터 불일치**: `completed > total` → 수동 수정 필요

### 복구 방법
```bash
# 손상된 파일 확인
python scripts/progress_manager.py --validate

# 문제 파일 수동 삭제 후 재실행
rm progress/corrupted_file.json
```

## 성능 고려사항

### 파일 크기 제한
- **권장 최대 크기**: 10MB
- **대용량 작업**: 청크 단위로 분할 처리 권장

### 동시 접근
- **읽기 전용**: 여러 프로세스에서 동시 읽기 가능
- **쓰기 작업**: 단일 프로세스에서만 수정

## 보안 고려사항

### 민감 정보
- 진행상황 파일에는 민감한 정보 포함 금지
- API 키, 토큰, 비밀번호 등 제외
- 에러 메시지에서 민감 정보 필터링

### 파일 권한
- **권장 권한**: 644 (소유자 읽기/쓰기, 그룹/기타 읽기)
- **디렉토리 권한**: 755

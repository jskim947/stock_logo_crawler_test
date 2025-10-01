# 로고 관리 시스템 API 스펙

## 개요

로고 관리 시스템은 주식 로고를 수집, 저장, 조회하는 RESTful API를 제공합니다. 외부 서비스에서 이 API를 통해 로고 데이터에 접근할 수 있습니다.

## 기본 정보

- **Base URL**: `http://localhost:8005`
- **API 버전**: v1
- **인증**: 없음 (공개 API)
- **응답 형식**: JSON
- **이미지 형식**: PNG, WebP, SVG

## 주요 엔드포인트

### 1. 시스템 상태 확인

#### 헬스 체크
```http
GET /api/v1/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "minio": "connected",
  "existing_api": "connected",
  "timestamp": "2025-10-01T04:51:00.237045"
}
```

#### 통계 정보
```http
GET /api/v1/stats
```

**응답 예시:**
```json
{
  "total_logos": 8,
  "today_logos": 8,
  "source_stats": {
    "tradingview": 56
  },
  "timestamp": "2025-10-01T04:51:02.606928"
}
```

### 2. 로고 조회

#### 특정 로고 조회
```http
GET /api/v1/logos/{infomax_code}?format={format}&size={size}
```

**파라미터:**
- `infomax_code` (필수): 종목 코드 (예: NAS:QBUF)
- `format` (선택): 이미지 형식 (png, webp, svg) - 기본값: png
- `size` (선택): 이미지 크기 (240, 300) - 기본값: 256

**예시:**
```http
GET /api/v1/logos/NAS:QBUF?format=png&size=240
GET /api/v1/logos/NAS:QBUF?format=webp&size=300
```

**응답:**
- 성공: 이미지 바이너리 데이터 (Content-Type: image/png, image/webp 등)
- 실패: JSON 에러 메시지

**에러 응답:**
```json
{
  "detail": "Logo not found in database"
}
```

#### 로고 검색
```http
GET /api/v1/logos/search?fs_regional_id={id}&fs_entity_id={id}&has_logo={boolean}&limit={number}
```

**파라미터:**
- `fs_regional_id` (선택): 지역 ID
- `fs_entity_id` (선택): 엔티티 ID
- `has_logo` (선택): 로고 보유 여부 (true/false)
- `limit` (선택): 결과 수 제한 - 기본값: 100

**예시:**
```http
GET /api/v1/logos/search?has_logo=true&limit=10
```

**응답 예시:**
```json
{
  "count": 3,
  "has_logo": true,
  "results": [
    {
      "infomax_code": "AMX:AAA",
      "terminal_code": "AMS:AAA",
      "english_name": "INVESTMENT MANAGERS SERIES TR II",
      "fs_regional_id": "P01C89-R",
      "fs_entity_id": null,
      "has_logo": true,
      "logo_hash": "8485b1610697af8af71a8d8163c225e7"
    }
  ]
}
```

### 3. 크롤링 관리

#### 미보유 로고 크롤링
```http
GET /api/v1/crawl/missing?prefix={prefix}&fs_exchange={exchange}&country={country}&is_active={boolean}&limit={number}
```

**파라미터:**
- `prefix` (선택): 종목 코드 접두사 (예: NAS:Q)
- `fs_exchange` (선택): 거래소 필터
- `country` (선택): 국가 필터
- `is_active` (선택): 활성 상태 필터
- `limit` (선택): 크롤링할 최대 개수 - 기본값: 10

**예시:**
```http
GET /api/v1/crawl/missing?prefix=NAS:Q&limit=5
```

**응답 예시:**
```json
{
  "status": "started",
  "job_id": "missing_20251001_045113",
  "message": "Missing logos crawling started for 1 items",
  "filters_applied": {
    "fs_exchange": null,
    "country": null,
    "is_active": null,
    "prefix": "NAS:Q"
  },
  "quota_skipped": 0
}
```

#### 크롤링 진행상황 확인
```http
GET /api/v1/progress/{job_id}
```

**예시:**
```http
GET /api/v1/progress/missing_20251001_045113
```

**응답 예시:**
```json
{
  "job_id": "missing_20251001_045113",
  "status": "completed",
  "created_at": "2025-10-01T04:51:13.315221",
  "total_items": 1,
  "processed_items": 1,
  "successful_items": 1,
  "failed_items": 0,
  "items": [
    {
      "infomax_code": "NAS:QCLR",
      "ticker": "NASDAQ-QCLR",
      "status": "success",
      "processed_at": "2025-10-01T04:51:45.123456"
    }
  ],
  "current_item": "NAS:QCLR",
  "completed_at": "2025-10-01T04:51:45.789012"
}
```

### 4. 로고 관리

#### 로고 업로드
```http
POST /api/v1/logos/upload
Content-Type: multipart/form-data
```

**파라미터:**
- `file` (필수): 이미지 파일
- `infomax_code` (필수): 종목 코드
- `data_source` (선택): 데이터 소스 (manual, tradingview, logo_dev)
- `upload_type` (선택): 업로드 타입 (manual, crawled)

**예시:**
```bash
curl -X POST "http://localhost:8005/api/v1/logos/upload" \
  -F "file=@logo.png" \
  -F "infomax_code=NAS:TEST" \
  -F "data_source=manual"
```

#### 로고 삭제
```http
DELETE /api/v1/logos/{infomax_code}
```

**예시:**
```http
DELETE /api/v1/logos/NAS:TEST
```

## 사용 예시

### JavaScript/TypeScript

```javascript
// 로고 조회
async function getLogo(infomaxCode, format = 'png', size = 240) {
  try {
    const response = await fetch(
      `http://localhost:8005/api/v1/logos/${infomaxCode}?format=${format}&size=${size}`
    );
    
    if (response.ok) {
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      return imageUrl;
    } else {
      const error = await response.json();
      console.error('로고 조회 실패:', error.detail);
      return null;
    }
  } catch (error) {
    console.error('네트워크 오류:', error);
    return null;
  }
}

// 사용 예시
const logoUrl = await getLogo('NAS:QBUF', 'png', 240);
if (logoUrl) {
  const img = document.createElement('img');
  img.src = logoUrl;
  document.body.appendChild(img);
}
```

### Python

```python
import requests
from PIL import Image
from io import BytesIO

def get_logo(infomax_code, format='png', size=240):
    """로고 조회"""
    url = f"http://localhost:8005/api/v1/logos/{infomax_code}"
    params = {'format': format, 'size': size}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            # 이미지 데이터를 PIL Image로 변환
            image = Image.open(BytesIO(response.content))
            return image
        else:
            print(f"로고 조회 실패: {response.json()}")
            return None
    except Exception as e:
        print(f"네트워크 오류: {e}")
        return None

# 사용 예시
logo = get_logo('NAS:QBUF', 'png', 240)
if logo:
    logo.show()
```

### cURL

```bash
# 로고 조회
curl -o logo.png "http://localhost:8005/api/v1/logos/NAS:QBUF?format=png&size=240"

# 로고 검색
curl "http://localhost:8005/api/v1/logos/search?has_logo=true&limit=5"

# 크롤링 시작
curl "http://localhost:8005/api/v1/crawl/missing?prefix=NAS:Q&limit=3"

# 진행상황 확인
curl "http://localhost:8005/api/v1/progress/missing_20251001_045113"
```

## 에러 코드

| HTTP 상태 코드 | 설명 | 해결 방법 |
|---------------|------|-----------|
| 200 | 성공 | - |
| 404 | 로고를 찾을 수 없음 | 올바른 infomax_code 확인 |
| 422 | 잘못된 파라미터 | 파라미터 형식 확인 |
| 500 | 서버 내부 오류 | 서버 로그 확인 |

## 제한사항

### 이미지 크기
- 지원되는 크기: 240px, 300px
- 요청된 크기가 지원되지 않으면 가장 가까운 크기로 자동 매핑

### 이미지 형식
- 지원되는 형식: PNG, WebP, SVG
- SVG는 실시간으로 PNG/WebP로 변환 가능

### 쿼터 제한
- logo.dev API: 일일 5,000건 제한
- 현재 사용량은 `/api/v1/quota/status`에서 확인 가능

## 모니터링

### 시스템 상태 확인
```http
GET /api/v1/health
```

### 통계 정보
```http
GET /api/v1/stats
```

### 쿼터 상태
```http
GET /api/v1/quota/status
```

## 연락처 및 지원

- **API 문서**: `http://localhost:8005/docs` (Swagger UI)
- **ReDoc 문서**: `http://localhost:8005/redoc`
- **프로젝트 문서**: `DOCUMENTATION.md`

## 버전 정보

- **API 버전**: v1
- **최종 업데이트**: 2025-10-01
- **호환성**: RESTful API 표준 준수

# 로고 관리 시스템 테스트 가이드

## 🚀 테스트 실행 방법

### 전체 테스트 실행
```bash
# 컨테이너 내부에서 실행
docker-compose exec logo-api-prototype python test_api.py

# 로컬에서 실행 (Pillow 설치 필요)
python test_api.py
```

### 개별 테스트 실행
```bash
# 특정 테스트만 실행
docker-compose exec logo-api-prototype python test_api.py [테스트명]

# 예시
docker-compose exec logo-api-prototype python test_api.py health
docker-compose exec logo-api-prototype python test_api.py upload
```

## 📋 테스트 목록

### 🔧 시스템 상태 테스트
- **health**: 헬스 체크 (서버 상태, MinIO, 기존 API 연결)
- **quota**: 쿼터 상태 (API 사용량 및 잔여량)
- **stats**: 시스템 통계 조회
- **connection**: 기존 API 연결 상태

### 📁 로고 관리 테스트
- **upload**: 로고 업로드 (logo_hash 기반 파일명, 이미지 처리, DB 저장)
- **retrieval**: 로고 조회 (파일 다운로드)
- **update**: 로고 수정 (기존 로고 교체)
- **delete**: 로고 삭제 (논리적 삭제)

### 🔍 검색 및 서비스 연동 테스트
- **search**: 로고 검색 (다양한 조건)
- **service**: 서비스 연동용 로고 조회

### 🕷️ 크롤링 기능 테스트
- **crawl**: 미보유 로고 자동 크롤링 (조건 필터링 지원)
- **batch**: 배치 크롤링 (특정 종목 리스트)

### 🔗 기존 API 연동 테스트
- **schemas**: 기존 API 스키마 목록 조회
- **tables**: 기존 API 테이블 목록 조회

### ⚠️ 에러 처리 테스트
- **errors**: 에러 케이스 (존재하지 않는 리소스, 잘못된 파라미터)

## 📊 테스트 결과 해석

### 성공률 기준
- **90% 이상**: 우수 (운영 환경 준비 완료)
- **80-89%**: 양호 (일부 기능 개선 필요)
- **70-79%**: 보통 (주요 기능 점검 필요)
- **70% 미만**: 불량 (전면 점검 필요)

### 카테고리별 분석
- **시스템 상태**: 서버 및 외부 연동 상태
- **로고 관리**: 핵심 CRUD 기능
- **검색 및 연동**: 조회 및 검색 기능
- **크롤링**: 자동 수집 기능
- **기존 API**: 외부 시스템 연동
- **에러 처리**: 예외 상황 처리

## 🔧 테스트 환경 설정

### 필수 조건
1. **Docker 컨테이너 실행**: `docker-compose up -d`
2. **기존 API 서버**: `http://10.150.2.150:8004` 접근 가능
3. **MinIO 서버**: `http://localhost:9000` 접근 가능

### 테스트 데이터
- **테스트 종목**: `AMX:AIM` (실제 존재하는 종목)
- **테스트 이미지**: 10x10 픽셀 PNG (자동 생성)
- **임시 파일**: 테스트 후 자동 정리

## 🐛 문제 해결

### 일반적인 오류
1. **연결 실패**: 컨테이너 상태 확인
2. **타임아웃**: 네트워크 연결 확인
3. **권한 오류**: 파일 접근 권한 확인

### 디버깅 방법
```bash
# 컨테이너 로그 확인
docker-compose logs logo-api-prototype

# 컨테이너 상태 확인
docker-compose ps

# 컨테이너 재시작
docker-compose restart logo-api-prototype
```

## 📈 성능 테스트

### 응답 시간 기준
- **헬스 체크**: < 1초
- **로고 조회**: < 2초
- **로고 업로드**: < 5초
- **크롤링**: < 30초

### 메모리 사용량
- **정상 범위**: < 500MB
- **경고**: 500MB - 1GB
- **위험**: > 1GB

## 🔄 지속적 테스트

### 자동화 스크립트
```bash
#!/bin/bash
# daily_test.sh
echo "일일 테스트 시작..."
docker-compose exec logo-api-prototype python test_api.py
echo "테스트 완료"
```

### 모니터링
- **성공률 추적**: 일일/주간 성공률 기록
- **실패 패턴 분석**: 반복 실패 항목 식별
- **성능 추적**: 응답 시간 변화 모니터링

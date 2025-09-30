# 프로젝트 TODO (상위)

- [x] 설계 확정: `stock_crwaling.md`와 `db_schema_and_ops.md` 검토/동기화
- [x] 인프라 준비: PostgreSQL, MinIO, Redis(or alt) 환경 변수/네트워크 구성
- [x] DB 초기화: `logo_master` 뷰/테이블, `logos`, `logo_files`, `logo_deletion_logs` 생성
- [x] 크롤러 1차 구현: TradingView 수집 (config.yaml 기반), MinIO 업로드, DB 트랜잭션 저장
- [x] logo.dev 연계: 레이트 리밋 카운팅/스킵 로직 구현, 파라미터 정책 적용
- [x] API 서버 구현: FastAPI 엔드포인트 (`GET /api/v1/logos/{infomax_code}` 등)
- [x] 변환 파이프라인: SVG→PNG/WebP 변환, 품질/리사이징 정책 반영, 저장
- [x] 기존 API 연동: 외부 FastAPI 서버와의 연동 및 데이터 입력/조회
- [x] 데이터 입력 테스트: logos, logo_files 테이블 데이터 입력 검증
- [x] 로고 관리 API: 신규 업로드, 수정, 삭제 기능 구현
- [x] 일일 쿼터 관리: ext_api_quota 기반 UTC 일일 5,000건 제한 시스템
- [x] 마스터 조건 필터 크롤링: fs_exchange, country, is_active, prefix 등 필터 지원
- [x] 미보유 로고만 크롤링: has_any_file=false 조건으로 중복 방지
- [x] 코드 정리: 중복 엔드포인트 제거 및 문서 일관성 확보
- [x] MinIO 파일명 구조 개선: logo_hash 기반 파일명으로 변경 (콜론 제거)
- [x] 데이터베이스 제약조건 추가: logo_files 테이블 minio_object_key unique constraint
- [x] 테스트 스위트 개선: 통합 테스트 및 개별 테스트 실행 기능
- [x] 들여쓰기 오류 수정: api_server.py 문법 오류 해결
- [x] 컨테이너 안정화: Docker 빌드 및 실행 안정성 확보
- [ ] 모니터링/로깅: 처리율, 오류율, 저장공간, 레이트리밋 상태
- [ ] 운영 문서화: 실행절차, 복구, 백업, 점검항목



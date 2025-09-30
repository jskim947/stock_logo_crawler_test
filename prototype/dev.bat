@echo off
REM 개발용 스크립트 - 빠른 테스트 및 개발 (Windows)

echo 🚀 로고 관리 시스템 개발 모드

REM 컨테이너 상태 확인
echo 📊 컨테이너 상태 확인...
docker-compose ps

REM 컨테이너가 실행 중이 아니면 시작
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    echo 🔄 컨테이너 시작 중...
    docker-compose up -d
    timeout /t 5 /nobreak >nul
)

REM API 서버 재시작 (코드 변경사항 반영)
echo 🔄 API 서버 재시작 중...
docker-compose restart logo-api-prototype

REM 서버 시작 대기
echo ⏳ 서버 시작 대기 중...
timeout /t 3 /nobreak >nul

REM 헬스 체크
echo 🏥 헬스 체크...
curl -s http://localhost:8005/health >nul 2>&1
if errorlevel 1 (
    echo ❌ 서버 연결 실패
) else (
    echo ✅ 서버 연결 성공
)

echo.
echo ✅ 개발 환경 준비 완료!
echo 📝 사용 가능한 명령어:
echo   - 테스트 실행: docker-compose exec logo-api-prototype python test_api.py
echo   - 개별 테스트: docker-compose exec logo-api-prototype python test_api.py [테스트명]
echo   - 로그 확인: docker-compose logs -f logo-api-prototype
echo   - 컨테이너 재시작: docker-compose restart logo-api-prototype

#!/bin/bash

# 로고 관리 시스템 프로토타입 실행 스크립트

echo "🚀 Logo Management System - Prototype Starting..."

# 환경변수 파일 확인
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env_example.txt .env
fi

# Docker Compose로 실행
echo "🐳 Starting with Docker Compose..."
docker-compose up -d

# 서버 상태 확인
echo "⏳ Waiting for server to start..."
sleep 10

# 헬스 체크
echo "🔍 Checking server health..."
curl -s http://localhost:8005/api/v1/health

echo "✅ Server is running!"
echo "📚 API Docs: http://localhost:8005/docs"
echo "📖 ReDoc: http://localhost:8005/redoc"
echo "🗄️ MinIO Console: http://localhost:9001"
echo "👤 MinIO Login: minioadmin / minioadmin123"
echo "🔗 Existing API: http://10.150.2.150:8004/docs"

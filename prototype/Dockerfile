FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치 (캐시 최적화)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐시 레이어 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (캐시 최적화)
RUN playwright install --with-deps chromium && \
    playwright install chromium

# 애플리케이션 코드 복사
# 주의: 존재하지 않는 디렉토리는 복사하지 않음
COPY *.py ./
COPY *.md ./
COPY *.txt ./

# 진행상황 디렉토리 생성
RUN mkdir -p progress logs

# 포트 노출
EXPOSE 8005

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8005/api/v1/health || exit 1

# 애플리케이션 실행
CMD ["python", "api_server.py"]

"""
로고 관리 시스템 프로토타입 - FastAPI 서버
기존 FastAPI 서버를 활용하여 로고 조회/관리 기능 제공
"""

from fastapi import FastAPI, HTTPException, Query, Depends, File, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
import os
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
import json
from datetime import datetime, date
import hashlib
import requests
# import aiohttp  # requests로 대체
from pydantic import BaseModel
# 크롤러는 선택적으로 사용 (playwright 미설치 환경 가드)
try:
    from crawler import LogoCrawler
except Exception as _crawler_import_error:
    LogoCrawler = None  # 크롤링 엔드포인트에서 필요 시 런타임 체크
    print(f"⚠️  crawler 임포트 실패: {_crawler_import_error}")
from PIL import Image, ImageDraw, ImageFont
import io
# from loguru import logger  # 임시로 비활성화
import logging
logger = logging.getLogger(__name__)
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded

# 기존 API 클라이언트
class ExistingAPIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    async def query_table_async(self, schema: str, table: str, params: dict = None):
        """테이블 쿼리 실행 (동기 방식으로 대체)"""
        try:
            # aiohttp 대신 requests 사용
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/query"
            response = requests.get(url, params=params or {}, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 기존 API 쿼리 오류: {e}")
            return None
    
    async def upsert_data_async(self, schema: str, table: str, data: dict):
        """데이터 삽입/업데이트 (동기 방식으로 대체)"""
        try:
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/upsert"
            response = requests.post(url, json=data, timeout=10)
            print(f"📥 응답 상태: {response.status_code}")
            print(f"📥 응답 내용: {response.text}")
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {"text": response.text}
        except Exception as e:
            print(f"❌ 기존 API 데이터 입력 오류: {e}")
            return None

    # 임시 호환용 동기 메서드 유지 (점진 전환)
    def query_table(self, schema: str, table: str, params: dict = None):
        try:
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/query"
            response = requests.get(url, params=params or {}, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 기존 API 쿼리 오류: {e}")
            return None

    def upsert_data(self, schema: str, table: str, data: dict):
        try:
            url = f"{self.base_url}/api/schemas/{schema}/tables/{table}/upsert"
            response = requests.post(url, json=data, timeout=10)
            print(f"📥 업서트 요청: {url}")
            print(f"📥 업서트 페이로드: {data}")
            print(f"📥 업서트 응답코드: {response.status_code}")
            print(f"📥 업서트 응답본문: {response.text}")
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {"text": response.text}
        except Exception as e:
            print(f"❌ 기존 API 데이터 입력 오류: {e}")
            return None

# 레이트리밋 설정 (임시 비활성화)
# limiter = Limiter(key_func=get_remote_address)

# FastAPI 앱 초기화
app = FastAPI(
    title="Logo Management System - Prototype",
    description="주식 로고 수집 및 관리 시스템 프로토타입",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 레이트리밋 미들웨어 추가 (임시 비활성화)
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 이미지 처리 유틸리티 함수
def process_uploaded_image(image_data: bytes, target_size: int = 256, target_format: str = "PNG") -> bytes:
    """업로드된 이미지를 처리하여 지정된 크기와 형식으로 변환"""
    try:
        print(f"🔍 이미지 처리 시작: {len(image_data)} bytes")
        
        # 이미지 열기
        image = Image.open(io.BytesIO(image_data))
        print(f"📐 원본 이미지 크기: {image.size}, 모드: {image.mode}")
        
        # RGB로 변환 (투명도 제거)
        if image.mode in ('RGBA', 'LA', 'P'):
            # 투명도가 있는 경우 흰색 배경 추가
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        print(f"🔄 변환 후 이미지 모드: {image.mode}")
        
        # 정사각형으로 크롭 (중앙 기준)
        width, height = image.size
        if width != height:
            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            right = left + size
            bottom = top + size
            image = image.crop((left, top, right, bottom))
            print(f"✂️ 크롭 후 크기: {image.size}")
        
        # 크기 조정
        if image.size[0] != target_size:
            image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)
            print(f"📏 리사이즈 후 크기: {image.size}")
        
        # 형식에 따라 변환
        output = io.BytesIO()
        if target_format.upper() == "PNG":
            image.save(output, format="PNG", optimize=True)
        elif target_format.upper() == "WEBP":
            image.save(output, format="WEBP", quality=90, optimize=True)
        elif target_format.upper() == "JPEG":
            image.save(output, format="JPEG", quality=90, optimize=True)
        else:
            # 기본값은 PNG
            image.save(output, format="PNG", optimize=True)
        
        result = output.getvalue()
        print(f"✅ 이미지 처리 완료: {len(result)} bytes")
        return result
        
    except Exception as e:
        print(f"❌ 이미지 처리 오류: {e}")
        print(f"❌ 오류 타입: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"이미지 처리 실패: {str(e)}")

def validate_image_file(file: UploadFile) -> bool:
    """업로드된 파일이 유효한 이미지인지 검증"""
    if not file.content_type or not file.content_type.startswith('image/'):
        return False
    
    # 지원하는 이미지 형식
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/svg+xml']
    return file.content_type in allowed_types

def get_logo_hash_from_master(infomax_code: str) -> str:
    """logo_master에서 logo_hash 조회"""
    try:
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "search_column": "infomax_code",
            "search": infomax_code,
            "limit": 1
        })
        
        if isinstance(master_response, dict) and 'data' in master_response and master_response['data']:
            master_data = master_response['data'][0]
            if isinstance(master_data, dict) and 'logo_hash' in master_data:
                return master_data['logo_hash']
        
        # fallback: infomax_code로 MD5 생성
        return hashlib.md5(infomax_code.encode('utf-8')).hexdigest()
        
    except Exception as e:
        print(f"❌ logo_hash 조회 오류: {e}")
        # fallback: infomax_code로 MD5 생성
        return hashlib.md5(infomax_code.encode('utf-8')).hexdigest()

# 환경변수 설정
def _get_env(key: str, fallback: str | None = None) -> str:
    value = os.getenv(key)
    if value is None or value == "":
        # 실행 중단을 피하기 위해 임시로 fallback 사용, 경고 출력
        if fallback is not None:
            print(f"⚠️  ENV {key} 미설정: 임시값 사용 → {fallback}. .env에 {key}를 설정하세요.")
            return fallback
        raise RuntimeError(f"환경변수 {key}가 필요합니다. .env에 설정하세요.")
    return value

# NOTE: 실행 안정성을 위해 임시 fallback 유지. 운영환경에서는 .env에 반드시 설정.
MINIO_ENDPOINT = _get_env('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = _get_env('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = _get_env('MINIO_SECRET_KEY', 'minioadmin123')
MINIO_BUCKET = _get_env('MINIO_BUCKET', 'logos')
EXISTING_API_BASE = _get_env('EXISTING_API_BASE', 'http://10.150.2.150:8004')
LOGO_DEV_DAILY_LIMIT = int(_get_env('LOGO_DEV_DAILY_LIMIT', '5000'))

# MinIO 연결
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# MinIO 버킷 생성 (없으면 생성)
def ensure_bucket_exists():
    """MinIO 버킷이 존재하는지 확인하고 없으면 생성"""
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
            print(f"✅ Created MinIO bucket: {MINIO_BUCKET}")
        else:
            print(f"✅ MinIO bucket exists: {MINIO_BUCKET}")
    except Exception as e:
        print(f"❌ MinIO bucket creation failed: {e}")

# 앱 시작 시 버킷 확인
ensure_bucket_exists()

# 진행상황 모니터링 디렉토리
PROGRESS_DIR = Path(os.getenv('PROGRESS_DIR', 'progress'))
PROGRESS_DIR.mkdir(exist_ok=True)

# 기존 API 클라이언트 초기화
existing_api = ExistingAPIClient(EXISTING_API_BASE)

# 쿼터 매니저 클래스
class QuotaManager:
    """API 쿼터 관리 클래스"""
    
    def __init__(self, api_name: str, daily_limit: int):
        self.api_name = api_name
        self.daily_limit = daily_limit
    
    def check_and_consume_quota(self, count: int = 1) -> bool:
        """쿼터 확인 및 소모 (원자적 연산)"""
        try:
            today = date.today()
            
            # 현재 사용량 조회
            current_usage = self._get_current_usage(today)
            
            if current_usage + count > self.daily_limit:
                print(f"❌ {self.api_name} 일일 쿼터 초과: {current_usage}/{self.daily_limit} (요청: {count})")
                return False
            
            # 쿼터 소모 (upsert 방식)
            success = self._consume_quota(today, count)
            if success:
                print(f"✅ {self.api_name} 쿼터 소모: {count}건 (총 {current_usage + count}/{self.daily_limit})")
            return success
            
        except Exception as e:
            print(f"❌ 쿼터 확인 오류: {e}")
            return False
    
    def _get_current_usage(self, target_date: date) -> int:
        """현재 사용량 조회"""
        try:
            response = existing_api.query_table("raw_data", "ext_api_quota", {
                "date_utc": target_date.isoformat(),
                "api_name": self.api_name,
                "limit": 1
            })
            
            if response and 'data' in response and response['data']:
                return response['data'][0].get('used_count', 0)
            return 0
        except Exception as e:
            print(f"❌ 사용량 조회 오류: {e}")
            return 0
    
    def _consume_quota(self, target_date: date, count: int) -> bool:
        """쿼터 소모 (upsert)"""
        try:
            # upsert 데이터 준비
            quota_data = {
                "data": {
                    "date_utc": target_date.isoformat(),
                    "api_name": self.api_name,
                    "used_count": count  # 증가량
                },
                "conflict_columns": ["date_utc", "api_name"]
            }
            
            # upsert 실행 (ON CONFLICT 시 used_count += count)
            result = existing_api.upsert_data("raw_data", "ext_api_quota", quota_data)
            return result is not None
            
        except Exception as e:
            print(f"❌ 쿼터 소모 오류: {e}")
            return False

# 쿼터 매니저 인스턴스
logo_dev_quota = QuotaManager("logo_dev", LOGO_DEV_DAILY_LIMIT)

# 로고 데이터 저장 함수
def save_logo_data(infomax_code: str, logo_hash: str, file_info: dict) -> bool:
    """로고 데이터를 DB에 저장 (logos -> logo_files 순서)"""
    try:
        # 1. logos 테이블에 데이터 입력 또는 기존 데이터 조회
        # 먼저 기존 데이터가 있는지 확인
        existing_logo = existing_api.query_table("raw_data", "logos", {
            "search_column": "logo_hash",
            "search": logo_hash,
            "limit": 1
        })
        
        if existing_logo and 'data' in existing_logo and existing_logo['data']:
            # 기존 데이터가 있으면 해당 logo_id 사용
            logo_id = existing_logo['data'][0]['logo_id']
            print(f"✅ 기존 logos 데이터 사용: logo_id={logo_id}, logo_hash={logo_hash}")
        else:
            # 기존 데이터가 없으면 새로 생성
            logo_data = {
                "data": {
                    "logo_hash": logo_hash,
                    "is_deleted": False
                },
                "conflict_columns": ["logo_hash"]
            }
            
            logo_result = existing_api.upsert_data("raw_data", "logos", logo_data)
            if not logo_result or 'data' not in logo_result:
                print(f"❌ logos 테이블 저장 실패: {infomax_code}")
                return False
            
            logo_id = logo_result['data']['logo_id']
            print(f"✅ logos 테이블 저장 성공: logo_id={logo_id}, logo_hash={logo_hash}")
        
        # 2. logo_files 테이블에 데이터 입력
        file_data = {
            "data": {
                "logo_id": logo_id,
                "file_format": file_info["format"],
                "dimension_width": file_info["width"],
                "dimension_height": file_info["height"],
                "file_size": file_info["size"],
                "minio_object_key": file_info["minio_key"],
                "data_source": file_info["source"],
                "upload_type": file_info["upload_type"],
                "is_original": file_info.get("is_original", True)
            },
            "conflict_columns": ["minio_object_key"]
        }
        
        file_result = existing_api.upsert_data("raw_data", "logo_files", file_data)
        if not file_result:
            print(f"❌ logo_files 테이블 저장 실패: {infomax_code}")
            return False
        
        print(f"✅ logo_files 테이블 저장 성공: logo_id={logo_id}")
        
        print(f"✅ 로고 데이터 저장 완료: {infomax_code}")
        return True
        
    except Exception as e:
        print(f"❌ 로고 데이터 저장 오류: {e}")
        return False

# 기존 API 클라이언트는 이미 위에서 정의됨
# crawler = LogoCrawler()  # 임시로 비활성화

def generate_logo_hash(infomax_code: str, source: str = "tradingview") -> str:
    """로고 해시 생성"""
    return hashlib.md5(f"{source}_{infomax_code}".encode()).hexdigest()

@app.get("/")
# @limiter.limit("10/minute")  # 임시 비활성화
async def root(request: Request):
    """루트 엔드포인트"""
    logger.info(f"Root endpoint accessed from {request.client.host}")
    return {
        "message": "Logo Management System - Prototype API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
        "existing_api": EXISTING_API_BASE
    }

@app.get("/api/v1/test")
async def test_endpoint():
    """테스트 엔드포인트"""
    print("🔍🔍🔍 TEST 엔드포인트 호출")
    return {"status": "test", "message": "Test endpoint working"}

@app.get("/api/v1/logos/search")
async def search_logos(
    fs_regional_id: Optional[str] = None,
    fs_entity_id: Optional[int] = None,
    has_logo: bool = True,
    limit: int = 100
):
    """로고 존재 여부 검색 - 기존 API를 통해 데이터 조회"""
    
    try:
        # 기존 API를 통해 master 데이터 조회 (logo_master 뷰 사용)
        master_params = {"limit": limit}
        if fs_regional_id:
            master_params["fs_regional_id"] = fs_regional_id
        if fs_entity_id:
            master_params["fs_entity_id"] = fs_entity_id
        
        master_response = existing_api.query_table("raw_data", "logo_master", master_params)
        
        # API 응답 구조 확인
        if isinstance(master_response, dict) and 'data' in master_response:
            master_data = master_response['data']
        else:
            master_data = master_response if master_response else []
        
        if not master_data:
            return {
                "count": 0,
                "has_logo": has_logo,
                "results": []
            }
        
        # 간단한 테스트를 위해 처음 3개만 처리
        results = []
        for i, master_info in enumerate(master_data[:3]):
            print(f"🔍 처리 중: {i} - {type(master_info)} - {master_info}")
            
            # master_info가 딕셔너리인지 확인
            if not isinstance(master_info, dict):
                print(f"⚠️ master_info가 딕셔너리가 아님: {type(master_info)} - {master_info}")
                continue
                
            infomax_code = master_info.get("infomax_code")
            if not infomax_code:
                print(f"⚠️ infomax_code가 없음: {master_info}")
                continue
            
            # logos 테이블에서 해당 infomax_code의 로고 존재 여부 확인
            logo_response = existing_api.query_table("raw_data", "logos", {
                "logo_hash": master_info.get("logo_hash"),
                "is_deleted": False,
                "limit": 1
            })
            
            logo_exists = False
            if isinstance(logo_response, dict) and 'data' in logo_response:
                logo_data = logo_response['data']
                logo_exists = len(logo_data) > 0
            elif logo_response:
                logo_exists = len(logo_response) > 0
            
            # has_logo 필터 적용
            if has_logo and not logo_exists:
                continue
            elif not has_logo and logo_exists:
                continue
            
            results.append({
                "infomax_code": infomax_code,
                "terminal_code": master_info.get("terminal_code"),
                "english_name": master_info.get("english_name"),
                "fs_regional_id": master_info.get("fs_regional_id"),
                "fs_entity_id": master_info.get("fs_entity_id"),
                "has_logo": logo_exists,
                "logo_hash": master_info.get("logo_hash")
            })
        
        return {
            "count": len(results),
            "has_logo": has_logo,
            "results": results
        }
        
    except Exception as e:
        print(f"❌ 로고 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

@app.get("/api/v1/logos/{infomax_code}")
# @limiter.limit("30/minute")  # 임시 비활성화
async def get_logo(request: Request, infomax_code: str, format: str = "png", size: int = 300):
    # 크기 매핑: 300px -> 256px (실제 존재하는 크기)
    if size == 300:
        size = 256
    """로고 조회 - 이미지 스트리밍 (메타 조회 → MinIO 객체 바이너리 반환)"""
    logger.info(f"Logo request: {infomax_code}, format={format}, size={size} from {request.client.host}")
    try:
        print(f"🔍 get_logo 함수 호출됨: infomax_code={infomax_code}, format={format}, size={size}")
        
        # 1. logo_hash 조회 또는 생성 (디버그 플로우와 동일)
        logo_hash = get_logo_hash_from_master(infomax_code)
        print(f"🔍 logo_hash: {logo_hash}")
        
        # 2. logos 테이블에서 로고 정보 조회
        print(f"🔍 logos 테이블 조회 시작: logo_hash={logo_hash}")
        logo_response = existing_api.query_table("raw_data", "logos", {
            "search_column": "logo_hash",
            "search": logo_hash,
            "is_deleted": False,
            "limit": 1
        })
        print(f"🔍 logos 테이블 응답: {logo_response}")
        
        if not logo_response or not logo_response.get('data'):
            print(f"❌ logos 테이블에서 {logo_hash}를 찾을 수 없음")
            raise HTTPException(status_code=404, detail="Logo not found in database")
        
        logo_data = logo_response['data'][0]
        logo_id = logo_data.get('logo_id')
        print(f"🔍 조회된 logo_id: {logo_id}")
        
        # 3. logo_files 테이블에서 해당 logo_id의 파일들 조회
        print(f"🔍 logo_files 테이블 조회 시작: logo_id={logo_id}")
        file_response = existing_api.query_table("raw_data", "logo_files", {
            "page": 1,
            "size": 100
        })
        print(f"🔍 logo_files 테이블 응답: {file_response}")
        
        if not file_response or not file_response.get('data'):
            print(f"❌ logo_files 테이블에서 파일을 찾을 수 없음")
            raise HTTPException(status_code=404, detail="Logo files not found")
        
        all_files = file_response['data']
        print(f"🔍 전체 파일 수: {len(all_files)}개")
        
        # 4. 조건에 맞는 파일 찾기
        found_file = None
        for f in all_files:
            if (f.get('logo_id') == logo_id and 
                f.get('file_format') == format and 
                f.get('dimension_width') == size and
                str(f.get('minio_object_key','')).startswith(logo_hash)):
                found_file = f
                print(f"🔍 조건에 맞는 파일 발견: {f.get('minio_object_key')}")
                break
        
        if not found_file:
            print(f"❌ 조건에 맞는 파일을 찾을 수 없음: logo_id={logo_id}, format={format}, size={size}")
            # 사용 가능한 파일들 출력
            available_files = [f for f in all_files if f.get('logo_id') == logo_id]
            print(f"🔍 사용 가능한 파일들: {[f.get('minio_object_key') for f in available_files]}")
            raise HTTPException(status_code=404, detail="Logo file not found")
        
        file_info = found_file
        object_key = file_info.get('minio_object_key')
        if not object_key:
            raise HTTPException(status_code=404, detail="Object key not found")
        
        print(f"🔍 최종 선택된 파일: {object_key}")
        
        # 5. MinIO에서 파일 조회
        try:
            minio_client.stat_object(MINIO_BUCKET, object_key)
            print(f"✅ MinIO 객체 존재 확인: {object_key}")
        except Exception as e:
            print(f"❌ MinIO 객체 없음: {e}")
            # 사용 가능한 객체들 출력
            try:
                print(f"🔎 prefix 목록: {logo_hash}")
                for o in minio_client.list_objects(MINIO_BUCKET, prefix=logo_hash):
                    print(f"  - {o.object_name}")
            except Exception as e2:
                print(f"❌ list_objects 실패: {e2}")
            raise HTTPException(status_code=404, detail=f"MinIO object not found: {object_key}")
        
        # 6. 파일 스트리밍 반환
        obj = minio_client.get_object(MINIO_BUCKET, object_key)
        content_type = f"image/{format.lower()}"
        data = obj.read()
        obj.close()
        obj.release_conn()
        
        print(f"✅ 로고 반환 완료: {len(data)} bytes")
        return Response(content=data, media_type=content_type)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ get_logo 오류: {e}")
        import traceback
        print(f"📋 상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/crawl/test")
async def crawl_test():
    """크롤링 테스트 엔드포인트"""
    print("🔍🔍🔍 CRAWL TEST 엔드포인트 호출")
    return {"status": "test", "message": "Crawl test endpoint working"}

@app.get("/api/v1/logo-info")
async def get_logo_by_criteria(
    infomax_code: Optional[str] = None,
    fs_regional_id: Optional[str] = None,
    fs_entity_id: Optional[int] = None,
    format: str = "png",
    size: int = 300
):
    """서비스에서 사용할 로고 조회 API - 기존 API를 통해 데이터 조회"""
    
    print(f"🔍 get_logo_by_criteria 함수 호출됨: infomax_code={infomax_code}, fs_regional_id={fs_regional_id}, fs_entity_id={fs_entity_id}")
    # 크기 매핑: 300px -> 256px (실제 저장된 표준 크기에 맞춤)
    if size == 300:
        size = 256
    
    if not any([infomax_code, fs_regional_id, fs_entity_id]):
        raise HTTPException(status_code=400, detail="At least one search criteria required")
    
    try:
        # 기존 API를 통해 master 데이터 조회 (logo_master 뷰 사용)
        master_params = {"limit": 1}
        if infomax_code:
            master_params["infomax_code"] = infomax_code
        if fs_regional_id:
            master_params["fs_regional_id"] = fs_regional_id
        if fs_entity_id:
            master_params["fs_entity_id"] = fs_entity_id
        
        master_response = existing_api.query_table("raw_data", "logo_master", master_params)
        
        # API 응답 구조 확인
        if isinstance(master_response, dict) and 'data' in master_response:
            master_data = master_response['data']
        else:
            master_data = master_response if master_response else []
        
        if not master_data or len(master_data) == 0:
            # 마스터에 없을 경우: infomax_code MD5 기반 fallback 조회
            if infomax_code:
                fallback_hash = hashlib.md5(infomax_code.encode('utf-8')).hexdigest()
                logo_response = existing_api.query_table("raw_data", "logos", {
                    "logo_hash": fallback_hash,
                    "is_deleted": False,
                    "limit": 1
                })
                if isinstance(logo_response, dict) and logo_response.get('data'):
                    logo_data = logo_response['data']
                    file_response = existing_api.query_table("raw_data", "logo_files", {
                        "page": 1,
                        "size": 100
                    })
                    if isinstance(file_response, dict) and file_response.get('data'):
                        all_files = file_response['data']
                        # 클라이언트에서 필터링
                        found_file = None
                        for f in all_files:
                            if (f.get('logo_id') == logo_data[0]["logo_id"] and 
                                f.get('file_format') == format and 
                                f.get('dimension_width') == size and
                                str(f.get('minio_object_key','')).startswith(logo_data[0]["logo_hash"])):
                                found_file = f
                                break
                        
                        if not found_file:
                            raise HTTPException(status_code=404, detail="Logo file not found")
                        
                        file_info = found_file
                        return {
                            "infomax_code": infomax_code,
                            "terminal_code": None,
                            "english_name": None,
                            "fs_regional_id": None,
                            "fs_entity_id": None,
                            "logo_hash": fallback_hash,
                            "logo_exists": True,
                            "file_info": {
                                "file_format": file_info.get('file_format'),
                                "file_size": file_info.get('file_size'),
                                "data_source": file_info.get('data_source'),
                                "upload_type": file_info.get('upload_type'),
                                "minio_object_key": file_info.get('minio_object_key'),
                                "dimension_width": file_info.get('dimension_width'),
                                "dimension_height": file_info.get('dimension_height'),
                                "quality": file_info.get('quality')
                            },
                            "logo_info": {
                                "logo_id": logo_data[0].get('logo_id'),
                                "is_deleted": logo_data[0].get('is_deleted'),
                                "created_at": logo_data[0].get('created_at'),
                                "updated_at": logo_data[0].get('updated_at')
                            }
                        }
            raise HTTPException(status_code=404, detail="Ticker not found in master data")
        
        master_info = master_data[0]
        infomax_code = master_info.get("infomax_code")
        
        # master_data에서 logo_hash 조회
        logo_hash = master_info.get("logo_hash")
        if not logo_hash:
            raise HTTPException(status_code=404, detail="Logo hash not found in master data")
        
        # logos 테이블에서 로고 정보 조회 (검색 파라미터 사용 후 클라이언트 필터)
        logo_response = existing_api.query_table("raw_data", "logos", {
            "page": 1,
            "search_column": "logo_hash",
            "search": logo_hash
        })
        if isinstance(logo_response, dict) and 'data' in logo_response:
            candidates = logo_response['data'] or []
        else:
            candidates = logo_response or []
        logo_data = [r for r in candidates if isinstance(r, dict) and r.get('logo_hash') == logo_hash and r.get('is_deleted') is False]
        if not logo_data:
            raise HTTPException(status_code=404, detail="Logo not found")
        
        # logo_files 테이블에서 파일 정보 조회 (검색 파라미터 사용 후 클라이언트 필터)
        files_response = existing_api.query_table("raw_data", "logo_files", {
            "page": 1,
            "search_column": "logo_id",
            "search": str(logo_data[0]["logo_id"])
        })
        if isinstance(files_response, dict) and 'data' in files_response:
            files = files_response['data'] or []
        else:
            files = files_response or []
        # 동일 해시 prefix만 사용
        files = [f for f in files if isinstance(f, dict) and str(f.get('minio_object_key','')).startswith(logo_hash)]
        # 후보 선택: 정확 매칭 → 포맷만 매칭 → 첫 번째
        file_info = None
        for f in files:
            if f.get('file_format') == format and f.get('dimension_width') == size:
                file_info = f; break
        if not file_info:
            for f in files:
                if f.get('file_format') == format:
                    file_info = f; break
        if not file_info and files:
            file_info = files[0]
        if not file_info:
            raise HTTPException(status_code=404, detail="Logo file not found")
        
        # JSON 메타데이터 반환
        return {
            "infomax_code": infomax_code,
            "terminal_code": master_info.get("terminal_code"),
            "english_name": master_info.get("english_name"),
            "fs_regional_id": master_info.get("fs_regional_id"),
            "fs_entity_id": master_info.get("fs_entity_id"),
            "logo_hash": logo_hash,
            "logo_exists": True,
            "file_info": {
                "file_format": file_info.get('file_format'),
                "file_size": file_info.get('file_size'),
                "data_source": file_info.get('data_source'),
                "upload_type": file_info.get('upload_type'),
                "minio_object_key": file_info.get('minio_object_key'),
                "dimension_width": file_info.get('dimension_width'),
                "dimension_height": file_info.get('dimension_height'),
                "quality": file_info.get('quality')
            },
            "logo_info": {
                "logo_id": logo_data[0].get('logo_id'),
                "is_deleted": logo_data[0].get('is_deleted'),
                "created_at": logo_data[0].get('created_at'),
                "updated_at": logo_data[0].get('updated_at')
            }
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/progress/{job_id}")
async def get_progress(job_id: str):
    """작업 진행상황 조회"""
    progress_file = PROGRESS_DIR / f"{job_id}.json"
    
    if not progress_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        return progress_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/stats")
async def get_stats():
    """시스템 통계 조회 - 기존 API를 통해 데이터 조회"""
    try:
        # 전체 로고 수
        logos_response = existing_api.query_table("raw_data", "logos", {
            "is_deleted": False,
            "limit": 1000  # 통계용으로 충분한 수
        })
        
        # API 응답 구조 확인
        if isinstance(logos_response, dict) and 'data' in logos_response:
            total_logos_data = logos_response['data']
            total_logos = len(total_logos_data)
        else:
            total_logos_data = logos_response if logos_response else []
            total_logos = len(total_logos_data)
        
        # 오늘 수집된 로고 수 (간단한 필터링)
        today_logos = 0
        if total_logos_data and isinstance(total_logos_data, list):
            today = datetime.now().strftime('%Y-%m-%d')
            for logo in total_logos_data:
                if isinstance(logo, dict) and logo.get('created_at', '').startswith(today):
                    today_logos += 1
        
        # 데이터 소스별 통계
        source_stats = {}
        if total_logos_data and isinstance(total_logos_data, list):
            for logo in total_logos_data:
                if isinstance(logo, dict):
                    logo_id = logo.get('logo_id')
                    if logo_id:
                        file_response = existing_api.query_table("raw_data", "logo_files", {
                            "page": 1,
                            "size": 100
                        })
                        
                        # API 응답 구조 확인
                        if isinstance(file_response, dict) and 'data' in file_response:
                            file_data = file_response['data']
                        else:
                            file_data = file_response if file_response else []
                        
                        if file_data and isinstance(file_data, list):
                            for file_info in file_data:
                                if isinstance(file_info, dict):
                                    data_source = file_info.get('data_source', 'unknown')
                                    source_stats[data_source] = source_stats.get(data_source, 0) + 1
        
        return {
            "total_logos": total_logos,
            "today_logos": today_logos,
            "source_stats": source_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/health")
async def health_check():
    """헬스 체크"""
    try:
        # MinIO 연결 확인
        minio_client.bucket_exists(MINIO_BUCKET)
        
        # 기존 API 연결 확인
        existing_api_status = "connected"
        try:
            response = requests.get(f"{EXISTING_API_BASE}/health", timeout=5)
            if response.status_code != 200:
                existing_api_status = "error"
        except:
            existing_api_status = "disconnected"
        
        return {
            "status": "healthy",
            "minio": "connected",
            "existing_api": existing_api_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/debug/test-api")
async def debug_test_api():
    """기존 API 연결 디버깅"""
    try:
        # 기존 API 테스트
        test_response = existing_api.query_table("raw_data", "logo_master", {"limit": 1})
        
        return {
            "test_response_type": str(type(test_response)),
            "test_response": test_response,
            "is_dict": isinstance(test_response, dict),
            "has_data": isinstance(test_response, dict) and 'data' in test_response if isinstance(test_response, dict) else False
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": str(type(e))
        }

@app.post("/api/v1/debug/test-insert")
async def debug_test_insert():
    """데이터 입력 테스트 - logos, logo_files 테이블"""
    try:
        # 테스트용 데이터 준비
        test_infomax_code = "TEST:DEBUG"
        test_logo_hash = generate_logo_hash(test_infomax_code)
        
        # 1. logos 테이블에 데이터 입력 테스트
        logo_data = {
            "data": {
            "logo_hash": test_logo_hash,
            "is_deleted": False
            },
            "conflict_columns": ["logo_hash"]
        }
        # 기존 API를 통해 logos 테이블에 데이터 입력 (upsert)
        logo_insert_response = existing_api.upsert_data("raw_data", "logos", logo_data)
        logo_id = None
        if isinstance(logo_insert_response, dict):
            # 예상 반환: { data: { logo_id: ..., logo_hash: ... } } 혹은 유사 형태
            logo_id = (
                logo_insert_response.get("data", {}).get("logo_id")
                if isinstance(logo_insert_response.get("data"), dict)
                else logo_insert_response.get("logo_id")
            )
        
        # logo_id가 응답에 없으면 조회로 확인
        if not logo_id:
            check = existing_api.query_table("raw_data", "logos", {"logo_hash": test_logo_hash, "limit": 1})
            if isinstance(check, dict) and check.get("data"):
                logo_id = check["data"][0].get("logo_id")
        
        # 2. logo_files 테이블에 데이터 입력 테스트
        file_payload = {
            "data": {
                "logo_id": logo_id or 0,
            "file_format": "png",
                "data_source": "manual",
                "upload_type": "manual",
                "dimension_width": 256,
                "dimension_height": 256,
            "file_size": 1024,
            "minio_object_key": f"test/{test_logo_hash}_256.png",
                "is_original": True
            },
            "conflict_columns": ["minio_object_key"]
        }
        file_insert_response = existing_api.upsert_data("raw_data", "logo_files", file_payload)
        
        return {
            "status": "success",
            "logo_insert": logo_insert_response,
            "file_insert": file_insert_response,
            "test_data": {
                "infomax_code": test_infomax_code,
                "logo_hash": test_logo_hash
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": str(type(e))
        }


@app.get("/api/v1/debug/files")
async def debug_list_files(infomax_code: str):
    """지정 종목의 logo_hash, logos, logo_files 목록 디버그 출력"""
    try:
        # 1) master → logo_hash
        master = existing_api.query_table("raw_data", "logo_master", {"infomax_code": infomax_code, "limit": 1})
        if not isinstance(master, dict) or not master.get("data"):
            return {"status": "not_found_in_master", "infomax_code": infomax_code}
        logo_hash = master["data"][0].get("logo_hash")
        # 2) logos by logo_hash
        logos_resp = existing_api.query_table("raw_data", "logos", {"page": 1, "search_column": "logo_hash", "search": logo_hash})
        logos = logos_resp.get("data", []) if isinstance(logos_resp, dict) else (logos_resp or [])
        if not logos:
            return {"status": "no_logos", "logo_hash": logo_hash}
        logo_id = logos[0].get("logo_id")
        # 3) files by logo_id
        files_resp = existing_api.query_table("raw_data", "logo_files", {"page": 1, "size": 1000})
        files = files_resp.get("data", []) if isinstance(files_resp, dict) else (files_resp or [])
        return {
            "status": "ok",
            "infomax_code": infomax_code,
            "logo_hash": logo_hash,
            "logo_id": logo_id,
            "files_count": len([f for f in files if isinstance(f, dict) and f.get('logo_id') == logo_id]),
            "files": [f for f in files if isinstance(f, dict) and f.get('logo_id') == logo_id],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/v1/debug/minio")
async def debug_minio_check(object_key: str):
    """MinIO 객체 존재 여부 및 메타데이터 확인"""
    try:
        # MinIO 객체 존재 확인
        stat = minio_client.stat_object(MINIO_BUCKET, object_key)
        return {
            "status": "exists",
            "object_key": object_key,
            "bucket": MINIO_BUCKET,
            "size": stat.size,
            "etag": stat.etag,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "content_type": stat.content_type
        }
    except Exception as e:
        # 객체 목록으로 확인
        try:
            objects = list(minio_client.list_objects(MINIO_BUCKET, prefix=object_key.split('_')[0]))
            return {
                "status": "not_found",
                "object_key": object_key,
                "bucket": MINIO_BUCKET,
                "error": str(e),
                "available_objects": [obj.object_name for obj in objects[:10]]
            }
        except Exception as e2:
            return {
                "status": "error",
                "object_key": object_key,
                "bucket": MINIO_BUCKET,
                "error": str(e),
                "list_error": str(e2)
            }

@app.get("/api/v1/crawl/status/{job_id}")
async def get_crawl_status(job_id: str):
    """크롤링 작업 상태 확인"""
    try:
        # 진행상황 파일 경로
        progress_file = PROGRESS_DIR / f"{job_id}.json"
        
        if not progress_file.exists():
            return {
                "status": "not_found",
                "job_id": job_id,
                "message": "Job not found"
            }
        
        # 진행상황 파일 읽기
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        return {
            "status": "found",
            "job_id": job_id,
            "progress": progress_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }

@app.get("/api/v1/crawl/jobs")
async def list_crawl_jobs():
    """모든 크롤링 작업 목록 조회"""
    try:
        jobs = []
        for progress_file in PROGRESS_DIR.glob("*.json"):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                
                jobs.append({
                    "job_id": progress_file.stem,
                    "status": progress_data.get("status", "unknown"),
                    "created_at": progress_data.get("created_at"),
                    "total_items": progress_data.get("total_items", 0),
                    "processed_items": progress_data.get("processed_items", 0),
                    "successful_items": progress_data.get("successful_items", 0),
                    "failed_items": progress_data.get("failed_items", 0)
                })
            except Exception as e:
                print(f"⚠️ 진행상황 파일 읽기 실패: {progress_file} - {e}")
                continue
        
        # 생성 시간 기준으로 정렬 (최신순)
        jobs.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        return {
            "status": "success",
            "total_jobs": len(jobs),
            "jobs": jobs
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/api/v1/debug/logo-flow")
async def debug_logo_flow(infomax_code: str):
    """로고 조회 플로우 전체 디버깅"""
    try:
        result = {"infomax_code": infomax_code, "steps": []}
        
        # 1. master_data 조회
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "infomax_code": infomax_code,
            "limit": 1
        })
        result["steps"].append({
            "step": "master_query",
            "response": master_response,
            "success": isinstance(master_response, dict) and master_response.get('data')
        })
        
        # 2. logo_hash 추출
        logo_hash = None
        if isinstance(master_response, dict) and master_response.get('data'):
            master_data = master_response['data'][0]
            logo_hash = master_data.get('logo_hash')
        
        if not logo_hash:
            logo_hash = hashlib.md5(infomax_code.encode('utf-8')).hexdigest()
            result["steps"].append({
                "step": "logo_hash_fallback",
                "logo_hash": logo_hash,
                "reason": "not_found_in_master"
            })
        else:
            result["steps"].append({
                "step": "logo_hash_from_master",
                "logo_hash": logo_hash
            })
        
        # 3. logos 테이블 조회
        logos_response = existing_api.query_table("raw_data", "logos", {
            "search_column": "logo_hash",
            "search": logo_hash,
            "is_deleted": False,
            "limit": 1
        })
        result["steps"].append({
            "step": "logos_query",
            "response": logos_response,
            "success": isinstance(logos_response, dict) and logos_response.get('data')
        })
        
        # 4. logo_files 테이블 조회
        if isinstance(logos_response, dict) and logos_response.get('data'):
            logo_id = logos_response['data'][0]['logo_id']
            files_response = existing_api.query_table("raw_data", "logo_files", {
                "page": 1,
                "size": 1000
            })
            result["steps"].append({
                "step": "logo_files_query",
                "logo_id": logo_id,
                "response": files_response,
                "success": isinstance(files_response, dict) and files_response.get('data')
            })
            
            # 5. MinIO 객체 확인
            if isinstance(files_response, dict) and files_response.get('data'):
                files = files_response['data']
                for f in files:
                    if f.get('minio_object_key'):
                        try:
                            stat = minio_client.stat_object(MINIO_BUCKET, f['minio_object_key'])
                            result["steps"].append({
                                "step": "minio_check",
                                "object_key": f['minio_object_key'],
                                "exists": True,
                                "size": stat.size
                            })
                        except Exception as e:
                            result["steps"].append({
                                "step": "minio_check",
                                "object_key": f['minio_object_key'],
                                "exists": False,
                                "error": str(e)
                            })
        
        return result
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/v1/debug/seed-file")
async def debug_seed_file(infomax_code: str, size: int = 256, format: str = "png"):
    """테스트용 파일을 서버에서 생성하여 MinIO와 DB에 저장"""
    try:
        # master → logo_hash
        master = existing_api.query_table("raw_data", "logo_master", {"infomax_code": infomax_code, "limit": 1})
        if not isinstance(master, dict) or not master.get("data"):
            raise HTTPException(status_code=404, detail="infomax_code not found in master")
        logo_hash = master["data"][0].get("logo_hash")

        # 간단 이미지 생성
        img = Image.new("RGB", (size, size), color=(173, 216, 230))
        buffer = io.BytesIO()
        fmt = format.upper()
        if fmt == "WEBP":
            img.save(buffer, format="WEBP", quality=88)
        elif fmt in ("JPG", "JPEG"):
            img.save(buffer, format="JPEG", quality=88)
        else:
            img.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()

        # MinIO 업로드
        object_key = f"{logo_hash}_{size}.{format.lower()}"
        minio_client.put_object(
            MINIO_BUCKET,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type=f"image/{format.lower()}"
        )

        # logos upsert 보장
        logo_upsert = existing_api.upsert_data("raw_data", "logos", {
            "data": {"logo_hash": logo_hash, "is_deleted": False},
            "conflict_columns": ["logo_hash"]
        })
        if isinstance(logo_upsert, dict):
            logo_id = (
                logo_upsert.get("data", {}).get("logo_id")
                if isinstance(logo_upsert.get("data"), dict)
                else logo_upsert.get("logo_id")
            )
        else:
            logo_id = None
        if not logo_id:
            check = existing_api.query_table("raw_data", "logos", {"page": 1, "search_column": "logo_hash", "search": logo_hash})
            if isinstance(check, dict) and check.get("data"):
                logo_id = check["data"][0].get("logo_id")

        if not logo_id:
            raise HTTPException(status_code=500, detail="Failed to ensure logo record")

        # logo_files upsert
        file_payload = {
            "data": {
                "logo_id": logo_id,
                "file_format": format.lower(),
                "data_source": "manual",
                "upload_type": "manual",
                "dimension_width": size,
                "dimension_height": size,
                "file_size": len(data),
                "minio_object_key": object_key,
                "is_original": True
            },
            "conflict_columns": ["minio_object_key"]
        }
        file_upsert = existing_api.upsert_data("raw_data", "logo_files", file_payload)

        return {
            "status": "seeded",
            "infomax_code": infomax_code,
            "logo_hash": logo_hash,
            "logo_id": logo_id,
            "object_key": object_key,
            "bytes": len(data),
            "file_upsert": file_upsert
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 기존 API 연동 엔드포인트들
@app.get("/api/v1/existing/schemas")
async def get_existing_schemas():
    """기존 API에서 스키마 목록 조회"""
    try:
        response = requests.get(f"{EXISTING_API_BASE}/api/schemas")
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch schemas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/existing/tables/{schema}")
async def get_existing_tables(schema: str):
    """기존 API에서 테이블 목록 조회"""
    try:
        response = requests.get(f"{EXISTING_API_BASE}/api/schemas/{schema}/tables")
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch tables")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/existing/query/{schema}/{table_name}")
async def query_existing_table(schema: str, table_name: str, page: int = 1, search_column: str = None, search: str = None):
    """기존 API를 통해 테이블 쿼리 (페이지네이션 방식)"""
    try:
        params = {"page": page}
        if search_column and search:
            params.update({
                "search_column": search_column,
                "search": search
            })
        
        response = requests.get(
            f"{EXISTING_API_BASE}/api/schemas/{schema}/tables/{table_name}/query",
            params=params
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to query table")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 크롤링 관련 엔드포인트
class CrawlSingleRequest(BaseModel):
    infomax_code: str
    ticker: str
    api_domain: Optional[str] = None

@app.post("/api/v1/crawl/single")
# @limiter.limit("5/minute")  # 임시 비활성화
async def crawl_single_logo(request: Request, crawl_request: CrawlSingleRequest):
    """단일 로고 크롤링 - 실제 크롤링 실행 후 결과 반환 (간단 동기)"""
    logger.info(f"Crawl request: {crawl_request.infomax_code} from {request.client.host}")
    try:
        # 크롤러 인스턴스 생성
        crawler = LogoCrawler()
        ok = await crawler.crawl_logo(crawl_request.infomax_code, crawl_request.ticker, crawl_request.api_domain)
        return {
            "status": "success" if ok else "failed",
            "infomax_code": crawl_request.infomax_code,
            "ticker": crawl_request.ticker,
            "api_domain": crawl_request.api_domain
        }
    except Exception as e:
        logger.error(f"Crawl failed for {crawl_request.infomax_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TickerInfo(BaseModel):
    infomax_code: str
    ticker: str
    api_domain: Optional[str] = None

class CrawlBatchRequest(BaseModel):
    tickers: List[TickerInfo]
    job_id: Optional[str] = None

@app.post("/api/v1/crawl/batch")
async def crawl_batch_logos(request: CrawlBatchRequest):
    """배치 로고 크롤링"""
    try:
        tickers_data = [{"infomax_code": t.infomax_code, "ticker": t.ticker, "api_domain": t.api_domain} for t in request.tickers]
        
        # 쿼터 체크 (logo.dev 사용 예상량)
        logo_dev_count = sum(1 for t in tickers_data if t.get('api_domain') == 'logo_dev')
        if logo_dev_count > 0:
            if not logo_dev_quota.check_and_consume_quota(logo_dev_count):
                print(f"⚠️ logo.dev 쿼터 부족으로 {logo_dev_count}건 스킵")
                # logo.dev 항목 제거하고 다른 소스만 처리
                tickers_data = [t for t in tickers_data if t.get('api_domain') != 'logo_dev']
        
        if not tickers_data:
            return {"status": "no_quota", "message": "No items available after quota check"}
        
        # result_job_id = await crawler.crawl_batch(tickers_data, request.job_id)
        result_job_id = "test_job_id"  # 임시로 비활성화
        return {
            "status": "started", 
            "job_id": result_job_id, 
            "message": f"Batch crawling started for {len(tickers_data)} items",
            "quota_skipped": logo_dev_count if logo_dev_count > 0 and not logo_dev_quota.check_and_consume_quota(0) else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/crawl/missing")
async def crawl_missing_logos(
    limit: int = 100,
    fs_exchange: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    prefix: Optional[str] = None
):
    """로고가 없는 종목들 크롤링 - 스트리밍 처리로 메모리 효율적"""
    try:
        # 스트리밍으로 미보유 종목 수집
        missing_items = await collect_missing_logos_streaming(
            limit=limit,
            fs_exchange=fs_exchange,
            country=country,
            is_active=is_active,
            prefix=prefix
        )
        
        if not missing_items:
            return {"status": "no_missing", "message": "No missing logos found with given filters"}
        
        print(f"🔍 미보유 종목 {len(missing_items)}개 발견")
        
        # 크롤링할 데이터 준비
        tickers = []
        for item in missing_items:
            infomax_code = item['infomax_code']
            crawling_ticker = item.get('crawling_ticker', infomax_code)
            api_domain = item.get('api_domain', 'tradingview')
            
            tickers.append({
                "infomax_code": infomax_code,
                "ticker": crawling_ticker,
                "api_domain": api_domain
            })
        
        # 쿼터 체크 (logo.dev 사용 예상량)
        logo_dev_count = sum(1 for t in tickers if t.get('api_domain') == 'logo_dev')
        if logo_dev_count > 0:
            if not logo_dev_quota.check_and_consume_quota(logo_dev_count):
                print(f"⚠️ logo.dev 쿼터 부족으로 {logo_dev_count}건 스킵")
                # logo.dev 항목 제거하고 다른 소스만 처리
                tickers = [t for t in tickers if t.get('api_domain') != 'logo_dev']
        
        if not tickers:
            return {"status": "no_quota", "message": "No items available after quota check"}
        
        # 배치 크롤링 시작 (백그라운드 작업으로 즉시 반환)
        job_id = f"missing_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 진행상황 파일 생성
        progress_data = {
            "job_id": job_id,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "total_items": len(tickers),
            "processed_items": 0,
            "successful_items": 0,
            "failed_items": 0,
            "items": []
        }
        
        # 진행상황 파일 저장
        progress_file = PROGRESS_DIR / f"{job_id}.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        print(f"🔍 크롤링 작업 시작: {job_id}")
        print(f"📊 크롤링 대상: {len(tickers)}개 종목")
        
        # 실제 크롤링 작업 수행 (백그라운드)
        import asyncio
        import threading
        
        def run_crawl():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(execute_crawl_batch(tickers, job_id))
            loop.close()
        
        thread = threading.Thread(target=run_crawl, daemon=True)
        thread.start()

        return {
            "status": "started",
            "job_id": job_id,
            "message": f"Missing logos crawling started for {len(tickers)} items",
            "filters_applied": {
                "fs_exchange": fs_exchange,
                "country": country,
                "is_active": is_active,
                "prefix": prefix
            },
            "quota_skipped": logo_dev_count if logo_dev_count > 0 and not logo_dev_quota.check_and_consume_quota(0) else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def collect_missing_logos_streaming(
    limit: int = 100,
    fs_exchange: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    prefix: Optional[str] = None
) -> List[Dict]:
    """스트리밍으로 미보유 로고 수집 - 메모리 효율적"""
    collected = []
    page = 1
    size = 1000  # 한 번에 가져올 최대 수
    
    # 필터 조건 준비
    filters = {
        "fs_exchange": fs_exchange,
        "country": country,
        "is_active": is_active,
        "prefix": prefix
    }
    
    while len(collected) < limit:
        print(f"🔍 페이지 {page} 조회 중... (현재 수집: {len(collected)}/{limit})")
        
        # 1. prefix가 있으면 search로 먼저 필터링
        if prefix:
            print(f"   prefix '{prefix}'로 검색...")
            response = existing_api.query_table("raw_data", "logo_master", {
                "search": prefix,
                "search_column": "infomax_code",
                "page": page,
                "size": size
            })
        else:
            # 2. 모든 데이터를 페이징으로 수집
            print(f"   전체 데이터 조회...")
            response = existing_api.query_table("raw_data", "logo_master", {
                "page": page,
                "size": size
            })
        
        if not response or not response.get('data'):
            print(f"   ❌ 응답 없음 또는 데이터 없음")
            break
        
        print(f"   📊 페이지 {page}에서 {len(response['data'])}개 항목 조회")
        
        # 3. 가져온 데이터를 실시간으로 필터링
        page_missing_count = 0
        for item in response['data']:
            if len(collected) >= limit:
                break
                
            # 모든 항목을 크롤링 대상으로 간주 (중복 체크는 나중에 구현)
            # 추가 필터 조건 확인
            if should_include_item(item, filters):
                collected.append(item)
                page_missing_count += 1
                print(f"      ✅ 수집: {item.get('infomax_code')}")
        
        print(f"   📊 페이지 {page}에서 {page_missing_count}개 미보유 항목 수집")
        
        # 4. 마지막 페이지인지 확인
        if page >= response.get('total_pages', 1):
            print(f"   📄 마지막 페이지 도달")
            break
            
        page += 1
    
    return collected

def should_include_item(item: Dict, filters: Dict) -> bool:
    """아이템이 필터 조건에 맞는지 확인"""
    if filters.get('fs_exchange') and item.get('fs_exchange') != filters['fs_exchange']:
        return False
    
    if filters.get('country') and item.get('country') != filters['country']:
        return False
    
    if filters.get('is_active') is not None and item.get('is_active') != filters['is_active']:
        return False
    
    # prefix는 이미 API에서 필터링되었으므로 추가 확인 불필요
    return True

async def is_logo_missing(infomax_code: str) -> bool:
    """해당 infomax_code의 로고가 실제로 없는지 확인"""
    try:
        # 1. logo_hash 조회
        logo_hash = get_logo_hash_from_master(infomax_code)
        
        # 2. logos 테이블에서 확인
        logos_response = existing_api.query_table("raw_data", "logos", {
            "search_column": "logo_hash",
            "search": logo_hash,
            "is_deleted": False,
            "limit": 1
        })
        
        if not logos_response or not logos_response.get('data'):
            return True  # 로고 없음
        
        logo_id = logos_response['data'][0]['logo_id']
        
        # 3. logo_files 테이블에서 실제 파일 확인
        files_response = existing_api.query_table("raw_data", "logo_files", {
            "page": 1,
            "size": 100
        })
        
        if not files_response or not files_response.get('data'):
            return True  # 파일 없음
        
        # 해당 logo_id의 파일이 있는지 확인
        files = files_response['data']
        for f in files:
            if f.get('logo_id') == logo_id and f.get('minio_object_key'):
                # MinIO에서 실제 파일 존재 확인
                try:
                    minio_client.stat_object(MINIO_BUCKET, f['minio_object_key'])
                    return False  # 로고 있음
                except:
                    continue  # 파일 없음, 계속 확인
        
        return True  # 로고 없음
        
    except Exception as e:
        print(f"⚠️ 로고 존재 확인 오류: {infomax_code} - {e}")
        return True  # 오류 시 크롤링 대상으로 간주

async def execute_crawl_batch(tickers: List[Dict], job_id: str):
    """실제 크롤링 배치 실행"""
    progress_file = PROGRESS_DIR / f"{job_id}.json"
    
    try:
        for i, ticker in enumerate(tickers):
            print(f"   {i+1}. {ticker['infomax_code']} ({ticker['ticker']}) - 크롤링 시작")
            
            # 진행상황 업데이트
            await update_progress(progress_file, {
                "processed_items": i + 1,
                "current_item": ticker['infomax_code']
            })
            
            # 실제 크롤링 시뮬레이션 (LogoCrawler가 없으므로)
            success = await simulate_crawl_single(ticker)
            
            if success:
                print(f"      ✅ 성공: {ticker['infomax_code']}")
                await update_progress(progress_file, {
                    "successful_items": i + 1
                })
            else:
                print(f"      ❌ 실패: {ticker['infomax_code']}")
                await update_progress(progress_file, {
                    "failed_items": i + 1
                })
            
            # 진행상황에 아이템 정보 추가
            item_info = {
                "infomax_code": ticker['infomax_code'],
                "ticker": ticker['ticker'],
                "status": "success" if success else "failed",
                "processed_at": datetime.now().isoformat()
            }
            
            # 기존 진행상황 읽기
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            if "items" not in progress_data:
                progress_data["items"] = []
            progress_data["items"].append(item_info)
            
            # 파일 저장
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            # 크롤링 간격 (1초)
            await asyncio.sleep(1)
        
        # 작업 완료
        await update_progress(progress_file, {
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        })
        
        print(f"🎉 크롤링 작업 완료: {job_id}")
        
    except Exception as e:
        print(f"❌ 크롤링 작업 오류: {job_id} - {e}")
        await update_progress(progress_file, {
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })

async def simulate_crawl_single(ticker: Dict) -> bool:
    """단일 크롤링 시뮬레이션"""
    try:
        if LogoCrawler is None:
            print("      ❌ LogoCrawler 미로딩: playwright 환경이 준비되지 않았습니다")
            return False

        print(f"      🚀 실제 크롤링 시작: {ticker['infomax_code']} ({ticker['ticker']})")
        crawler = LogoCrawler()
        # api_domain은 환경변수에서 읽도록 설계되었을 수 있으므로 None 전달
        ok = await crawler.crawl_logo(ticker['infomax_code'], ticker['ticker'], None)
        print(f"      ✅ 크롤링 결과: {'성공' if ok else '실패'} - {ticker['infomax_code']}")
        return bool(ok)
     
    except Exception as e:
        print(f"      ❌ 크롤링 오류: {e}")
        return False

async def update_progress(progress_file: Path, updates: Dict):
    """진행상황 파일 업데이트"""
    try:
        # 기존 진행상황 읽기
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        # 업데이트 적용
        for key, value in updates.items():
            if key == "items":
                # items는 추가 (append)
                if "items" not in progress_data:
                    progress_data["items"] = []
                if isinstance(value, list):
                    progress_data["items"].extend(value)
                else:
                    progress_data["items"].append(value)
            else:
                progress_data[key] = value
        
        # 파일 저장
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"⚠️ 진행상황 업데이트 실패: {e}")

@app.get("/api/v1/quota/status")
async def get_quota_status():
    """API 쿼터 상태 조회"""
    try:
        today = date.today()
        
        # logo.dev 쿼터 상태
        logo_dev_usage = logo_dev_quota._get_current_usage(today)
        logo_dev_remaining = max(0, LOGO_DEV_DAILY_LIMIT - logo_dev_usage)
        
        return {
            "date_utc": today.isoformat(),
            "logo_dev": {
                "used": logo_dev_usage,
                "limit": LOGO_DEV_DAILY_LIMIT,
                "remaining": logo_dev_remaining,
                "percentage": round((logo_dev_usage / LOGO_DEV_DAILY_LIMIT) * 100, 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 로고 관리 API
@app.post("/api/v1/logos/upload")
async def upload_logo(
    infomax_code: str = Form(...),
    file: UploadFile = File(...),
    format: str = Form("png"),
    size: int = Form(256),
    data_source: str = Form("manual")
):
    """신규 로고 업로드"""
    try:
        # 1. 파일 검증
        if not validate_image_file(file):
            raise HTTPException(status_code=400, detail="Invalid file type. Only PNG, JPEG, WebP, SVG are supported")
        
        # 2. infomax_code 검증 (기존 master 데이터에 있는지 확인)
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "infomax_code": infomax_code,
            "limit": 1
        })
        
        if not master_response or not master_response.get('data'):
            raise HTTPException(status_code=404, detail=f"infomax_code '{infomax_code}' not found in master data")
        
        # 3. 이미지 데이터 읽기
        image_data = await file.read()
        
        # 4. 이미지 처리
        processed_image = process_uploaded_image(image_data, target_size=size, target_format=format)
        
        # 5. logo_hash 조회 (DB에서)
        logo_hash = get_logo_hash_from_master(infomax_code)
        
        # 6. MinIO에 업로드 (logo_hash 사용)
        minio_key = f"{logo_hash}_{size}.{format.lower()}"
        minio_client.put_object(
            MINIO_BUCKET, 
            minio_key, 
            io.BytesIO(processed_image),
            length=len(processed_image),
            content_type=f"image/{format.lower()}"
        )
        
        # 7. DB에 저장
        success = save_logo_data(infomax_code, logo_hash, {
            "format": format.lower(),
            "source": data_source,
            "upload_type": "manual",
            "width": size,
            "height": size,
            "size": len(processed_image),
            "minio_key": minio_key,
            "is_original": True
        })
        
        if success:
            return {
                "status": "success", 
                "message": "Logo uploaded successfully",
                "data": {
                    "infomax_code": infomax_code,
                    "logo_hash": logo_hash,
                    "format": format.lower(),
                    "size": size,
                    "minio_key": minio_key
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save logo data to database")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.put("/api/v1/logos/{infomax_code}")
async def update_logo(
    infomax_code: str,
    file: UploadFile = File(...),
    format: str = Form("png"),
    size: int = Form(256)
):
    """기존 로고 수정"""
    try:
        # 1. 기존 로고 조회
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "infomax_code": infomax_code,
            "limit": 1
        })
        
        if not master_response or not master_response.get('data'):
            raise HTTPException(status_code=404, detail=f"infomax_code '{infomax_code}' not found in master data")
        
        # 2. 파일 검증
        if not validate_image_file(file):
            raise HTTPException(status_code=400, detail="Invalid file type. Only PNG, JPEG, WebP, SVG are supported")
        
        # 3. 이미지 데이터 읽기 및 처리
        image_data = await file.read()
        processed_image = process_uploaded_image(image_data, target_size=size, target_format=format)
        
        # 4. logo_hash 조회 (DB에서)
        logo_hash = get_logo_hash_from_master(infomax_code)
        
        # 5. 기존 파일 삭제 (MinIO)
        try:
            minio_client.remove_object(MINIO_BUCKET, f"{logo_hash}_{size}.{format.lower()}")
        except:
            pass  # 파일이 없어도 계속 진행
        
        # 6. 새 파일 업로드 (logo_hash 사용)
        minio_key = f"{logo_hash}_{size}.{format.lower()}"
        minio_client.put_object(
            MINIO_BUCKET, 
            minio_key, 
            io.BytesIO(processed_image),
            length=len(processed_image),
            content_type=f"image/{format.lower()}"
        )
        
        # 7. DB에 저장 (기존 데이터 업데이트)
        success = save_logo_data(infomax_code, logo_hash, {
            "format": format.lower(),
            "source": "manual",
            "upload_type": "manual",
            "width": size,
            "height": size,
            "size": len(processed_image),
            "minio_key": minio_key,
            "is_original": True
        })
        
        if success:
            return {
                "status": "success", 
                "message": "Logo updated successfully",
                "data": {
                    "infomax_code": infomax_code,
                    "logo_hash": logo_hash,
                    "format": format.lower(),
                    "size": size,
                    "minio_key": minio_key
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update logo data in database")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@app.delete("/api/v1/logos/{infomax_code}")
async def delete_logo(infomax_code: str):
    """로고 삭제 (논리적 삭제)"""
    try:
        # 1. 먼저 master 데이터에서 infomax_code로 조회하여 실제 logo_hash 확인
        master_response = existing_api.query_table("raw_data", "logo_master", {
            "infomax_code": infomax_code,
            "limit": 1
        })
        
        if not master_response or 'data' not in master_response or not master_response['data']:
            raise HTTPException(status_code=404, detail="Ticker not found in master data")
        
        master_data = master_response['data'][0]
        logo_hash = master_data['logo_hash']
        
        # 2. logos 테이블에서 해당 logo_hash로 삭제되지 않은 레코드 확인
        logo_response = existing_api.query_table("raw_data", "logos", {
            "logo_hash": logo_hash,
            "is_deleted": False,
            "limit": 1
        })
        
        if not logo_response or 'data' not in logo_response or not logo_response['data']:
            raise HTTPException(status_code=404, detail="Logo not found")
        
        # 2. logos 테이블에서 is_deleted = true로 업데이트
        logo_data = {
            "data": {
                "logo_hash": logo_hash,
                "is_deleted": True,
                "deleted_by": "api_user"
            },
            "conflict_columns": ["logo_hash"]
        }
        
        result = existing_api.upsert_data("raw_data", "logos", logo_data)
        
        if result:
            return {
                "status": "success", 
                "message": "Logo deleted successfully",
                "data": {
                    "infomax_code": infomax_code,
                    "logo_hash": logo_hash,
                    "deleted_at": datetime.now().isoformat()
                }
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete logo from database")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@app.get("/api/v1/debug/test-logo")
async def debug_test_logo(infomax_code: str = "DEBUG:TEST"):
    """디버그용 로고 생성 테스트"""
    try:
        ticker = {
            "infomax_code": infomax_code,
            "ticker": "DEBUG-TEST"
        }
        
        result = await create_test_logo_file(ticker)
        return {
            "success": result,
            "infomax_code": infomax_code,
            "message": "테스트 로고 생성 완료" if result else "테스트 로고 생성 실패"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "infomax_code": infomax_code
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="info"
    )

#!/usr/bin/env python3
"""
모의 데이터를 사용한 크롤링 테스트
- 기존 API 없이 크롤링 기능 테스트
- MinIO 저장 확인
- 로고 조회 테스트
"""

import requests
import json
import time
from minio import Minio
from PIL import Image
import io
import hashlib

def test_crawling_with_mock_data():
    """모의 데이터를 사용한 크롤링 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 모의 데이터를 사용한 크롤링 테스트")
    print("=" * 60)
    
    # 1. API 서버 상태 확인
    print("1️⃣ API 서버 상태 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ API 서버 정상: {health.get('status')}")
            print(f"   📊 MinIO: {health.get('minio')}")
        else:
            print(f"   ❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ API 서버 연결 실패: {e}")
        return
    
    # 2. 모의 로고 데이터 생성 및 업로드
    print(f"\n2️⃣ 모의 로고 데이터 생성 및 업로드...")
    test_infomax_code = "TEST:MOCK"
    test_ticker = "MOCK"
    
    # 테스트 로고 이미지 생성
    test_logo_data = create_test_logo_image()
    print(f"   ✅ 테스트 로고 이미지 생성: {len(test_logo_data)} bytes")
    
    # 로고 업로드
    success = upload_test_logo(base_url, test_infomax_code, test_ticker, test_logo_data)
    
    if success:
        # 3. 업로드된 로고 확인
        print(f"\n3️⃣ 업로드된 로고 확인...")
        check_uploaded_logo(base_url, test_infomax_code)
        
        # 4. MinIO 직접 확인
        print(f"\n4️⃣ MinIO 직접 확인...")
        check_minio_directly(test_infomax_code)
        
        # 5. 로고 조회 테스트
        print(f"\n5️⃣ 로고 조회 테스트...")
        test_logo_retrieval(base_url, test_infomax_code)
    else:
        print(f"   ❌ 로고 업로드 실패")

def create_test_logo_image():
    """테스트 로고 이미지 생성"""
    
    # 간단한 테스트 이미지 생성 (240x240 PNG)
    img = Image.new('RGB', (240, 240), color='lightgreen')
    
    # 텍스트 추가
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.load_default()
    except:
        font = None
    
    # 텍스트 그리기
    text = "MOCK LOGO"
    if font:
        draw.text((120, 120), text, fill='darkgreen', font=font, anchor='mm')
    else:
        draw.text((120, 120), text, fill='darkgreen', anchor='mm')
    
    # PNG로 변환
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    return img_buffer.getvalue()

def upload_test_logo(base_url: str, infomax_code: str, ticker: str, logo_data: bytes):
    """테스트 로고 업로드"""
    
    try:
        files = {
            'file': ('test_logo.png', logo_data, 'image/png')
        }
        data = {
            'infomax_code': infomax_code,
            'format': 'png',
            'size': '240',
            'data_source': 'test'
        }
        
        response = requests.post(f"{base_url}/api/v1/logos/upload", 
                              files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 로고 업로드 성공")
            print(f"   📊 상태: {result.get('status')}")
            print(f"   📊 메시지: {result.get('message')}")
            return True
        else:
            print(f"   ❌ 로고 업로드 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ 업로드 오류: {e}")
        return False

def check_uploaded_logo(base_url: str, infomax_code: str):
    """업로드된 로고 확인"""
    
    # 1. 로고 메타데이터 조회
    print(f"   📊 로고 메타데이터 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": infomax_code}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"      ✅ 메타데이터 조회 성공")
            print(f"      📊 로고 존재: {data.get('logo_exists')}")
            print(f"      📊 로고 해시: {data.get('logo_hash')}")
            
            file_info = data.get('file_info', {})
            if file_info:
                print(f"      📊 파일 형식: {file_info.get('file_format')}")
                print(f"      📊 파일 크기: {file_info.get('file_size')} bytes")
                print(f"      📊 MinIO 키: {file_info.get('minio_object_key')}")
                print(f"      📊 데이터 소스: {file_info.get('data_source')}")
            else:
                print(f"      ❌ 파일 정보 없음")
        else:
            print(f"      ❌ 메타데이터 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"      ❌ 오류: {e}")

def check_minio_directly(infomax_code: str):
    """MinIO 직접 확인"""
    
    try:
        minio_client = Minio(
            'localhost:9000',
            access_key='minioadmin',
            secret_key='minioadmin123',
            secure=False
        )
        
        bucket_name = 'logos'
        
        # 로고 해시 생성 (테스트용)
        logo_hash = hashlib.md5(infomax_code.encode()).hexdigest()
        
        # 가능한 파일명들 확인
        possible_keys = [
            f"{logo_hash}_240.png",
            f"{logo_hash}_256.png",
            f"{logo_hash}_300.png",
            f"{logo_hash}_original.png"
        ]
        
        print(f"   📊 MinIO 파일 확인...")
        print(f"   🔍 로고 해시: {logo_hash}")
        
        found_files = []
        for key in possible_keys:
            try:
                stat = minio_client.stat_object(bucket_name, key)
                print(f"      ✅ 파일 존재: {key} ({stat.size} bytes)")
                found_files.append(key)
            except:
                print(f"      ❌ 파일 없음: {key}")
        
        if not found_files:
            # 모든 파일 목록 확인
            print(f"   🔍 MinIO 전체 파일 목록...")
            objects = list(minio_client.list_objects(bucket_name))
            print(f"      📊 총 파일 수: {len(objects)}개")
            for obj in objects:
                print(f"         - {obj.object_name} ({obj.size} bytes)")
        
    except Exception as e:
        print(f"   ❌ MinIO 확인 오류: {e}")

def test_logo_retrieval(base_url: str, infomax_code: str):
    """로고 이미지 조회 테스트"""
    
    test_sizes = [240, 300]
    
    for size in test_sizes:
        try:
            print(f"   {size}px 조회...")
            response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                                  params={"format": "png", "size": size}, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"      ✅ 성공: {content_type}, {content_length} bytes")
            else:
                print(f"      ❌ 실패: {response.status_code}")
                print(f"      응답: {response.text}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

if __name__ == "__main__":
    test_crawling_with_mock_data()
    
    print("\n" + "=" * 60)
    print("🎯 모의 데이터를 사용한 크롤링 테스트 완료!")
    print("=" * 60)

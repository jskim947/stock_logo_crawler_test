#!/usr/bin/env python3
"""
로고 조회 문제 진단 및 해결
- 단계별 디버깅
- MinIO 파일 경로 확인
- API 응답 분석
"""

import requests
import json
from minio import Minio

def debug_logo_retrieval():
    """로고 조회 문제 진단"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 로고 조회 문제 진단")
    print("=" * 60)
    
    # 1. API 서버 상태 확인
    print("1️⃣ API 서버 상태 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ API 서버 정상")
        else:
            print(f"   ❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ API 서버 연결 실패: {e}")
        return
    
    # 2. 로고 메타데이터 상세 조회
    print("\n2️⃣ 로고 메타데이터 상세 조회...")
    infomax_code = "AMX:AAA"
    
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": infomax_code}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 메타데이터 조회 성공")
            print(f"   📊 종목: {data.get('infomax_code')}")
            print(f"   📊 로고 해시: {data.get('logo_hash')}")
            print(f"   📊 로고 존재: {data.get('logo_exists')}")
            
            file_info = data.get('file_info', {})
            print(f"   📊 MinIO 키: {file_info.get('minio_object_key')}")
            print(f"   📊 파일 형식: {file_info.get('file_format')}")
            print(f"   📊 파일 크기: {file_info.get('file_size')} bytes")
            print(f"   📊 차원: {file_info.get('dimension_width')}x{file_info.get('dimension_height')}")
            
            minio_key = file_info.get('minio_object_key')
            if minio_key:
                # 3. MinIO 직접 확인
                print(f"\n3️⃣ MinIO 직접 확인...")
                check_minio_file(minio_key)
                
                # 4. API 로고 조회 테스트
                print(f"\n4️⃣ API 로고 조회 테스트...")
                test_api_logo_retrieval(base_url, infomax_code, minio_key)
        else:
            print(f"   ❌ 메타데이터 조회 실패: {response.status_code}")
            print(f"   응답: {response.text}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def check_minio_file(minio_key):
    """MinIO 파일 직접 확인"""
    try:
        minio_client = Minio(
            'localhost:9000',
            access_key='minioadmin',
            secret_key='minioadmin123',
            secure=False
        )
        
        bucket_name = 'logos'
        
        # 파일 존재 확인
        try:
            stat = minio_client.stat_object(bucket_name, minio_key)
            print(f"   ✅ MinIO 파일 존재: {minio_key}")
            print(f"   📊 크기: {stat.size} bytes")
            print(f"   📊 수정일: {stat.last_modified}")
        except Exception as e:
            print(f"   ❌ MinIO 파일 없음: {e}")
            
            # 비슷한 파일들 찾기
            print(f"   🔍 비슷한 파일들 검색...")
            try:
                prefix = minio_key.split('_')[0]  # 해시 부분만 추출
                objects = list(minio_client.list_objects(bucket_name, prefix=prefix))
                print(f"   📊 찾은 파일들:")
                for obj in objects:
                    print(f"      - {obj.object_name} ({obj.size} bytes)")
            except Exception as list_error:
                print(f"   ❌ 파일 목록 조회 실패: {list_error}")
    except Exception as e:
        print(f"   ❌ MinIO 연결 실패: {e}")

def test_api_logo_retrieval(base_url, infomax_code, expected_minio_key):
    """API 로고 조회 테스트"""
    
    # 다양한 크기로 테스트
    test_cases = [
        {"format": "png", "size": 240},
        {"format": "png", "size": 256},
        {"format": "png", "size": 300},
    ]
    
    for test_case in test_cases:
        print(f"   {test_case['format'].upper()} {test_case['size']}px 테스트...")
        try:
            response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                                  params=test_case, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"      ✅ 성공: {content_type}, {content_length} bytes")
            else:
                print(f"      ❌ 실패: {response.status_code}")
                if response.status_code == 404:
                    print(f"         응답: {response.text}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

def test_direct_minio_access():
    """MinIO 직접 접근 테스트"""
    print("\n5️⃣ MinIO 직접 접근 테스트...")
    
    base_url = "http://localhost:8005"
    
    try:
        minio_client = Minio(
            'localhost:9000',
            access_key='minioadmin',
            secret_key='minioadmin123',
            secure=False
        )
        
        bucket_name = 'logos'
        
        # 모든 파일 목록
        objects = list(minio_client.list_objects(bucket_name))
        print(f"   📊 MinIO 총 파일 수: {len(objects)}개")
        
        for i, obj in enumerate(objects[:5]):
            print(f"   {i+1}. {obj.object_name} ({obj.size} bytes)")
            
            # 각 파일을 API로 접근 시도
            if obj.object_name.endswith('.png'):
                print(f"      API 접근 테스트...")
                try:
                    # MinIO 직접 URL 시도
                    minio_url = f"http://localhost:9000/{bucket_name}/{obj.object_name}"
                    response = requests.get(minio_url, timeout=5)
                    if response.status_code == 200:
                        print(f"         ✅ MinIO 직접 접근 성공")
                    else:
                        print(f"         ❌ MinIO 직접 접근 실패: {response.status_code}")
                except Exception as e:
                    print(f"         ❌ MinIO 직접 접근 오류: {e}")
    except Exception as e:
        print(f"   ❌ MinIO 테스트 오류: {e}")

if __name__ == "__main__":
    debug_logo_retrieval()
    test_direct_minio_access()
    
    print("\n" + "=" * 60)
    print("🎯 로고 조회 문제 진단 완료!")
    print("=" * 60)

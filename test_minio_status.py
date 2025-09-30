#!/usr/bin/env python3
"""
MinIO 상태 및 파일 확인
- MinIO 연결 상태 확인
- 버킷 내용 확인
- 파일 경로 확인
"""

import requests
import json

def test_minio_status():
    """MinIO 상태 확인"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 MinIO 상태 및 파일 확인")
    print("=" * 50)
    
    # 1. API 서버 상태 확인
    print("1️⃣ API 서버 상태 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ API 서버 정상")
            print(f"   📊 MinIO: {health.get('minio')}")
        else:
            print(f"   ❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ API 서버 연결 실패: {e}")
        return
    
    # 2. 로고 메타데이터에서 MinIO 경로 확인
    print("\n2️⃣ 로고 메타데이터에서 MinIO 경로 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": "AMX:AAA"}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            file_info = data.get('file_info', {})
            minio_key = file_info.get('minio_object_key')
            print(f"   📊 MinIO 객체 키: {minio_key}")
            print(f"   📊 파일 형식: {file_info.get('file_format')}")
            print(f"   📊 파일 크기: {file_info.get('file_size')} bytes")
            
            if minio_key:
                print(f"\n   🔍 MinIO 객체 '{minio_key}' 직접 접근 테스트...")
                # MinIO 직접 접근 URL (일반적으로 /minio/ 경로 사용)
                minio_url = f"{base_url}/minio/logos/{minio_key}"
                print(f"   📊 시도 URL: {minio_url}")
                
                try:
                    minio_response = requests.get(minio_url, timeout=5)
                    if minio_response.status_code == 200:
                        print(f"      ✅ MinIO 직접 접근 성공: {len(minio_response.content)} bytes")
                    else:
                        print(f"      ❌ MinIO 직접 접근 실패: {minio_response.status_code}")
                except Exception as e:
                    print(f"      ❌ MinIO 직접 접근 오류: {e}")
        else:
            print(f"   ❌ 로고 메타데이터 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")
    
    # 3. 다른 로고들도 확인
    print("\n3️⃣ 다른 로고들 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/logos/search", 
                              params={"has_logo": True, "limit": 3}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logos = data.get('results', [])
            
            for i, logo in enumerate(logos):
                infomax_code = logo.get('infomax_code')
                logo_hash = logo.get('logo_hash')
                print(f"   {i+1}. {infomax_code} - {logo_hash}")
                
                # 각 로고의 상세 정보 확인
                try:
                    detail_response = requests.get(f"{base_url}/api/v1/logo-info", 
                                                 params={"infomax_code": infomax_code}, timeout=5)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        file_info = detail_data.get('file_info', {})
                        minio_key = file_info.get('minio_object_key')
                        print(f"      MinIO 키: {minio_key}")
                    else:
                        print(f"      ❌ 상세 정보 조회 실패: {detail_response.status_code}")
                except Exception as e:
                    print(f"      ❌ 상세 정보 조회 오류: {e}")
        else:
            print(f"   ❌ 로고 목록 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_api_endpoints():
    """API 엔드포인트 확인"""
    print("\n4️⃣ API 엔드포인트 확인...")
    
    base_url = "http://localhost:8005"
    
    endpoints = [
        "/api/v1/logos/search",
        "/api/v1/logo-info",
        "/api/v1/logos/AMX:AAA",
        "/api/v1/stats",
        "/api/v1/health"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"   {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   {endpoint}: 오류 - {e}")

if __name__ == "__main__":
    test_minio_status()
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("🎯 MinIO 상태 확인 완료!")
    print("=" * 50)

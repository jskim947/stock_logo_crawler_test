#!/usr/bin/env python3
"""
기존 API 연결 상태 확인
- API 엔드포인트 테스트
- 데이터베이스 연결 확인
- 스키마 정보 확인
"""

import requests
import json

def test_existing_api():
    """기존 API 연결 상태 확인"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 기존 API 연결 상태 확인")
    print("=" * 50)
    
    # 1. API 서버 상태 확인
    print("1️⃣ API 서버 상태 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ API 서버 정상")
            print(f"   📊 MinIO: {health.get('minio')}")
            print(f"   📊 기존 API: {health.get('existing_api')}")
        else:
            print(f"   ❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ API 서버 연결 실패: {e}")
        return
    
    # 2. 기존 API 직접 테스트
    print(f"\n2️⃣ 기존 API 직접 테스트...")
    test_direct_api_connection(base_url)
    
    # 3. 디버그 엔드포인트 테스트
    print(f"\n3️⃣ 디버그 엔드포인트 테스트...")
    test_debug_endpoints(base_url)

def test_direct_api_connection(base_url: str):
    """기존 API 직접 연결 테스트"""
    
    # 기존 API 서버 URL (실제 서버 주소로 변경 필요)
    existing_api_url = "http://localhost:8000"  # 기본 포트
    
    print(f"   📊 기존 API 서버: {existing_api_url}")
    
    # 1. 기존 API 서버 상태 확인
    try:
        response = requests.get(f"{existing_api_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"      ✅ 기존 API 서버 정상")
        else:
            print(f"      ❌ 기존 API 서버 오류: {response.status_code}")
    except Exception as e:
        print(f"      ❌ 기존 API 서버 연결 실패: {e}")
    
    # 2. 테이블 조회 테스트
    test_tables = ["logo_master", "logos", "logo_files"]
    
    for table in test_tables:
        try:
            print(f"   📊 {table} 테이블 조회...")
            response = requests.get(f"{existing_api_url}/api/v1/query/raw_data/{table}", 
                                  params={"limit": 5}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                count = len(data.get('data', []))
                print(f"      ✅ {table}: {count}개 레코드")
                
                if count > 0:
                    sample = data['data'][0]
                    print(f"         샘플: {sample}")
            else:
                print(f"      ❌ {table} 조회 실패: {response.status_code}")
        except Exception as e:
            print(f"      ❌ {table} 조회 오류: {e}")

def test_debug_endpoints(base_url: str):
    """디버그 엔드포인트 테스트"""
    
    debug_endpoints = [
        "/api/v1/debug/test-api",
        "/api/v1/debug/query?table=logo_master&limit=5",
        "/api/v1/debug/query?table=logos&limit=5",
        "/api/v1/debug/query?table=logo_files&limit=5"
    ]
    
    for endpoint in debug_endpoints:
        try:
            print(f"   📊 {endpoint}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"      ✅ 성공: {type(data)}")
                if isinstance(data, dict):
                    print(f"         키: {list(data.keys())}")
            else:
                print(f"      ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

def test_manual_data_creation():
    """수동 데이터 생성 테스트"""
    print(f"\n4️⃣ 수동 데이터 생성 테스트...")
    
    base_url = "http://localhost:8005"
    
    # 테스트용 로고 데이터 생성
    test_data = {
        "infomax_code": "TEST:001",
        "ticker": "TEST",
        "english_name": "Test Company",
        "fs_exchange": "TEST",
        "country": "US",
        "is_active": True,
        "logo_hash": "test_hash_123456789"
    }
    
    try:
        print(f"   📊 테스트 데이터 생성...")
        response = requests.post(f"{base_url}/api/v1/debug/create-test-data", 
                               json=test_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"      ✅ 테스트 데이터 생성 성공: {result}")
        else:
            print(f"      ❌ 테스트 데이터 생성 실패: {response.status_code}")
            print(f"      응답: {response.text}")
    except Exception as e:
        print(f"      ❌ 오류: {e}")

if __name__ == "__main__":
    test_existing_api()
    test_manual_data_creation()
    
    print("\n" + "=" * 50)
    print("🎯 기존 API 연결 상태 확인 완료!")
    print("=" * 50)

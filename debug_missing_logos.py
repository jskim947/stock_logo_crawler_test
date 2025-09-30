#!/usr/bin/env python3
"""
미보유 로고 조회 로직 디버깅
- 기존 API 직접 조회
- 필터링 로직 확인
- 데이터 구조 분석
"""

import requests
import json

def debug_missing_logos():
    """미보유 로고 조회 로직 디버깅"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 미보유 로고 조회 로직 디버깅")
    print("=" * 60)
    
    # 1. 기존 API 직접 조회
    print("1️⃣ 기존 API 직접 조회...")
    try:
        # logo_master 테이블 조회
        response = requests.get(f"{base_url}/api/v1/debug/test-api", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 기존 API 연결 성공")
            print(f"   📊 logo_master 총 개수: {data.get('logo_master_count', 0)}")
            print(f"   📊 logos 총 개수: {data.get('logos_count', 0)}")
            print(f"   📊 logo_files 총 개수: {data.get('logo_files_count', 0)}")
            
            # 2. logo_master 샘플 데이터 조회
            print(f"\n2️⃣ logo_master 샘플 데이터 조회...")
            sample_response = requests.get(f"{base_url}/api/v1/debug/query", 
                                         params={"table": "logo_master", "limit": 5}, timeout=10)
            
            if sample_response.status_code == 200:
                sample_data = sample_response.json()
                print(f"   ✅ 샘플 데이터 조회 성공")
                print(f"   📊 샘플 데이터:")
                for i, item in enumerate(sample_data.get('data', [])[:3]):
                    print(f"      {i+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')[:50]}...")
                    print(f"         티커: {item.get('ticker')}, 거래소: {item.get('fs_exchange')}")
                    print(f"         로고 해시: {item.get('logo_hash')}")
                    print(f"         활성: {item.get('is_active')}")
            
            # 3. logos 테이블 샘플 데이터 조회
            print(f"\n3️⃣ logos 테이블 샘플 데이터 조회...")
            logos_response = requests.get(f"{base_url}/api/v1/debug/query", 
                                        params={"table": "logos", "limit": 5}, timeout=10)
            
            if logos_response.status_code == 200:
                logos_data = logos_response.json()
                print(f"   ✅ logos 샘플 데이터 조회 성공")
                print(f"   📊 logos 샘플 데이터:")
                for i, item in enumerate(logos_data.get('data', [])[:3]):
                    print(f"      {i+1}. 로고 ID: {item.get('logo_id')}")
                    print(f"         로고 해시: {item.get('logo_hash')}")
                    print(f"         삭제됨: {item.get('is_deleted')}")
                    print(f"         생성일: {item.get('created_at')}")
            
            # 4. 미보유 로고 조회 로직 테스트
            print(f"\n4️⃣ 미보유 로고 조회 로직 테스트...")
            test_missing_logic(base_url)
            
        else:
            print(f"   ❌ 기존 API 연결 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_missing_logic(base_url: str):
    """미보유 로고 조회 로직 테스트"""
    
    # 다양한 조건으로 테스트
    test_conditions = [
        {"limit": 5},
        {"has_logo": False, "limit": 5},
        {"has_logo": True, "limit": 5},
        {"prefix": "AMX", "limit": 5},
        {"prefix": "NYSE", "limit": 5},
        {"prefix": "NAS", "limit": 5},
    ]
    
    for i, condition in enumerate(test_conditions, 1):
        print(f"   {i}. 조건: {condition}")
        
        try:
            response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                                  params=condition, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                missing_logos = data.get('results', [])
                print(f"      📊 결과: {len(missing_logos)}개")
                
                if missing_logos:
                    print(f"      📋 샘플:")
                    for j, item in enumerate(missing_logos[:2]):
                        print(f"         {j+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')[:30]}...")
                else:
                    print(f"      ℹ️ 결과 없음")
            else:
                print(f"      ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

def test_direct_api_calls():
    """기존 API 직접 호출 테스트"""
    print(f"\n5️⃣ 기존 API 직접 호출 테스트...")
    
    base_url = "http://localhost:8005"
    
    # logo_master 테이블 직접 조회
    try:
        response = requests.get(f"{base_url}/api/v1/debug/query", 
                              params={"table": "logo_master", "limit": 10}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            print(f"   📊 logo_master 샘플 {len(items)}개:")
            
            for i, item in enumerate(items[:5]):
                print(f"      {i+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')[:40]}...")
                print(f"         티커: {item.get('ticker')}, 거래소: {item.get('fs_exchange')}")
                print(f"         로고 해시: {item.get('logo_hash')}")
                print(f"         활성: {item.get('is_active')}")
                print(f"         국가: {item.get('country')}")
                print()
        else:
            print(f"   ❌ logo_master 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    debug_missing_logos()
    test_direct_api_calls()
    
    print("\n" + "=" * 60)
    print("🎯 미보유 로고 조회 로직 디버깅 완료!")
    print("=" * 60)

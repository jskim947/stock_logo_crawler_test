#!/usr/bin/env python3
"""
직접 API 호출 테스트
- 스트리밍 처리 로직 직접 테스트
- 디버깅 출력 확인
"""

import requests
import json

def test_direct_api_call():
    """직접 API 호출 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 직접 API 호출 테스트")
    print("=" * 50)
    
    # NAS:Q prefix로 테스트
    print("1️⃣ NAS:Q prefix 테스트...")
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"prefix": "NAS:Q", "limit": 5}, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API 응답 성공")
            print(f"   상태: {result.get('status')}")
            print(f"   메시지: {result.get('message')}")
            print(f"   작업 ID: {result.get('job_id')}")
            print(f"   적용된 필터: {result.get('filters_applied')}")
        else:
            print(f"❌ API 호출 실패: {response.status_code}")
            print(f"   응답: {response.text}")
    except Exception as e:
        print(f"❌ 오류: {e}")

def test_manual_streaming():
    """수동 스트리밍 처리 테스트"""
    print("\n2️⃣ 수동 스트리밍 처리 테스트...")
    
    base_url = "http://localhost:8005"
    
    # 기존 API 직접 호출
    try:
        print("   NAS:Q 검색...")
        response = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                              params={
                                  "search": "NAS:Q",
                                  "search_column": "infomax_code",
                                  "page": 1,
                                  "size": 10
                              }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            print(f"   📊 조회된 항목: {len(items)}개")
            
            # 미보유 항목 필터링
            missing_items = [item for item in items if not item.get('has_any_file', True)]
            print(f"   📊 미보유 항목: {len(missing_items)}개")
            
            # 샘플 출력
            print("   📋 미보유 NAS:Q 항목 샘플:")
            for i, item in enumerate(missing_items[:5]):
                print(f"      {i+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')}")
        else:
            print(f"   ❌ 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_pagination_behavior():
    """페이징 동작 테스트"""
    print("\n3️⃣ 페이징 동작 테스트...")
    
    base_url = "http://localhost:8005"
    
    try:
        # 여러 페이지 조회
        for page in range(1, 4):
            print(f"   페이지 {page} 조회...")
            response = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                                  params={"page": page, "size": 5}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('data', [])
                print(f"      📊 {len(items)}개 항목")
                
                # 미보유 항목 확인
                missing = [item for item in items if not item.get('has_any_file', True)]
                print(f"      📊 미보유: {len(missing)}개")
                
                if missing:
                    print(f"      📋 샘플: {missing[0].get('infomax_code')}")
            else:
                print(f"      ❌ 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    test_direct_api_call()
    test_manual_streaming()
    test_pagination_behavior()
    
    print("\n" + "=" * 50)
    print("🎯 직접 API 테스트 완료!")
    print("=" * 50)

#!/usr/bin/env python3
"""
실제 데이터 확인 테스트
- 기존 API에서 실제 데이터 조회
- 스트리밍 처리 결과 검증
- 페이징 동작 확인
"""

import requests
import json
import time
from typing import Dict, List

def test_actual_data():
    """실제 데이터 확인 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 실제 데이터 확인 테스트")
    print("=" * 60)
    
    # 1. 기존 API에서 실제 데이터 조회
    print("1️⃣ 기존 API 데이터 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                              params={"page": 1, "size": 10}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            print(f"   ✅ 데이터 조회 성공: {len(items)}개 항목")
            
            # 미보유 항목들 확인
            missing_items = [item for item in items if not item.get('has_any_file', True)]
            print(f"   📊 미보유 항목: {len(missing_items)}개")
            
            # NAS:Q로 시작하는 항목들 확인
            nasq_items = [item for item in items if item.get('infomax_code', '').startswith('NAS:Q')]
            print(f"   📊 NAS:Q 항목: {len(nasq_items)}개")
            
            # 샘플 데이터 출력
            print("\n   📋 샘플 데이터:")
            for i, item in enumerate(items[:3]):
                print(f"      {i+1}. {item.get('infomax_code')} - has_any_file: {item.get('has_any_file')}")
            
            return items
        else:
            print(f"   ❌ 데이터 조회 실패: {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        return []

def test_pagination_consistency():
    """페이징 일관성 테스트"""
    print("\n2️⃣ 페이징 일관성 테스트...")
    
    base_url = "http://localhost:8005"
    
    try:
        # 여러 페이지 조회
        all_items = []
        for page in range(1, 4):  # 3페이지까지
            response = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                                  params={"page": page, "size": 5}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('data', [])
                all_items.extend(items)
                print(f"   페이지 {page}: {len(items)}개 항목")
            else:
                print(f"   페이지 {page}: 조회 실패 ({response.status_code})")
        
        # 중복 확인
        infomax_codes = [item.get('infomax_code') for item in all_items]
        unique_codes = set(infomax_codes)
        
        print(f"   📊 전체 수집: {len(all_items)}개")
        print(f"   📊 고유 항목: {len(unique_codes)}개")
        
        if len(all_items) == len(unique_codes):
            print("   ✅ 페이징 일관성 확인 (중복 없음)")
        else:
            print(f"   ⚠️ 페이징 일관성 문제 (중복 {len(all_items) - len(unique_codes)}개)")
            
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_streaming_with_verification():
    """스트리밍 처리 검증 테스트"""
    print("\n3️⃣ 스트리밍 처리 검증...")
    
    base_url = "http://localhost:8005"
    
    # NAS:Q prefix로 테스트
    print("   NAS:Q prefix 테스트...")
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"prefix": "NAS:Q", "limit": 5}, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ API 응답: {result.get('status')}")
            print(f"   📝 메시지: {result.get('message')}")
            
            # 실제로 NAS:Q 항목들이 있는지 확인
            print("\n   🔍 실제 NAS:Q 항목 확인...")
            nasq_response = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                                       params={"search": "NAS:Q", "search_column": "infomax_code", "size": 10}, timeout=10)
            
            if nasq_response.status_code == 200:
                nasq_data = nasq_response.json()
                nasq_items = nasq_data.get('data', [])
                print(f"   📊 실제 NAS:Q 항목: {len(nasq_items)}개")
                
                # 미보유 항목들
                missing_nasq = [item for item in nasq_items if not item.get('has_any_file', True)]
                print(f"   📊 미보유 NAS:Q 항목: {len(missing_nasq)}개")
                
                if missing_nasq:
                    print("   📋 미보유 NAS:Q 항목 샘플:")
                    for i, item in enumerate(missing_nasq[:3]):
                        print(f"      {i+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')}")
                else:
                    print("   ℹ️ 미보유 NAS:Q 항목이 없습니다.")
            else:
                print(f"   ❌ NAS:Q 항목 조회 실패: {nasq_response.status_code}")
        else:
            print(f"   ❌ API 호출 실패: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_memory_usage_simulation():
    """메모리 사용량 시뮬레이션"""
    print("\n4️⃣ 메모리 사용량 시뮬레이션...")
    
    base_url = "http://localhost:8005"
    
    # 다양한 limit으로 테스트
    limits = [5, 10, 20, 50]
    
    for limit in limits:
        print(f"   limit={limit} 테스트...")
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                                  params={"limit": limit}, timeout=30)
            end_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                print(f"      ✅ 성공: {result.get('message')} (응답시간: {end_time-start_time:.2f}초)")
            else:
                print(f"      ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

if __name__ == "__main__":
    # 1. 실제 데이터 확인
    items = test_actual_data()
    
    # 2. 페이징 일관성 테스트
    test_pagination_consistency()
    
    # 3. 스트리밍 처리 검증
    test_streaming_with_verification()
    
    # 4. 메모리 사용량 시뮬레이션
    test_memory_usage_simulation()
    
    print("\n" + "=" * 60)
    print("🎯 데이터 검증 테스트 완료!")
    print("=" * 60)

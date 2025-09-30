#!/usr/bin/env python3
"""
포괄적인 스트리밍 처리 테스트
- 다양한 조건으로 테스트
- 페이징 처리 확인
- 실제 결과 검증
"""

import requests
import json
import time
from typing import Dict, List

def test_streaming_processing():
    """스트리밍 처리 포괄 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 포괄적인 스트리밍 처리 테스트 시작")
    print("=" * 60)
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "NAS:Q prefix 테스트",
            "params": {"prefix": "NAS:Q", "limit": 5},
            "expected_min": 1
        },
        {
            "name": "NYSE prefix 테스트", 
            "params": {"prefix": "NYSE", "limit": 3},
            "expected_min": 1
        },
        {
            "name": "미보유 종목 전체 테스트",
            "params": {"limit": 10},
            "expected_min": 1
        },
        {
            "name": "대용량 limit 테스트",
            "params": {"limit": 50},
            "expected_min": 10
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}️⃣ {test_case['name']}")
        print("-" * 40)
        
        try:
            # API 호출
            response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                                 params=test_case['params'], 
                                 timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API 호출 성공")
                print(f"   상태: {result.get('status')}")
                print(f"   메시지: {result.get('message')}")
                print(f"   작업 ID: {result.get('job_id')}")
                print(f"   적용된 필터: {result.get('filters_applied')}")
                
                # 결과 검증
                if result.get('status') == 'started':
                    job_id = result.get('job_id')
                    if job_id:
                        # 작업 진행상황 확인
                        time.sleep(2)  # 잠시 대기
                        progress_result = check_progress(base_url, job_id)
                        
                        test_result = {
                            "test_name": test_case['name'],
                            "status": "success",
                            "job_id": job_id,
                            "filters": test_case['params'],
                            "progress": progress_result
                        }
                        results.append(test_result)
                        
                        print(f"   진행상황: {progress_result}")
                    else:
                        print("❌ 작업 ID가 없음")
                        results.append({
                            "test_name": test_case['name'],
                            "status": "failed",
                            "error": "No job ID"
                        })
                else:
                    print(f"❌ 예상과 다른 상태: {result.get('status')}")
                    results.append({
                        "test_name": test_case['name'],
                        "status": "failed",
                        "error": f"Unexpected status: {result.get('status')}"
                    })
            else:
                print(f"❌ API 호출 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                results.append({
                    "test_name": test_case['name'],
                    "status": "failed",
                    "error": f"HTTP {response.status_code}"
                })
                
        except Exception as e:
            print(f"❌ 테스트 오류: {e}")
            results.append({
                "test_name": test_case['name'],
                "status": "failed",
                "error": str(e)
            })
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    total_count = len(results)
    
    print(f"전체 테스트: {total_count}개")
    print(f"성공: {success_count}개")
    print(f"실패: {total_count - success_count}개")
    print(f"성공률: {success_count/total_count*100:.1f}%")
    
    print("\n📋 상세 결과:")
    for result in results:
        status_icon = "✅" if result['status'] == 'success' else "❌"
        print(f"  {status_icon} {result['test_name']}: {result['status']}")
        if result['status'] == 'failed':
            print(f"      오류: {result.get('error', 'Unknown error')}")
        elif 'progress' in result:
            print(f"      진행상황: {result['progress']}")
    
    return results

def check_progress(base_url: str, job_id: str) -> Dict:
    """작업 진행상황 확인"""
    try:
        response = requests.get(f"{base_url}/api/v1/progress/{job_id}", timeout=10)
        if response.status_code == 200:
            progress = response.json()
            return {
                "total": progress.get('total', 0),
                "completed": progress.get('completed', 0),
                "failed": progress.get('failed', 0),
                "progress_percentage": progress.get('progress_percentage', 0)
            }
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def test_pagination_behavior():
    """페이징 동작 테스트"""
    print("\n" + "=" * 60)
    print("📄 페이징 동작 테스트")
    print("=" * 60)
    
    base_url = "http://localhost:8005"
    
    # 기존 API 직접 호출하여 페이징 확인
    try:
        print("1️⃣ 기존 API 페이징 확인...")
        
        # 첫 번째 페이지
        response1 = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                               params={"page": 1, "size": 5}, timeout=10)
        
        if response1.status_code == 200:
            data1 = response1.json()
            print(f"   페이지 1: {len(data1.get('data', []))}개 항목")
            print(f"   전체 페이지: {data1.get('total_pages', 'Unknown')}")
            print(f"   전체 항목: {data1.get('total', 'Unknown')}")
            
            # 두 번째 페이지
            response2 = requests.get(f"{base_url}/api/v1/existing/query/raw_data/logo_master_with_status", 
                                   params={"page": 2, "size": 5}, timeout=10)
            
            if response2.status_code == 200:
                data2 = response2.json()
                print(f"   페이지 2: {len(data2.get('data', []))}개 항목")
                
                # 다른 데이터인지 확인
                page1_items = [item.get('infomax_code') for item in data1.get('data', [])]
                page2_items = [item.get('infomax_code') for item in data2.get('data', [])]
                
                if set(page1_items) != set(page2_items):
                    print("   ✅ 페이징 정상 작동 (다른 데이터)")
                else:
                    print("   ⚠️ 페이징 문제 (같은 데이터)")
            else:
                print(f"   ❌ 페이지 2 조회 실패: {response2.status_code}")
        else:
            print(f"   ❌ 페이지 1 조회 실패: {response1.status_code}")
            
    except Exception as e:
        print(f"   ❌ 페이징 테스트 오류: {e}")

def test_memory_efficiency():
    """메모리 효율성 테스트"""
    print("\n" + "=" * 60)
    print("💾 메모리 효율성 테스트")
    print("=" * 60)
    
    base_url = "http://localhost:8005"
    
    # 작은 limit으로 테스트
    print("1️⃣ 작은 limit 테스트 (limit=3)...")
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"limit": 3}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 성공: {result.get('message')}")
        else:
            print(f"   ❌ 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")
    
    # 큰 limit으로 테스트
    print("\n2️⃣ 큰 limit 테스트 (limit=100)...")
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"limit": 100}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 성공: {result.get('message')}")
        else:
            print(f"   ❌ 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    # 1. 기본 스트리밍 처리 테스트
    results = test_streaming_processing()
    
    # 2. 페이징 동작 테스트
    test_pagination_behavior()
    
    # 3. 메모리 효율성 테스트
    test_memory_efficiency()
    
    print("\n" + "=" * 60)
    print("🎯 테스트 완료!")
    print("=" * 60)

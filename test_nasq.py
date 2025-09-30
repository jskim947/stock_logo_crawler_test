#!/usr/bin/env python3
"""
NAS:Q로 시작하는 종목들 테스트
"""

import requests
import json
import time

def test_nasq_crawling():
    """NAS:Q로 시작하는 종목들 크롤링 테스트"""
    
    # API 서버 URL
    base_url = "http://localhost:8005"
    
    print("🔍 NAS:Q로 시작하는 종목들 크롤링 테스트 시작")
    
    # 1. API 서버 상태 확인
    try:
        print("\n1️⃣ API 서버 상태 확인...")
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ API 서버 정상 작동")
            print(f"   응답: {response.json()}")
        else:
            print(f"❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ API 서버 연결 실패: {e}")
        return
    
    # 2. NAS:Q로 시작하는 미보유 종목 조회
    try:
        print("\n2️⃣ NAS:Q로 시작하는 미보유 종목 조회...")
        params = {
            "prefix": "NAS:Q",
            "limit": 10
        }
        
        response = requests.get(f"{base_url}/api/v1/crawl/missing", params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 미보유 종목 조회 성공")
            print(f"   상태: {result.get('status')}")
            print(f"   메시지: {result.get('message')}")
            print(f"   작업 ID: {result.get('job_id')}")
            print(f"   적용된 필터: {result.get('filters_applied')}")
            print(f"   쿼터 스킵: {result.get('quota_skipped')}")
            
            # 작업 ID가 있으면 진행상황 확인
            if result.get('job_id'):
                job_id = result['job_id']
                print(f"\n3️⃣ 작업 진행상황 확인 (Job ID: {job_id})...")
                
                # 5초 대기 후 진행상황 확인
                time.sleep(5)
                
                progress_response = requests.get(f"{base_url}/api/v1/progress/{job_id}", timeout=10)
                if progress_response.status_code == 200:
                    progress = progress_response.json()
                    print("✅ 진행상황 조회 성공")
                    print(f"   전체: {progress.get('total', 0)}")
                    print(f"   완료: {progress.get('completed', 0)}")
                    print(f"   실패: {progress.get('failed', 0)}")
                    print(f"   진행률: {progress.get('progress_percentage', 0):.1f}%")
                else:
                    print(f"❌ 진행상황 조회 실패: {progress_response.status_code}")
        else:
            print(f"❌ 미보유 종목 조회 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            
    except Exception as e:
        print(f"❌ 미보유 종목 조회 오류: {e}")

if __name__ == "__main__":
    test_nasq_crawling()

#!/usr/bin/env python3
"""
크롤링 기능 테스트 스크립트
"""

import requests
import json
import time

BASE_URL = "http://localhost:8005"

def test_crawling():
    """크롤링 기능 테스트"""
    print("🔍 크롤링 기능 테스트 시작...\n")
    
    # 테스트할 종목 코드
    test_ticker = "AMX:AIM"
    
    # 1. 단일 로고 크롤링 테스트
    print("1. 단일 로고 크롤링 테스트")
    try:
        data = {
            "infomax_code": test_ticker,
            "ticker": "AIM",
            "api_domain": "aimimmuno.com"
        }
        
        print(f"   요청 데이터: {data}")
        response = requests.post(f"{BASE_URL}/api/v1/crawl/single", 
                               json=data, 
                               timeout=60)
        
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   응답: {json.dumps(result, indent=2, ensure_ascii=False)[:300]}...")
            print("   ✅ 단일 크롤링 성공")
        else:
            print(f"   오류: {response.text[:200]}")
            print("   ❌ 단일 크롤링 실패")
            
    except Exception as e:
        print(f"   예외: {e}")
        print("   ❌ 단일 크롤링 실패")
    
    print()
    
    # 2. 배치 로고 크롤링 테스트
    print("2. 배치 로고 크롤링 테스트")
    try:
        data = {
            "tickers": [
                {
                    "infomax_code": test_ticker,
                    "ticker": "AIM",
                    "api_domain": "aimimmuno.com"
                }
            ]
        }
        
        print(f"   요청 데이터: {data}")
        response = requests.post(f"{BASE_URL}/api/v1/crawl/batch", 
                               json=data, 
                               timeout=120)
        
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   응답: {json.dumps(result, indent=2, ensure_ascii=False)[:300]}...")
            print("   ✅ 배치 크롤링 성공")
        else:
            print(f"   오류: {response.text[:200]}")
            print("   ❌ 배치 크롤링 실패")
            
    except Exception as e:
        print(f"   예외: {e}")
        print("   ❌ 배치 크롤링 실패")
    
    print()
    
    # 3. 누락된 로고 크롤링 테스트
    print("3. 누락된 로고 크롤링 테스트")
    try:
        data = {
            "limit": 5,
            "filters": {
                "has_logo": False
            }
        }
        
        print(f"   요청 데이터: {data}")
        response = requests.post(f"{BASE_URL}/api/v1/crawl/missing", 
                               json=data, 
                               timeout=120)
        
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   응답: {json.dumps(result, indent=2, ensure_ascii=False)[:300]}...")
            print("   ✅ 누락된 로고 크롤링 성공")
        else:
            print(f"   오류: {response.text[:200]}")
            print("   ❌ 누락된 로고 크롤링 실패")
            
    except Exception as e:
        print(f"   예외: {e}")
        print("   ❌ 누락된 로고 크롤링 실패")
    
    print("\n✅ 크롤링 기능 테스트 완료")

if __name__ == "__main__":
    test_crawling()

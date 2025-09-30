#!/usr/bin/env python3
"""
빠른 API 테스트 스크립트
"""

import requests
import json

BASE_URL = "http://localhost:8005"

def test_endpoint(endpoint, method="GET", data=None):
    """엔드포인트 테스트"""
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"🔍 테스트: {method} {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        
        print(f"   상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"   응답: {json.dumps(result, indent=2, ensure_ascii=False)[:200]}...")
            except:
                print(f"   응답 크기: {len(response.content)} bytes")
            return True
        else:
            print(f"   오류: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"   예외: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 빠른 API 테스트 시작\n")
    
    # 기본 테스트들
    tests = [
        ("/", "GET"),
        ("/api/v1/logos/AMX:AIM", "GET"),
        ("/api/v1/logos/search?limit=5", "GET"),
        ("/api/v1/service/logos?infomax_code=AMX:AIM", "GET"),
        ("/api/v1/logos/AMX:AIM", "DELETE"),
    ]
    
    results = []
    for endpoint, method in tests:
        success = test_endpoint(endpoint, method)
        results.append((endpoint, success))
        print()
    
    # 결과 요약
    print("=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    success_count = 0
    for endpoint, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {endpoint}")
        if success:
            success_count += 1
    
    print(f"\n총 {len(results)}개 테스트 중 {success_count}개 성공")

if __name__ == "__main__":
    main()

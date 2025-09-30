#!/usr/bin/env python3
"""
최종 테스트 스크립트 - 모든 기능 테스트
"""

import requests
import json
import time

BASE_URL = "http://localhost:8005"

def test_endpoint(endpoint, method="GET", data=None, timeout=10):
    """엔드포인트 테스트"""
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"🔍 테스트: {method} {url}")
        
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        elif method == "DELETE":
            response = requests.delete(url, timeout=timeout)
        
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
    print("🚀 최종 API 테스트 시작\n")
    
    # 기본 테스트들
    tests = [
        # 기본 기능
        ("/", "GET"),
        ("/health", "GET"),
        ("/api/v1/quota", "GET"),
        
        # 로고 관리
        ("/api/v1/logos/AMX:AIM", "GET"),
        ("/api/v1/logos/search?limit=5", "GET"),
        ("/api/v1/service/logos?infomax_code=AMX:AIM", "GET"),
        
        # 통계 및 스키마
        ("/api/v1/stats", "GET"),
        ("/api/v1/schemas", "GET"),
        ("/api/v1/tables", "GET"),
        
        # 오류 처리 테스트
        ("/api/v1/logos/NONEXISTENT", "GET"),
        ("/api/v1/logos/INVALID:CODE", "GET"),
    ]
    
    results = []
    for endpoint, method in tests:
        success = test_endpoint(endpoint, method)
        results.append((endpoint, success))
        print()
        time.sleep(0.5)  # 요청 간 간격
    
    # 결과 요약
    print("=" * 60)
    print("📊 최종 테스트 결과 요약")
    print("=" * 60)
    
    success_count = 0
    for endpoint, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {endpoint}")
        if success:
            success_count += 1
    
    print(f"\n총 {len(results)}개 테스트 중 {success_count}개 성공")
    print(f"성공률: {success_count/len(results)*100:.1f}%")
    
    if success_count == len(results):
        print("\n🎉 모든 테스트가 성공했습니다!")
    else:
        print(f"\n⚠️  {len(results) - success_count}개 테스트가 실패했습니다.")

if __name__ == "__main__":
    main()

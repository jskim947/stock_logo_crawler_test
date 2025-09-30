#!/usr/bin/env python3
"""
오류 처리 테스트 스크립트
"""

import requests
import json

BASE_URL = "http://localhost:8005"

def test_error_handling():
    """오류 처리 테스트"""
    print("❌ 오류 처리 테스트 시작...\n")
    
    # 1. 존재하지 않는 로고 조회
    print("1. 존재하지 않는 로고 조회 테스트")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/logos/NONEXISTENT", timeout=10)
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ 404 오류 정상 처리")
        else:
            print(f"   응답: {response.text[:200]}")
            print("   ⚠️  예상과 다른 응답")
    except Exception as e:
        print(f"   예외: {e}")
    
    print()
    
    # 2. 잘못된 형식의 종목 코드
    print("2. 잘못된 형식의 종목 코드 테스트")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/logos/INVALID:CODE", timeout=10)
        print(f"   상태 코드: {response.status_code}")
        if response.status_code in [400, 404]:
            print("   ✅ 잘못된 형식 오류 정상 처리")
        else:
            print(f"   응답: {response.text[:200]}")
            print("   ⚠️  예상과 다른 응답")
    except Exception as e:
        print(f"   예외: {e}")
    
    print()
    
    # 3. 잘못된 파라미터로 검색
    print("3. 잘못된 파라미터로 검색 테스트")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/logos/search?limit=invalid", timeout=10)
        print(f"   상태 코드: {response.status_code}")
        if response.status_code in [400, 422]:
            print("   ✅ 잘못된 파라미터 오류 정상 처리")
        else:
            print(f"   응답: {response.text[:200]}")
            print("   ⚠️  예상과 다른 응답")
    except Exception as e:
        print(f"   예외: {e}")
    
    print()
    
    # 4. 존재하지 않는 엔드포인트
    print("4. 존재하지 않는 엔드포인트 테스트")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/nonexistent", timeout=10)
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ 404 오류 정상 처리")
        else:
            print(f"   응답: {response.text[:200]}")
            print("   ⚠️  예상과 다른 응답")
    except Exception as e:
        print(f"   예외: {e}")
    
    print()
    
    # 5. 잘못된 HTTP 메서드
    print("5. 잘못된 HTTP 메서드 테스트")
    try:
        response = requests.put(f"{BASE_URL}/api/v1/logos/AMX:AIM", timeout=10)
        print(f"   상태 코드: {response.status_code}")
        if response.status_code == 405:
            print("   ✅ 405 Method Not Allowed 정상 처리")
        else:
            print(f"   응답: {response.text[:200]}")
            print("   ⚠️  예상과 다른 응답")
    except Exception as e:
        print(f"   예외: {e}")
    
    print("\n✅ 오류 처리 테스트 완료")

if __name__ == "__main__":
    test_error_handling()

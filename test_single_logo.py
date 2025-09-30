#!/usr/bin/env python3
"""
단일 로고 조회 테스트
- API 서버 로그 확인
- 단계별 디버깅
"""

import requests
import json

def test_single_logo():
    """단일 로고 조회 테스트"""
    
    base_url = "http://localhost:8005"
    infomax_code = "AMX:AAA"
    
    print("🔍 단일 로고 조회 테스트")
    print("=" * 50)
    
    # 1. 로고 메타데이터 조회
    print("1️⃣ 로고 메타데이터 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": infomax_code}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 메타데이터 조회 성공")
            print(f"   📊 로고 해시: {data.get('logo_hash')}")
            print(f"   📊 로고 존재: {data.get('logo_exists')}")
            
            file_info = data.get('file_info', {})
            print(f"   📊 MinIO 키: {file_info.get('minio_object_key')}")
            print(f"   📊 파일 형식: {file_info.get('file_format')}")
            print(f"   📊 차원: {file_info.get('dimension_width')}x{file_info.get('dimension_height')}")
        else:
            print(f"   ❌ 메타데이터 조회 실패: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        return
    
    # 2. 로고 이미지 조회 (256px - 실제 존재하는 크기)
    print(f"\n2️⃣ 로고 이미지 조회 (256px)...")
    try:
        response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                              params={"format": "png", "size": 256}, timeout=10)
        
        print(f"   📊 응답 상태: {response.status_code}")
        print(f"   📊 응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            print(f"   ✅ 성공: {content_type}, {content_length} bytes")
        else:
            print(f"   ❌ 실패: {response.status_code}")
            print(f"   📝 응답 내용: {response.text}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    test_single_logo()
    
    print("\n" + "=" * 50)
    print("🎯 단일 로고 조회 테스트 완료!")
    print("=" * 50)

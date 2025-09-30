#!/usr/bin/env python3
"""
로고 조회 기능 테스트
- 처리된 로고 조회 테스트
- 다양한 형식/크기 조회 테스트
- 이미지 스트리밍 테스트
"""

import requests
import json
import time
from typing import Dict, List

def test_logo_retrieval():
    """로고 조회 기능 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 로고 조회 기능 테스트")
    print("=" * 60)
    
    # 1. API 서버 상태 확인
    print("1️⃣ API 서버 상태 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ API 서버 정상: {health.get('status')}")
            print(f"   📊 MinIO: {health.get('minio')}")
            print(f"   📊 기존 API: {health.get('existing_api')}")
        else:
            print(f"   ❌ API 서버 오류: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ API 서버 연결 실패: {e}")
        return
    
    # 2. 로고가 있는 종목들 조회
    print("\n2️⃣ 로고가 있는 종목들 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/logos/search", 
                              params={"has_logo": True, "limit": 5}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logos = data.get('results', [])
            print(f"   ✅ 로고 보유 종목: {len(logos)}개")
            
            if logos:
                print("   📋 로고 보유 종목 샘플:")
                for i, logo in enumerate(logos[:3]):
                    print(f"      {i+1}. {logo.get('infomax_code')} - {logo.get('english_name', 'N/A')}")
                    print(f"         해시: {logo.get('logo_hash')}")
                
                # 첫 번째 로고로 상세 테스트
                test_logo = logos[0]
                test_infomax_code = test_logo.get('infomax_code')
                
                if test_infomax_code:
                    print(f"\n   🔍 '{test_infomax_code}' 로고 상세 테스트...")
                    test_specific_logo(base_url, test_infomax_code)
            else:
                print("   ℹ️ 로고 보유 종목이 없습니다.")
        else:
            print(f"   ❌ 로고 검색 실패: {response.status_code}")
            print(f"   응답: {response.text}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_specific_logo(base_url: str, infomax_code: str):
    """특정 로고 상세 테스트"""
    
    # 3. 로고 메타데이터 조회
    print(f"   3️⃣ '{infomax_code}' 메타데이터 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": infomax_code}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"      ✅ 메타데이터 조회 성공")
            print(f"      📊 종목명: {data.get('english_name', 'N/A')}")
            print(f"      📊 로고 해시: {data.get('logo_hash')}")
            print(f"      📊 로고 존재: {data.get('logo_exists')}")
            
            file_info = data.get('file_info', {})
            if file_info:
                print(f"      📊 파일 형식: {file_info.get('file_format')}")
                print(f"      📊 파일 크기: {file_info.get('file_size')} bytes")
                print(f"      📊 데이터 소스: {file_info.get('data_source')}")
        else:
            print(f"      ❌ 메타데이터 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"      ❌ 오류: {e}")
    
    # 4. 로고 이미지 조회 (다양한 형식/크기)
    print(f"   4️⃣ '{infomax_code}' 이미지 조회 테스트...")
    
    test_formats = [
        {"format": "png", "size": 240},
        {"format": "png", "size": 300},
        {"format": "webp", "size": 240},
        {"format": "webp", "size": 300}
    ]
    
    for test_format in test_formats:
        try:
            print(f"      {test_format['format'].upper()} {test_format['size']}px 조회...")
            response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                                  params=test_format, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"         ✅ 성공: {content_type}, {content_length} bytes")
            else:
                print(f"         ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"         ❌ 오류: {e}")

def test_logo_upload_simulation():
    """로고 업로드 시뮬레이션 테스트"""
    print("\n5️⃣ 로고 업로드 시뮬레이션...")
    
    base_url = "http://localhost:8005"
    
    # 먼저 로고가 없는 종목 찾기
    try:
        response = requests.get(f"{base_url}/api/v1/logos/search", 
                              params={"has_logo": False, "limit": 1}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            missing_logos = data.get('results', [])
            
            if missing_logos:
                test_item = missing_logos[0]
                infomax_code = test_item.get('infomax_code')
                print(f"   📊 테스트 대상: {infomax_code}")
                
                # 업로드 가능한지 확인 (API 엔드포인트 존재 확인)
                print(f"   🔍 업로드 엔드포인트 확인...")
                try:
                    # OPTIONS 요청으로 엔드포인트 존재 확인
                    response = requests.options(f"{base_url}/api/v1/logos/upload", timeout=5)
                    if response.status_code in [200, 405]:  # 405는 Method Not Allowed (엔드포인트는 존재)
                        print(f"      ✅ 업로드 엔드포인트 존재")
                    else:
                        print(f"      ❌ 업로드 엔드포인트 없음: {response.status_code}")
                except Exception as e:
                    print(f"      ❌ 업로드 엔드포인트 확인 오류: {e}")
            else:
                print("   ℹ️ 미보유 로고 종목이 없습니다.")
        else:
            print(f"   ❌ 미보유 로고 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

def test_system_stats():
    """시스템 통계 조회 테스트"""
    print("\n6️⃣ 시스템 통계 조회...")
    
    base_url = "http://localhost:8005"
    
    try:
        response = requests.get(f"{base_url}/api/v1/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ 통계 조회 성공")
            print(f"   📊 전체 로고: {stats.get('total_logos', 0)}개")
            print(f"   📊 오늘 수집: {stats.get('today_logos', 0)}개")
            print(f"   📊 데이터 소스별:")
            
            source_stats = stats.get('source_stats', {})
            for source, count in source_stats.items():
                print(f"      {source}: {count}개")
        else:
            print(f"   ❌ 통계 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 오류: {e}")

if __name__ == "__main__":
    test_logo_retrieval()
    test_logo_upload_simulation()
    test_system_stats()
    
    print("\n" + "=" * 60)
    print("🎯 로고 조회 기능 테스트 완료!")
    print("=" * 60)

#!/usr/bin/env python3
"""
크롤링 대상 종목 찾기
- 다양한 조건으로 미보유 로고 조회
- 크롤링 가능한 종목 확인
"""

import requests
import json

def find_crawling_targets():
    """크롤링 대상 종목 찾기"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 크롤링 대상 종목 찾기")
    print("=" * 50)
    
    # 다양한 조건으로 테스트
    test_conditions = [
        {"prefix": "NAS:Q", "limit": 5},
        {"prefix": "NYSE", "limit": 5},
        {"prefix": "AMX", "limit": 5},
        {"has_logo": False, "limit": 10},
        {"limit": 10}  # 전체
    ]
    
    for i, condition in enumerate(test_conditions, 1):
        print(f"\n{i}️⃣ 조건 테스트: {condition}")
        
        try:
            response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                                  params=condition, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                missing_logos = data.get('results', [])
                print(f"   📊 미보유 로고: {len(missing_logos)}개")
                
                if missing_logos:
                    print("   📋 샘플 종목:")
                    for j, item in enumerate(missing_logos[:3]):
                        print(f"      {j+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')[:50]}...")
                        print(f"         티커: {item.get('ticker')}, 거래소: {item.get('fs_exchange')}")
                    
                    # 첫 번째 종목으로 크롤링 테스트
                    if i == 1:  # 첫 번째 조건에서만 크롤링 테스트
                        test_item = missing_logos[0]
                        test_infomax_code = test_item.get('infomax_code')
                        test_ticker = test_item.get('ticker')
                        
                        if test_infomax_code and test_ticker:
                            print(f"\n   🎯 '{test_infomax_code}' 크롤링 테스트...")
                            test_single_crawling(base_url, test_infomax_code, test_ticker)
                else:
                    print("   ℹ️ 미보유 로고 없음")
            else:
                print(f"   ❌ 조회 실패: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 오류: {e}")

def test_single_crawling(base_url: str, infomax_code: str, ticker: str):
    """단일 종목 크롤링 테스트"""
    
    print(f"   3️⃣ '{infomax_code}' 크롤링 실행...")
    
    # 크롤링 요청
    crawl_data = {
        "infomax_code": infomax_code,
        "ticker": ticker,
        "api_domain": None
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/crawl/single", 
                               json=crawl_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"      ✅ 크롤링 완료: {result.get('status')}")
            print(f"      📊 결과: {result}")
            
            # 크롤링 후 저장 확인
            print(f"\n   4️⃣ 크롤링 결과 저장 확인...")
            check_crawling_results(base_url, infomax_code)
        else:
            print(f"      ❌ 크롤링 실패: {response.status_code}")
            print(f"      📝 응답: {response.text}")
    except Exception as e:
        print(f"      ❌ 크롤링 오류: {e}")

def check_crawling_results(base_url: str, infomax_code: str):
    """크롤링 결과 확인"""
    
    # 1. 로고 메타데이터 확인
    print(f"      📊 로고 메타데이터 확인...")
    try:
        response = requests.get(f"{base_url}/api/v1/logo-info", 
                              params={"infomax_code": infomax_code}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"         ✅ 메타데이터 조회 성공")
            print(f"         📊 로고 존재: {data.get('logo_exists')}")
            print(f"         📊 로고 해시: {data.get('logo_hash')}")
            
            file_info = data.get('file_info', {})
            if file_info:
                print(f"         📊 파일 형식: {file_info.get('file_format')}")
                print(f"         📊 파일 크기: {file_info.get('file_size')} bytes")
                print(f"         📊 MinIO 키: {file_info.get('minio_object_key')}")
                print(f"         📊 데이터 소스: {file_info.get('data_source')}")
                
                # 2. MinIO 파일 확인
                minio_key = file_info.get('minio_object_key')
                if minio_key:
                    print(f"\n      📊 MinIO 파일 확인...")
                    check_minio_file(minio_key)
                
                # 3. 로고 이미지 조회 테스트
                print(f"\n      📊 로고 이미지 조회 테스트...")
                test_logo_retrieval(base_url, infomax_code)
            else:
                print(f"         ❌ 파일 정보 없음")
        else:
            print(f"         ❌ 메타데이터 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"         ❌ 오류: {e}")

def check_minio_file(minio_key: str):
    """MinIO 파일 확인"""
    try:
        from minio import Minio
        
        minio_client = Minio(
            'localhost:9000',
            access_key='minioadmin',
            secret_key='minioadmin123',
            secure=False
        )
        
        bucket_name = 'logos'
        
        # 파일 존재 확인
        try:
            stat = minio_client.stat_object(bucket_name, minio_key)
            print(f"            ✅ MinIO 파일 존재: {minio_key}")
            print(f"            📊 크기: {stat.size} bytes")
            print(f"            📊 수정일: {stat.last_modified}")
        except Exception as e:
            print(f"            ❌ MinIO 파일 없음: {e}")
    except Exception as e:
        print(f"            ❌ MinIO 연결 실패: {e}")

def test_logo_retrieval(base_url: str, infomax_code: str):
    """로고 이미지 조회 테스트"""
    
    test_sizes = [240, 300]
    
    for size in test_sizes:
        try:
            print(f"         {size}px 조회...")
            response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                                  params={"format": "png", "size": size}, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"            ✅ 성공: {content_type}, {content_length} bytes")
            else:
                print(f"            ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"            ❌ 오류: {e}")

if __name__ == "__main__":
    find_crawling_targets()
    
    print("\n" + "=" * 50)
    print("🎯 크롤링 대상 종목 찾기 완료!")
    print("=" * 50)

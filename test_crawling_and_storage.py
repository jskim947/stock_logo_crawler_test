#!/usr/bin/env python3
"""
크롤링 및 저장 테스트
- 특정 조건으로 크롤링 진행
- DB와 MinIO 저장 확인
- 결과 검증
"""

import requests
import json
import time
from typing import Dict, List
from minio import Minio

def test_crawling_and_storage():
    """크롤링 및 저장 테스트"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 크롤링 및 저장 테스트")
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
    
    # 2. 크롤링할 종목 선택 (NAS:Q로 시작하는 종목)
    print("\n2️⃣ 크롤링 대상 종목 조회...")
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"prefix": "NAS:Q", "limit": 3}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            missing_logos = data.get('results', [])
            print(f"   ✅ 미보유 로고 종목: {len(missing_logos)}개")
            
            if missing_logos:
                print("   📋 크롤링 대상 종목:")
                for i, item in enumerate(missing_logos[:3]):
                    print(f"      {i+1}. {item.get('infomax_code')} - {item.get('english_name', 'N/A')}")
                    print(f"         티커: {item.get('ticker')}")
                    print(f"         거래소: {item.get('fs_exchange')}")
                
                # 첫 번째 종목으로 크롤링 테스트
                test_item = missing_logos[0]
                test_infomax_code = test_item.get('infomax_code')
                test_ticker = test_item.get('ticker')
                
                if test_infomax_code and test_ticker:
                    print(f"\n   🎯 '{test_infomax_code}' 크롤링 테스트...")
                    test_single_crawling(base_url, test_infomax_code, test_ticker)
            else:
                print("   ℹ️ 크롤링 대상 종목이 없습니다.")
        else:
            print(f"   ❌ 미보유 로고 조회 실패: {response.status_code}")
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
            
            # 비슷한 파일들 찾기
            print(f"            🔍 비슷한 파일들 검색...")
            try:
                prefix = minio_key.split('_')[0]  # 해시 부분만 추출
                objects = list(minio_client.list_objects(bucket_name, prefix=prefix))
                print(f"            📊 찾은 파일들:")
                for obj in objects:
                    print(f"               - {obj.object_name} ({obj.size} bytes)")
            except Exception as list_error:
                print(f"            ❌ 파일 목록 조회 실패: {list_error}")
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

def test_batch_crawling():
    """배치 크롤링 테스트"""
    print("\n5️⃣ 배치 크롤링 테스트...")
    
    base_url = "http://localhost:8005"
    
    # 미보유 로고 2개 선택
    try:
        response = requests.get(f"{base_url}/api/v1/crawl/missing", 
                              params={"prefix": "NAS:Q", "limit": 2}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            missing_logos = data.get('results', [])
            
            if len(missing_logos) >= 2:
                # 배치 크롤링 요청
                batch_data = {
                    "tickers": [
                        {
                            "infomax_code": missing_logos[0].get('infomax_code'),
                            "ticker": missing_logos[0].get('ticker'),
                            "api_domain": None
                        },
                        {
                            "infomax_code": missing_logos[1].get('infomax_code'),
                            "ticker": missing_logos[1].get('ticker'),
                            "api_domain": None
                        }
                    ],
                    "job_id": f"test_batch_{int(time.time())}"
                }
                
                print(f"   📊 배치 크롤링 요청: {len(batch_data['tickers'])}개 종목")
                
                response = requests.post(f"{base_url}/api/v1/crawl/batch", 
                                       json=batch_data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ 배치 크롤링 시작: {result.get('status')}")
                    print(f"   📊 작업 ID: {result.get('job_id')}")
                else:
                    print(f"   ❌ 배치 크롤링 실패: {response.status_code}")
            else:
                print(f"   ℹ️ 배치 크롤링 대상 부족: {len(missing_logos)}개")
        else:
            print(f"   ❌ 미보유 로고 조회 실패: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 배치 크롤링 오류: {e}")

if __name__ == "__main__":
    test_crawling_and_storage()
    test_batch_crawling()
    
    print("\n" + "=" * 60)
    print("🎯 크롤링 및 저장 테스트 완료!")
    print("=" * 60)

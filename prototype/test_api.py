#!/usr/bin/env python3
"""
로고 관리 시스템 API 테스트 스위트
모든 API 엔드포인트를 종합적으로 테스트합니다.
"""

import requests
import os
import json
from PIL import Image
import io
import time

# 테스트 설정
BASE_URL = "http://localhost:8005"
EXISTING_API_BASE = "http://10.150.2.150:8004"

class APITester:
    """API 테스트 클래스"""
    
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.test_results = []
    
    def log_test(self, test_name, success, message=""):
        """테스트 결과 로깅"""
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
    
    def test_health_check(self):
        """헬스 체크 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("헬스 체크", True, f"상태: {data.get('status')}")
                return True
            else:
                self.log_test("헬스 체크", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("헬스 체크", False, f"오류: {e}")
            return False
    
    def test_quota_status(self):
        """쿼터 상태 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/quota/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                logo_dev = data.get('logo_dev', {})
                self.log_test("쿼터 상태", True, 
                    f"사용량: {logo_dev.get('used')}/{logo_dev.get('limit')} "
                    f"({logo_dev.get('percentage')}%)")
                return True
            else:
                self.log_test("쿼터 상태", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("쿼터 상태", False, f"오류: {e}")
            return False
    
    def test_logo_upload(self):
        """로고 업로드 테스트"""
        try:
            # 테스트 이미지 생성
            img = Image.new('RGB', (10, 10), color='red')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            test_image_data = buf.getvalue()
            
            # 임시 파일 생성
            temp_file = '/tmp/test_logo.png' if os.name != 'nt' else 'test_logo.png'
            with open(temp_file, 'wb') as f:
                f.write(test_image_data)
            
            # 업로드 요청
            url = f"{self.base_url}/api/v1/logos/upload"
            files = {'file': ('test_logo.png', open(temp_file, 'rb'), 'image/png')}
            data = {
                'infomax_code': 'AMX:AIM',
                'format': 'png',
                'size': '256',
                'data_source': 'manual'
            }
            
            response = requests.post(url, files=files, data=data, timeout=30)
            files['file'][1].close()
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("로고 업로드", True, f"logo_hash: {result.get('logo_hash')}")
                return True
            else:
                self.log_test("로고 업로드", False, f"상태 코드: {response.status_code}, 응답: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("로고 업로드", False, f"오류: {e}")
            return False
        finally:
            # 임시 파일 정리
            temp_file = '/tmp/test_logo.png' if os.name != 'nt' else 'test_logo.png'
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_logo_retrieval(self):
        """로고 조회 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/logos/AMX:AIM", timeout=10)
            if response.status_code == 200:
                self.log_test("로고 조회", True, f"파일 크기: {len(response.content)} bytes")
                return True
            else:
                self.log_test("로고 조회", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("로고 조회", False, f"오류: {e}")
            return False
    
    def test_crawl_missing(self):
        """미보유 로고 크롤링 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/crawl/missing?limit=5", timeout=90)
            if response.status_code == 200:
                data = response.json()
                self.log_test("미보유 크롤링", True, f"상태: {data.get('status')}")
                return True
            else:
                self.log_test("미보유 크롤링", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("미보유 크롤링", False, f"오류: {e}")
            return False
    
    def test_logo_search(self):
        """로고 검색 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/logos/search?limit=5", timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                self.log_test("로고 검색", True, f"검색 결과: {len(results)}개")
                return True
            else:
                self.log_test("로고 검색", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("로고 검색", False, f"오류: {e}")
            return False
    
    def test_service_logos(self):
        """서비스 연동 로고 조회 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/logo-info?infomax_code=AMX:AIM", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("서비스 연동", True, f"로고 존재: {data.get('logo_exists')}")
                return True
            else:
                self.log_test("서비스 연동", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("서비스 연동", False, f"오류: {e}")
            return False
    
    def test_logo_update(self):
        """로고 수정 테스트"""
        try:
            # 테스트 이미지 생성
            img = Image.new('RGB', (15, 15), color='blue')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            test_image_data = buf.getvalue()
            
            # 임시 파일 생성
            temp_file = '/tmp/test_update_logo.png' if os.name != 'nt' else 'test_update_logo.png'
            with open(temp_file, 'wb') as f:
                f.write(test_image_data)
            
            # 수정 요청
            url = f"{self.base_url}/api/v1/logos/AMX:AIM"
            files = {'file': ('test_update_logo.png', open(temp_file, 'rb'), 'image/png')}
            data = {
                'format': 'png',
                'size': '256'
            }
            
            response = requests.put(url, files=files, data=data, timeout=30)
            files['file'][1].close()
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("로고 수정", True, f"상태: {result.get('status')}")
                return True
            else:
                self.log_test("로고 수정", False, f"상태 코드: {response.status_code}, 응답: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("로고 수정", False, f"오류: {e}")
            return False
        finally:
            # 임시 파일 정리
            temp_file = '/tmp/test_update_logo.png' if os.name != 'nt' else 'test_update_logo.png'
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def test_logo_delete(self):
        """로고 삭제 테스트"""
        try:
            response = requests.delete(f"{self.base_url}/api/v1/logos/AMX:AIM", timeout=10)
            if response.status_code == 200:
                result = response.json()
                self.log_test("로고 삭제", True, f"상태: {result.get('status')}")
                return True
            else:
                self.log_test("로고 삭제", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("로고 삭제", False, f"오류: {e}")
            return False
    
    def test_batch_crawl(self):
        """배치 크롤링 테스트"""
        try:
            url = f"{self.base_url}/api/v1/crawl/batch"
            data = {
                "tickers": [
                    {
                        "infomax_code": "AMX:AIM",
                        "ticker": "AMX-AIM",
                        "api_domain": "tradingview"
                    }
                ]
            }
            
            response = requests.post(url, json=data, timeout=90)
            if response.status_code == 200:
                result = response.json()
                self.log_test("배치 크롤링", True, f"상태: {result.get('status')}")
                return True
            else:
                self.log_test("배치 크롤링", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("배치 크롤링", False, f"오류: {e}")
            return False
    
    def test_stats(self):
        """통계 조회 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/stats", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("통계 조회", True, f"상태: {data.get('status')}")
                return True
            else:
                self.log_test("통계 조회", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("통계 조회", False, f"오류: {e}")
            return False
    
    def test_existing_api_schemas(self):
        """기존 API 스키마 조회 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/existing/schemas", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("기존 API 스키마", True, f"스키마 수: {len(data) if isinstance(data, list) else 'N/A'}")
                return True
            else:
                self.log_test("기존 API 스키마", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("기존 API 스키마", False, f"오류: {e}")
            return False
    
    def test_existing_api_tables(self):
        """기존 API 테이블 조회 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/existing/tables/raw_data", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("기존 API 테이블", True, f"테이블 수: {len(data) if isinstance(data, list) else 'N/A'}")
                return True
            else:
                self.log_test("기존 API 테이블", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("기존 API 테이블", False, f"오류: {e}")
            return False
    
    def test_error_cases(self):
        """에러 케이스 테스트"""
        error_tests = []
        
        # 1. 존재하지 않는 로고 조회
        try:
            response = requests.get(f"{self.base_url}/api/v1/logos/NONEXISTENT:CODE", timeout=5)
            if response.status_code == 404:
                error_tests.append(("존재하지 않는 로고 조회", True))
            else:
                error_tests.append(("존재하지 않는 로고 조회", False))
        except Exception as e:
            error_tests.append(("존재하지 않는 로고 조회", False))
        
        # 2. 잘못된 파라미터로 검색
        try:
            response = requests.get(f"{self.base_url}/api/v1/logos/search?invalid_param=test", timeout=5)
            if response.status_code in [200, 400]:  # 200이면 무시, 400이면 올바른 에러 처리
                error_tests.append(("잘못된 파라미터 검색", True))
            else:
                error_tests.append(("잘못된 파라미터 검색", False))
        except Exception as e:
            error_tests.append(("잘못된 파라미터 검색", False))
        
        # 3. 존재하지 않는 진행상황 조회
        try:
            response = requests.get(f"{self.base_url}/api/v1/progress/nonexistent_job", timeout=5)
            if response.status_code == 404:
                error_tests.append(("존재하지 않는 진행상황 조회", True))
            else:
                error_tests.append(("존재하지 않는 진행상황 조회", False))
        except Exception as e:
            error_tests.append(("존재하지 않는 진행상황 조회", False))
        
        # 결과 로깅
        for test_name, success in error_tests:
            self.log_test(f"에러 케이스 - {test_name}", success, "에러 처리 확인")
        
        return all(success for _, success in error_tests)
    
    def test_existing_api_connection(self):
        """기존 API 연결 테스트"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/debug/test-api", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("기존 API 연결", True, f"상태: {data.get('status')}")
                return True
            else:
                self.log_test("기존 API 연결", False, f"상태 코드: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("기존 API 연결", False, f"오류: {e}")
            return False
    
    def run_single_test(self, test_name):
        """단일 테스트 실행"""
        print(f"🔍 개별 테스트 실행: {test_name}\n")
        
        # 테스트 결과 초기화
        self.test_results = []
        
        if test_name == "health":
            self.test_health_check()
        elif test_name == "quota":
            self.test_quota_status()
        elif test_name == "upload":
            self.test_logo_upload()
        elif test_name == "retrieval":
            self.test_logo_retrieval()
        elif test_name == "search":
            self.test_logo_search()
        elif test_name == "service":
            self.test_service_logos()
        elif test_name == "update":
            self.test_logo_update()
        elif test_name == "delete":
            self.test_logo_delete()
        elif test_name == "crawl":
            self.test_crawl_missing()
        elif test_name == "batch":
            self.test_batch_crawl()
        elif test_name == "stats":
            self.test_stats()
        elif test_name == "schemas":
            self.test_existing_api_schemas()
        elif test_name == "tables":
            self.test_existing_api_tables()
        elif test_name == "errors":
            self.test_error_cases()
        elif test_name == "connection":
            self.test_existing_api_connection()
        else:
            print(f"❌ 알 수 없는 테스트: {test_name}")
            print("사용 가능한 테스트: health, quota, upload, retrieval, search, service, update, delete, crawl, batch, stats, schemas, tables, errors, connection")
            return False
        
        # 개별 테스트 결과 출력
        print("\n" + "="*40)
        print("📊 테스트 결과")
        print("="*40)
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        print("="*40)
        return True

    def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 로고 관리 시스템 API 테스트 시작...\n")
        
        # 기본 연결 테스트
        if not self.test_health_check():
            print("❌ 서버 연결 실패. 테스트를 중단합니다.")
            return
        
        print()
        
        # 1. 시스템 상태 테스트
        print("🔧 시스템 상태 테스트")
        print("-" * 30)
        self.test_quota_status()
        self.test_existing_api_connection()
        self.test_stats()
        print()
        
        # 2. 로고 관리 테스트
        print("📁 로고 관리 테스트")
        print("-" * 30)
        self.test_logo_upload()
        self.test_logo_retrieval()
        self.test_logo_update()
        self.test_logo_delete()
        print()
        
        # 3. 로고 검색 및 서비스 연동 테스트
        print("🔍 로고 검색 및 서비스 연동 테스트")
        print("-" * 30)
        self.test_logo_search()
        self.test_service_logos()
        print()
        
        # 4. 크롤링 기능 테스트
        print("🕷️ 크롤링 기능 테스트")
        print("-" * 30)
        self.test_crawl_missing()
        self.test_batch_crawl()
        print()
        
        # 5. 기존 API 연동 테스트
        print("🔗 기존 API 연동 테스트")
        print("-" * 30)
        self.test_existing_api_schemas()
        self.test_existing_api_tables()
        print()
        
        # 6. 에러 케이스 테스트
        print("⚠️ 에러 케이스 테스트")
        print("-" * 30)
        self.test_error_cases()
        print()
        
        # 결과 요약
        self._print_test_summary()
    
    def _print_test_summary(self):
        """테스트 결과 요약 출력"""
        print("="*60)
        print("📊 테스트 결과 요약")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"총 테스트: {total_tests}")
        print(f"성공: {passed_tests}")
        print(f"실패: {failed_tests}")
        print(f"성공률: {(passed_tests/total_tests)*100:.1f}%")
        
        # 카테고리별 결과
        categories = {
            "시스템 상태": ["헬스 체크", "쿼터 상태", "기존 API 연결", "통계 조회"],
            "로고 관리": ["로고 업로드", "로고 조회", "로고 수정", "로고 삭제"],
            "검색 및 연동": ["로고 검색", "서비스 연동"],
            "크롤링": ["미보유 크롤링", "배치 크롤링"],
            "기존 API": ["기존 API 스키마", "기존 API 테이블"],
            "에러 처리": ["에러 케이스"]
        }
        
        print("\n📈 카테고리별 결과:")
        for category, test_names in categories.items():
            category_tests = [r for r in self.test_results if any(name in r['test'] for name in test_names)]
            if category_tests:
                category_passed = sum(1 for t in category_tests if t['success'])
                category_total = len(category_tests)
                print(f"  {category}: {category_passed}/{category_total} ({(category_passed/category_total)*100:.1f}%)")
        
        if failed_tests > 0:
            print("\n❌ 실패한 테스트:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['message']}")
        
        print("\n" + "="*60)
        if failed_tests == 0:
            print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
        else:
            print(f"⚠️ {failed_tests}개의 테스트가 실패했습니다. 위의 오류를 확인해주세요.")
        print("="*60)

def main():
    """메인 실행 함수"""
    import sys
    
    tester = APITester()
    
    if len(sys.argv) > 1:
        # 개별 테스트 실행
        test_name = sys.argv[1].lower()
        print(f"🔍 개별 테스트 실행: {test_name}")
        tester.run_single_test(test_name)
    else:
        # 전체 테스트 실행
        tester.run_all_tests()

if __name__ == "__main__":
    main()

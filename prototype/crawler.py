"""
로고 크롤링 모듈
TradingView와 logo.dev에서 로고를 수집하는 기능
"""

import asyncio
import aiohttp
import requests
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from io import BytesIO
import json

from playwright.async_api import async_playwright
from fake_useragent import UserAgent
from PIL import Image
from minio import Minio

class DateTimeEncoder(json.JSONEncoder):
    """datetime 객체를 JSON으로 직렬화하는 커스텀 인코더"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class LogoCrawler:
    """로고 크롤링 클래스"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.minio_client = Minio(
            os.getenv('MINIO_ENDPOINT', 'minio:9000'),
            access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
            secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin123'),
            secure=False
        )
        self.bucket = os.getenv('MINIO_BUCKET', 'logos')
        self.existing_api_base = os.getenv('EXISTING_API_BASE', 'http://10.150.2.150:8004')
        self.logo_dev_token = os.getenv('LOGO_DEV_TOKEN')
        
    async def crawl_tradingview(self, infomax_code: str, ticker: str) -> Optional[bytes]:
        """TradingView에서 로고 크롤링"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self.ua.random
                )
                # 페이지 타임아웃 설정
                context.set_default_timeout(20000)  # 20초
                
                page = await context.new_page()
                
                # TradingView 페이지로 이동
                url = f"https://www.tradingview.com/symbols/{ticker}/"
                await page.goto(url, timeout=20000)
                
                # 로고 이미지 선택자 (여러 가능성 시도)
                selectors = [
                    'img[data-testid="logo"]',
                    '.tv-symbol-header__logo img',
                    '.tv-symbol-header__logo svg',
                    'img[alt*="logo" i]',
                    'img[src*="logo" i]',
                    '.tv-symbol-header img',
                    'header img'
                ]
                
                for selector in selectors:
                    try:
                        element = await page.wait_for_selector(selector, timeout=15000)
                        if element:
                            # SVG인 경우
                            if 'svg' in selector:
                                svg_content = await element.inner_html()
                                return svg_content.encode('utf-8')
                            # IMG인 경우
                            else:
                                src = await element.get_attribute('src')
                                if src and src.startswith('http'):
                                    timeout = aiohttp.ClientTimeout(total=10)  # 10초 타임아웃
                                    async with aiohttp.ClientSession(timeout=timeout) as session:
                                        async with session.get(src) as response:
                                            if response.status == 200:
                                                return await response.read()
                    except:
                        continue
                
                await browser.close()
                return None
                
        except Exception as e:
            print(f"TradingView 크롤링 오류 ({infomax_code}): {e}")
            return None
    
    async def crawl_logo_dev(self, infomax_code: str, api_domain: str) -> Optional[bytes]:
        """logo.dev API에서 로고 크롤링"""
        try:
            if not self.logo_dev_token:
                print("LOGO_DEV_TOKEN이 설정되지 않았습니다")
                return None
            
            # API 쿼터 확인
            if not await self._check_quota('logo_dev'):
                print("logo.dev 일일 쿼터 초과")
                return None
            
            url = f"https://img.logo.dev/{api_domain}?token={self.logo_dev_token}&format=png&size=300&fallback=404"
            
            timeout = aiohttp.ClientTimeout(total=15)  # 15초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        # 쿼터 사용량 업데이트
                        await self._update_quota('logo_dev')
                        return await response.read()
                    else:
                        print(f"logo.dev API 오류: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"logo.dev 크롤링 오류 ({infomax_code}): {e}")
            return None
    
    async def _check_quota(self, provider: str) -> bool:
        """API 쿼터 확인"""
        try:
            # 기존 API를 통해 쿼터 확인
            timeout = aiohttp.ClientTimeout(total=10)  # 10초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.existing_api_base}/api/query/raw_data/ext_api_quota"
                params = {
                    "api_name": provider,
                    "quota_date": datetime.now().strftime('%Y-%m-%d'),
                    "limit": 1
                }
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"🔍 쿼터 확인 응답: {data}")
                        # 페이지네이션된 응답 구조 확인
                        if 'data' in data and data['data'] and len(data['data']) > 0:
                            used_count = data['data'][0].get('used_count', 0)
                            max_count = data['data'][0].get('max_count', 5000)
                            print(f"🔍 쿼터 사용량: {used_count}/{max_count}")
                            return used_count < max_count
                        elif data and len(data) > 0:
                            used_count = data[0].get('used_count', 0)
                            max_count = data[0].get('max_count', 5000)
                            print(f"🔍 쿼터 사용량 (직접): {used_count}/{max_count}")
                            return used_count < max_count
            print(f"🔍 쿼터 확인 실패, 기본값 True 반환")
            return True
        except:
            return True
    
    async def _update_quota(self, provider: str):
        """API 쿼터 사용량 업데이트"""
        try:
            # 기존 API를 통해 쿼터 업데이트
            timeout = aiohttp.ClientTimeout(total=10)  # 10초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.existing_api_base}/api/schemas/raw_data/tables/ext_api_quota/upsert"
                data = {
                    "api_name": provider,
                    "quota_date": datetime.now().strftime('%Y-%m-%d'),
                    "used_count": 1,
                    "max_count": 5000
                }
                async with session.post(url, json=data) as response:
                    pass  # 결과는 무시
        except:
            pass
    
    def convert_image(self, image_data: bytes, infomax_code: str) -> Dict[str, bytes]:
        """이미지를 다양한 크기로 변환"""
        try:
            # SVG인 경우 원본 그대로 반환
            if image_data.startswith(b'<svg') or image_data.startswith(b'<?xml'):
                return {"original": image_data}
            
            # BytesIO 객체를 생성하고 이미지 열기
            image_buffer = BytesIO(image_data)
            image = Image.open(image_buffer)
            
            # 표준 사이즈로 변환 (환경변수 IMAGE_SIZES 사용, 기본 240,300)
            sizes_env = os.getenv('IMAGE_SIZES', '240,300')
            try:
                sizes = [int(s.strip()) for s in sizes_env.split(',') if s.strip()]
            except Exception:
                sizes = [240, 300]
            formats = ['PNG', 'WebP']
            results = {}
            
            for size in sizes:
                for format_type in formats:
                    # 리사이즈
                    resized = image.resize((size, size), Image.Resampling.LANCZOS)
                    
                    # 바이트로 변환
                    output = BytesIO()
                    if format_type == 'PNG':
                        resized.save(output, format='PNG', optimize=True)
                    else:  # WebP
                        resized.save(output, format='WebP', quality=85, optimize=True)
                    
                    results[f"{format_type.lower()}_{size}"] = output.getvalue()
            
            return results
            
        except Exception as e:
            print(f"이미지 변환 오류 ({infomax_code}): {e}")
            # 변환 실패해도 원본은 저장
            result = {"original": image_data}
            print(f"🔍 변환 실패로 원본만 반환: {len(result)}개")
            return result
    
    async def save_to_minio(self, image_data: bytes, object_key: str, content_type: str = "image/png"):
        """MinIO에 이미지 저장"""
        try:
            self.minio_client.put_object(
                self.bucket,
                object_key,
                BytesIO(image_data),
                len(image_data),
                content_type=content_type
            )
            return True
        except Exception as e:
            print(f"MinIO 저장 오류: {e}")
            return False
    
    async def save_to_database(self, infomax_code: str, logo_hash: str, file_info: Dict):
        """데이터베이스에 로고 정보 저장"""
        print(f"🔍 DB 저장 시작: {infomax_code}, {logo_hash}")
        try:
            # 기존 API를 통해 데이터 저장
            timeout = aiohttp.ClientTimeout(total=15)  # 15초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # logos 테이블에 저장
                logo_url = f"{self.existing_api_base}/api/schemas/raw_data/tables/logos/upsert"
                logo_data = {
                    "data": {
                        "logo_hash": logo_hash,
                        "is_deleted": False,
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    },
                    "conflict_columns": ["logo_hash"]
                }
                async with session.post(logo_url, json=logo_data, headers={'Content-Type': 'application/json'}) as response:
                    print(f"🔍 logos 테이블 저장 응답: {response.status}")
                    if response.status == 200:
                        logo_result = await response.json()
                        print(f"🔍 logos 저장 결과: {logo_result}")
                        logo_id = logo_result.get('data', {}).get('logo_id')
                        
                        if logo_id:
                            print(f"🔍 logo_id 획득: {logo_id}")
                            # logo_files 테이블에 저장
                            file_url = f"{self.existing_api_base}/api/schemas/raw_data/tables/logo_files/upsert"
                            file_data = {
                                "data": {
                                    "logo_id": logo_id,
                                    "minio_object_key": file_info['object_key'],
                                    "file_format": file_info['format'],
                                    "dimension_width": file_info['dimension_width'],
                                    "dimension_height": file_info['dimension_height'],
                                    "file_size": file_info['file_size'],
                                    "is_original": file_info.get('is_original', False),
                                    "upload_type": "crawled",
                                    "data_source": file_info['data_source'],
                                    "created_at": datetime.now()
                                },
                                "conflict_columns": ["logo_id", "minio_object_key"]
                            }
                            async with session.post(file_url, json=file_data, headers={'Content-Type': 'application/json'}) as file_response:
                                print(f"🔍 logo_files 테이블 저장 응답: {file_response.status}")
                                if file_response.status == 200:
                                    file_result = await file_response.json()
                                    print(f"🔍 logo_files 저장 결과: {file_result}")
                                return file_response.status == 200
                        else:
                            print(f"❌ logo_id를 찾을 수 없음: {logo_result}")
                    else:
                        print(f"❌ logos 테이블 저장 실패: {response.status}")
                        error_text = await response.text()
                        print(f"❌ 오류 내용: {error_text}")
            return False
        except Exception as e:
            print(f"데이터베이스 저장 오류: {e}")
            return False
    
    async def crawl_logo(self, infomax_code: str, ticker: str, api_domain: str = None) -> bool:
        """로고 크롤링 메인 함수"""
        print(f"🔍🔍🔍 CRAWL_LOGO 함수 진입: {infomax_code}")
        print(f"🔍🔍🔍 파라미터: ticker={ticker}, api_domain={api_domain}")
        try:
            print(f"🔍 크롤링 시작: {infomax_code}, ticker={ticker}, api_domain={api_domain}")
            print(f"🔍 함수 진입 확인: {infomax_code}")
            
            # 타임아웃 설정 (60초)
            import asyncio
            try:
                result = await asyncio.wait_for(
                    self._crawl_logo_internal(infomax_code, ticker, api_domain),
                    timeout=60.0
                )
                print(f"🔍🔍🔍 CRAWL_LOGO 함수 완료: {infomax_code}, 결과: {result}")
                return result
            except asyncio.TimeoutError:
                print(f"🔍 크롤링 타임아웃: {infomax_code}")
                return False
                
        except Exception as e:
            print(f"🔍 크롤링 함수 오류: {infomax_code} - {e}")
            import traceback
            print(f"🔍 오류 상세: {traceback.format_exc()}")
            return False
    
    async def _crawl_logo_internal(self, infomax_code: str, ticker: str, api_domain: str = None) -> bool:
        """로고 크롤링 내부 함수"""
        try:
            print(f"🔍 내부 함수 진입: {infomax_code}")
            image_data = None
            data_source = None
            logo_hash = None
            
            # TradingView에서 크롤링 시도 (ticker가 있을 때만)
            if ticker and ticker.strip():
                print(f"🔍 TradingView 크롤링 시도: {infomax_code}")
                try:
                    image_data = await self.crawl_tradingview(infomax_code, ticker)
                    if image_data:
                        data_source = "tradingview"
                        logo_hash = hashlib.md5(f"tradingview_{infomax_code}".encode()).hexdigest()
                        print(f"🔍 TradingView 크롤링 성공: {infomax_code}")
                    else:
                        print(f"🔍 TradingView 크롤링 실패: {infomax_code}")
                except Exception as e:
                    print(f"🔍 TradingView 크롤링 오류: {infomax_code} - {e}")
            
            # TradingView 실패 시 logo.dev 시도
            if not image_data and api_domain:
                print(f"🔍 logo.dev 크롤링 시도: {infomax_code}")
                try:
                    image_data = await self.crawl_logo_dev(infomax_code, api_domain)
                    if image_data:
                        data_source = "logo_dev"
                        logo_hash = hashlib.md5(f"logo_dev_{infomax_code}".encode()).hexdigest()
                        print(f"🔍 logo.dev 크롤링 성공: {infomax_code}")
                    else:
                        print(f"🔍 logo.dev 크롤링 실패: {infomax_code}")
                except Exception as e:
                    print(f"🔍 logo.dev 크롤링 오류: {infomax_code} - {e}")
            
            if not image_data:
                print(f"❌ 모든 크롤링 시도 실패: {infomax_code}")
                return False
            
            # 이미지 변환
            print(f"🔍 이미지 변환 시작: {infomax_code}")
            converted_images = self.convert_image(image_data, infomax_code)
            print(f"🔍 이미지 변환 완료: {infomax_code}")
            
            # MinIO에 저장
            saved_files = []
            print(f"🔍 변환된 이미지 개수: {len(converted_images)}")
            for format_key, img_data in converted_images.items():
                if format_key == "original":
                    # logo_hash 기반 저장으로 통일 (원본 SVG도 logo_hash 키 사용을 위해 infomax_code 해시)
                    logo_hash = hashlib.md5(f"{infomax_code}".encode()).hexdigest()
                    object_key = f"{logo_hash}_original.svg"
                    content_type = "image/svg+xml"
                    is_original = True
                    format_type = "svg"
                    size = None
                else:
                    format_type, size = format_key.split('_')
                    logo_hash = hashlib.md5(f"{infomax_code}".encode()).hexdigest()
                    object_key = f"{logo_hash}_{size}.{format_type.lower()}"
                    content_type = f"image/{format_type.lower()}"
                    is_original = False
                
                print(f"🔍 MinIO 저장 시도: {object_key}")
                if await self.save_to_minio(img_data, object_key, content_type):
                    print(f"✅ MinIO 저장 성공: {object_key}")
                    saved_files.append({
                        'object_key': object_key,
                        'format': format_type.lower(),
                        'dimension_width': int(size) if size else None,
                        'dimension_height': int(size) if size else None,
                        'file_size': len(img_data),
                        'is_original': is_original,
                        'data_source': data_source
                    })
                else:
                    print(f"❌ MinIO 저장 실패: {object_key}")
            
            # 데이터베이스에 저장
            print(f"🔍 saved_files 개수: {len(saved_files)}")
            if not saved_files:
                print(f"❌ 저장할 파일이 없음: {infomax_code}")
                return False
                
            for file_info in saved_files:
                print(f"🔍 파일 저장: {file_info}")
                await self.save_to_database(infomax_code, logo_hash, file_info)
            
            print(f"로고 크롤링 성공: {infomax_code} ({len(saved_files)}개 파일)")
            return True
            
        except Exception as e:
            print(f"로고 크롤링 오류 ({infomax_code}): {e}")
            return False
    
    async def crawl_batch(self, tickers: List[Dict], job_id: str = None) -> str:
        """배치 크롤링 실행"""
        if not job_id:
            job_id = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 진행상황 파일 생성
        progress_file = Path("progress") / f"{job_id}.json"
        progress_file.parent.mkdir(exist_ok=True)
        
        progress_data = {
            "job_id": job_id,
            "status": "running",
            "total": len(tickers),
            "completed": 0,
            "success": 0,
            "failed": 0,
            "current": "",
            "started_at": datetime.now().isoformat(),
            "errors": []
        }
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        try:
            for i, ticker_info in enumerate(tickers):
                infomax_code = ticker_info['infomax_code']
                ticker = ticker_info['ticker']
                api_domain = ticker_info.get('api_domain')
                
                # 진행상황 업데이트
                progress_data['current'] = f"{infomax_code} ({ticker})"
                progress_data['completed'] = i
                
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
                # 크롤링 실행
                success = await self.crawl_logo(infomax_code, ticker, api_domain)
                
                if success:
                    progress_data['success'] += 1
                else:
                    progress_data['failed'] += 1
                    progress_data['errors'].append(f"Failed: {infomax_code}")
            
            # 완료 처리
            progress_data['status'] = "completed"
            progress_data['completed'] = len(tickers)
            progress_data['finished_at'] = datetime.now().isoformat()
            
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            return job_id
            
        except Exception as e:
            progress_data['status'] = "error"
            progress_data['error'] = str(e)
            progress_data['finished_at'] = datetime.now().isoformat()
            
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            raise e

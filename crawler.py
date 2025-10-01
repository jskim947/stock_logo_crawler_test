"""
로고 크롤링 모듈
웹사이트와 logo.dev에서 로고를 수집하는 기능을 제공
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
import logging

logger = logging.getLogger(__name__)

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
        
        # existing_api 인스턴스 생성
        from api_server import existing_api
        self.existing_api = existing_api
        
    async def crawl_website(self, infomax_code: str, ticker: str) -> Optional[bytes]:
        """웹사이트에서 로고 크롤링 (재시도 로직 포함)"""
        max_retries = 3
        base_timeout = 10000  # 10초
        
        for attempt in range(max_retries):
            try:
                logger.info(f"웹사이트 크롤링 시도 {attempt + 1}/{max_retries}: {infomax_code}")
                
                # 시도마다 타임아웃 증가
                timeout = base_timeout + (attempt * 5000)  # 10초, 15초, 20초
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent=self.ua.random
                    )
                    # 페이지 타임아웃 설정
                    context.set_default_timeout(timeout)
                    
                    page = await context.new_page()
                    
                    # 웹사이트 페이지로 이동
                    base_url = os.getenv('WEBSITE_BASE_URL', 'https://example.com')
                    url = f"{base_url}/symbols/{ticker}/news"
                    print(f"🔍 웹사이트 URL: {url} (타임아웃: {timeout}ms)")
                    await page.goto(url, timeout=timeout)
                    
                    # 로고 이미지 선택자 (여러 가능성 시도)
                    selectors = [
                        'img[data-testid="logo"]',
                        '.tv-symbol-header__logo img',
                        '.tv-symbol-header__logo svg',
                        '#js-category-content > div.js-symbol-page-header-root > div > div.symbolRow-NopKb87z > div > div.container-F4HZNWkx.logo-iJMmXWiA > img.logo-PsAlMQQF.xxxlarge-PsAlMQQF.large-F4HZNWkx.letter-PsAlMQQF',
                        'img[alt*="logo" i]',
                        'img[src*="logo" i]',
                        '.tv-symbol-header img',
                        'header img'
                    ]
                    
                    # XPath 셀렉터 추가 (img 태그를 찾아서 src에서 SVG URL 추출)
                    xpath_selectors = [
                        # 원래 XPath들 (더 유연하게 수정)
                        '/html/body/div[2]/main/div[2]/div[1]/div/div[1]/div/div[1]/img[1]',
                        '/html/body/div[2]/main/div[2]/div[1]/div/div[1]/div/div[1]/img[2]',
                        '/html/body/div[2]/main/div[2]/div[1]/div/div[1]/div/div[1]/img[3]',
                        # 더 유연한 XPath들
                        '//div[contains(@class, "symbolRow")]//img[1]',
                        '//div[contains(@class, "symbolRow")]//img[2]',
                        '//div[contains(@class, "symbolRow")]//img[3]',
                        '//div[contains(@class, "logo")]//img[1]',
                        '//div[contains(@class, "logo")]//img[2]',
                        '//div[contains(@class, "logo")]//img[3]',
                        # 일반적인 img 태그들
                        '//img[contains(@class, "logo")]',
                        '//img[contains(@src, "svg")]'
                    ]
                    
                    # XPath 셀렉터 우선 시도
                    for xpath in xpath_selectors:
                        try:
                            element = await page.wait_for_selector(f"xpath={xpath}", timeout=3000, state="attached")
                            if element:
                                # SVG인 경우
                                if 'svg' in xpath:
                                    svg_content = await element.inner_html()
                                    await browser.close()
                                    print(f"✅ SVG 크롤링 성공 (XPath): {infomax_code}")
                                    return svg_content.encode('utf-8')
                                # IMG인 경우
                                else:
                                    src = await element.get_attribute('src')
                                    print(f"🔍 XPath IMG src 발견: {src}")
                                    if src:
                                        # 국기 이미지 제외 (country/로 시작하고 .svg로 끝나는 경우)
                                        if 'country/' in src and src.endswith('.svg'):
                                            print(f"🔍 국기 이미지 제외: {src}")
                                            await browser.close()
                                            return None  # logo.dev로 폴백
                                        
                                        # 상대 경로인 경우 절대 경로로 변환
                                        if not src.startswith('http'):
                                            base_url = os.getenv('WEBSITE_BASE_URL', 'https://example.com')
                                            src = f"{base_url}{src}" if src.startswith('/') else f"{base_url}/{src}"
                                        
                                        print(f"🔍 최종 URL: {src}")
                                        timeout_http = aiohttp.ClientTimeout(total=10)  # 10초 타임아웃
                                        async with aiohttp.ClientSession(timeout=timeout_http) as session:
                                            async with session.get(src) as response:
                                                if response.status == 200:
                                                    data = await response.read()
                                                    await browser.close()
                                                    print(f"✅ IMG 크롤링 성공 (XPath): {infomax_code}, 크기: {len(data)} bytes")
                                                    return data
                                                else:
                                                    print(f"🔍 HTTP 응답 실패: {response.status}")
                                    else:
                                        print(f"🔍 XPath IMG src 없음: {xpath}")
                                        continue
                        except Exception as e:
                            print(f"🔍 XPath 셀렉터 실패: {xpath} - {e}")
                            continue
                    
                    # CSS 셀렉터 시도 (XPath 실패 시)
                    for selector in selectors:
                        try:
                            element = await page.wait_for_selector(selector, timeout=3000, state="attached")  # 3초로 단축
                            if element:
                                # SVG인 경우
                                if 'svg' in selector:
                                    svg_content = await element.inner_html()
                                    await browser.close()
                                    print(f"✅ SVG 크롤링 성공 (CSS): {infomax_code}")
                                    return svg_content.encode('utf-8')
                                # IMG인 경우
                                else:
                                    src = await element.get_attribute('src')
                                    print(f"🔍 CSS IMG src 발견: {src}")
                                    if src:
                                        # 국기 이미지 제외 (country/로 시작하고 .svg로 끝나는 경우)
                                        if 'country/' in src and src.endswith('.svg'):
                                            print(f"🔍 국기 이미지 제외: {src}")
                                            await browser.close()
                                            return None  # logo.dev로 폴백
                                        
                                        # 상대 경로인 경우 절대 경로로 변환
                                        if not src.startswith('http'):
                                            base_url = os.getenv('WEBSITE_BASE_URL', 'https://example.com')
                                            src = f"{base_url}{src}" if src.startswith('/') else f"{base_url}/{src}"
                                        
                                        print(f"🔍 최종 URL: {src}")
                                        timeout_http = aiohttp.ClientTimeout(total=10)  # 10초 타임아웃
                                        async with aiohttp.ClientSession(timeout=timeout_http) as session:
                                            async with session.get(src) as response:
                                                if response.status == 200:
                                                    data = await response.read()
                                                    await browser.close()
                                                    print(f"✅ IMG 크롤링 성공 (CSS): {infomax_code}, 크기: {len(data)} bytes")
                                                    return data
                                                else:
                                                    print(f"🔍 HTTP 응답 실패: {response.status}")
                        except Exception as e:
                            print(f"🔍 CSS 셀렉터 실패: {selector} - {e}")
                            continue
                    
                    await browser.close()
                    print(f"❌ 모든 셀렉터 실패: {infomax_code}")
                    if attempt < max_retries - 1:
                        print(f"🔄 재시도 예정: {infomax_code}")
                        continue
                    return None
                    
            except Exception as e:
                print(f"웹사이트 크롤링 오류 ({infomax_code}, 시도 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print(f"🔄 재시도 예정: {infomax_code}")
                    continue
                return None
        
        return None
    
    async def crawl_logo_dev(self, infomax_code: str, api_domain: str) -> Optional[bytes]:
        """logo.dev API에서 로고 크롤링"""
        print(f"🔍 logo.dev 크롤링 시작: {infomax_code}, api_domain: {api_domain}")
        try:
            if not self.logo_dev_token:
                print("❌ LOGO_DEV_TOKEN이 설정되지 않았습니다")
                return None
            
            print(f"🔍 logo.dev 토큰 확인: {self.logo_dev_token[:10]}...")
            
            # API 쿼터 확인
            if not await self._check_quota('logo_dev'):
                print("logo.dev 일일 쿼터 초과")
                return None
            
            url = f"https://img.logo.dev/{api_domain}?token={self.logo_dev_token}&format=png&size=300&fallback=404"
            print(f"🔍 logo.dev API URL: {url}")
            
            timeout = aiohttp.ClientTimeout(total=15)  # 15초 타임아웃
            async with aiohttp.ClientSession(timeout=timeout) as session:
                print(f"🔍 logo.dev API 호출 시작: {api_domain}")
                async with session.get(url) as response:
                    print(f"🔍 logo.dev API 응답: {response.status}")
                    if response.status == 200:
                        data = await response.read()
                        print(f"✅ logo.dev 크롤링 성공: {infomax_code}, 크기: {len(data)} bytes")
                        # 쿼터 사용량 업데이트
                        await self._update_quota('logo_dev')
                        return data
                    else:
                        print(f"❌ logo.dev API 오류: {response.status}")
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
        """이미지를 다양한 크기로 변환 (SVG → PNG/WebP 포함)"""
        print(f"🔍 convert_image 함수 진입: {infomax_code}")
        try:
            results = {}
            image = None
            
            # SVG인 경우 PNG/WebP로 변환
            print(f"🔍 이미지 데이터 확인: {infomax_code}, 시작 바이트: {image_data[:50]}")
            if image_data.startswith(b'<svg') or image_data.startswith(b'<?xml'):
                print(f"🔍 SVG 파일 감지: {infomax_code}")
                
                # SVG를 PIL Image로 변환하기 위해 cairosvg 사용 시도
                try:
                    import cairosvg
                    # SVG를 PNG로 변환
                    png_data = cairosvg.svg2png(bytestring=image_data)
                    print(f"🔍 SVG → PNG 변환 완료: {infomax_code} ({len(png_data)} bytes)")
                    
                    # PNG 데이터를 PIL Image로 열기
                    png_buffer = BytesIO(png_data)
                    image = Image.open(png_buffer)
                    print(f"✅ SVG → PNG → PIL Image 변환 성공: {infomax_code}, 크기: {image.size}")
                except ImportError:
                    print("❌ cairosvg가 설치되지 않음. SVG 원본만 저장")
                    return {"original": image_data}
                except Exception as e:
                    print(f"❌ SVG 변환 실패: {e}")
                    print(f"🔍 PNG 데이터 확인: {png_data[:50] if 'png_data' in locals() else 'None'}")
                    return {"original": image_data}
            else:
                # 일반 이미지 파일
                print(f"🔍 일반 이미지 파일 감지: {infomax_code}")
                image_buffer = BytesIO(image_data)
                image = Image.open(image_buffer)
            
            # image가 None이면 변환 실패
            if image is None:
                print(f"❌ 이미지 변환 실패: {infomax_code}")
                return {"original": image_data}
            
            print(f"🔍 이미지 변환 시작: {infomax_code}, 크기: {image.size}")
            
            # 표준 사이즈로 변환 (환경변수 IMAGE_SIZES 사용, 기본 240,300)
            sizes_env = os.getenv('IMAGE_SIZES', '240,300')
            try:
                sizes = [int(s.strip()) for s in sizes_env.split(',') if s.strip()]
            except Exception:
                sizes = [240, 300]
            
            formats = ['PNG', 'WebP']
            
            # 원본도 저장 (SVG인 경우)
            if image_data.startswith(b'<svg') or image_data.startswith(b'<?xml'):
                results["original"] = image_data
            
            for size in sizes:
                for format_type in formats:
                    try:
                        # 리사이즈
                        resized = image.resize((size, size), Image.Resampling.LANCZOS)
                        
                        # 바이트로 변환
                        output = BytesIO()
                        if format_type == 'PNG':
                            resized.save(output, format='PNG', optimize=True)
                        else:  # WebP
                            resized.save(output, format='WebP', quality=85, optimize=True)
                        
                        converted_data = output.getvalue()
                        results[f"{format_type.lower()}_{size}"] = converted_data
                        print(f"✅ 이미지 변환 완료: {format_type.lower()}_{size}px ({len(converted_data)} bytes)")
                        
                    except Exception as e:
                        print(f"❌ 이미지 변환 실패 ({format_type}_{size}px): {e}")
                        continue
            
            logger.info(f"이미지 변환 완료: {infomax_code}, {len(results)}개 파일")
            return results
            
        except Exception as e:
            logger.error(f"이미지 변환 오류 ({infomax_code}): {e}")
            # 변환 실패해도 원본은 저장
            result = {"original": image_data}
            logger.info(f"변환 실패로 원본만 반환: {len(result)}개")
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
        """데이터베이스에 로고 정보 저장 (직접 API 호출)"""
        print(f"🔍 DB 저장 시작: {infomax_code}, {logo_hash}")
        print(f"🔍 file_info: {file_info}")
        try:
            # 직접 기존 API 호출
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                
                # 1. logos 테이블 확인/생성
                logo_url = f"{self.existing_api_base}/api/schemas/raw_data/tables/logos/query"
                logo_params = {
                    "search_column": "logo_hash",
                    "search": logo_hash,
                    "limit": 1
                }
                
                async with session.get(logo_url, params=logo_params) as response:
                    if response.status == 200:
                        logo_data = await response.json()
                        if logo_data and 'data' in logo_data and logo_data['data']:
                            logo_id = logo_data['data'][0]['logo_id']
                            print(f"✅ 기존 logos 데이터 사용: logo_id={logo_id}")
                        else:
                            # 새로 생성
                            logo_upsert_url = f"{self.existing_api_base}/api/schemas/raw_data/tables/logos/upsert"
                            logo_upsert_data = {
                                "data": {
                                    "logo_hash": logo_hash,
                                    "is_deleted": False
                                },
                                "conflict_columns": ["logo_hash"]
                            }
                            
                            async with session.post(logo_upsert_url, json=logo_upsert_data) as upsert_response:
                                if upsert_response.status == 200:
                                    upsert_data = await upsert_response.json()
                                    logo_id = upsert_data['data']['logo_id']
                                    print(f"✅ logos 테이블 저장 성공: logo_id={logo_id}")
                                else:
                                    print(f"❌ logos 테이블 저장 실패: {upsert_response.status}")
                                    return False
                    else:
                        print(f"❌ logos 테이블 조회 실패: {response.status}")
                        return False
                
                # 2. logo_files 테이블 저장
                file_url = f"{self.existing_api_base}/api/schemas/raw_data/tables/logo_files/upsert"
                file_data = {
                    "data": {
                        "logo_id": logo_id,
                        "file_format": file_info['format'],
                        "dimension_width": file_info['dimension_width'],
                        "dimension_height": file_info['dimension_height'],
                        "file_size": file_info['file_size'],
                        "minio_object_key": file_info['object_key'],
                        "data_source": file_info['data_source'],
                        "upload_type": "crawled",
                        "is_original": file_info.get('is_original', True)
                    },
                    "conflict_columns": ["minio_object_key"]
                }
                
                print(f"🔍 logo_files 저장 데이터: {file_data}")
                
                async with session.post(file_url, json=file_data) as file_response:
                    if file_response.status == 200:
                        print(f"✅ logo_files 테이블 저장 성공: logo_id={logo_id}")
                        print(f"✅ DB 저장 완료: {infomax_code}")
                        return True
                    else:
                        error_text = await file_response.text()
                        print(f"❌ logo_files 테이블 저장 실패: {file_response.status}")
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
            
            # 타임아웃 설정 (30초)
            import asyncio
            try:
                print(f"🔍 _crawl_logo_internal 호출 전: {infomax_code}")
                print(f"🔍 asyncio.wait_for 시작: {infomax_code}")
                result = await asyncio.wait_for(
                    self._crawl_logo_internal(infomax_code, ticker, api_domain),
                    timeout=30.0
                )
                print(f"🔍 _crawl_logo_internal 호출 후: {infomax_code}, 결과: {result}")
                print(f"🔍🔍🔍 CRAWL_LOGO 함수 완료: {infomax_code}, 결과: {result}")
                return result
            except asyncio.TimeoutError:
                print(f"🔍 크롤링 타임아웃: {infomax_code}")
                return False
            except Exception as e:
                print(f"🔍 asyncio.wait_for 오류: {infomax_code} - {e}")
                import traceback
                print(f"🔍 asyncio 오류 상세: {traceback.format_exc()}")
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
            
            # 웹사이트에서 크롤링 시도 (ticker가 있을 때만)
            if ticker and ticker.strip():
                print(f"🔍 웹사이트 크롤링 시도: {infomax_code}")
                try:
                    image_data = await self.crawl_website(infomax_code, ticker)
                    print(f"🔍 crawl_website 반환값 확인: {infomax_code}, 타입: {type(image_data)}, 길이: {len(image_data) if image_data else 'None'}")
                    if image_data:
                        data_source = "website"
                        logo_hash = hashlib.md5(f"website_{infomax_code}".encode()).hexdigest()
                        print(f"🔍 웹사이트 크롤링 성공: {infomax_code}")
                    else:
                        print(f"🔍 웹사이트 크롤링 실패: {infomax_code}")
                except Exception as e:
                    print(f"🔍 웹사이트 크롤링 오류: {infomax_code} - {e}")
            
            # 웹사이트 실패 시 logo.dev 시도
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
            try:
                converted_images = self.convert_image(image_data, infomax_code)
                print(f"🔍 이미지 변환 완료: {infomax_code}")
            except Exception as e:
                print(f"❌ 이미지 변환 중 오류: {infomax_code} - {e}")
                converted_images = {"original": image_data}
            
            # master에서 logo_hash 조회
            print(f"🔍 master에서 logo_hash 조회: {infomax_code}")
            try:
                master_result = self.existing_api.query_table("raw_data", "logo_master", {
                    "search_column": "infomax_code",
                    "search": infomax_code,
                    "limit": 1
                })
                print(f"🔍 master 조회 결과: {master_result}")
                
                if master_result and 'data' in master_result and master_result['data']:
                    logo_hash = master_result['data'][0]['logo_hash']
                    print(f"🔍 master logo_hash 조회 성공: {logo_hash}")
                else:
                    print(f"❌ master logo_hash 조회 실패: {infomax_code}")
                    return False
            except Exception as e:
                print(f"❌ master 조회 오류: {e}")
                return False
            
            # MinIO에 저장
            saved_files = []
            print(f"🔍 변환된 이미지 개수: {len(converted_images)}")
            for format_key, img_data in converted_images.items():
                if format_key == "original":
                    # master의 logo_hash 사용
                    object_key = f"{logo_hash}_original.svg"
                    content_type = "image/svg+xml"
                    is_original = True
                    format_type = "svg"
                    size = None
                else:
                    format_type, size = format_key.split('_')
                    # master의 logo_hash 사용
                    object_key = f"{logo_hash}_{size}.{format_type.lower()}"
                    content_type = f"image/{format_type.lower()}"
                    is_original = False
                
                print(f"🔍 MinIO 저장 시도: {object_key}, 크기: {len(img_data)} bytes")
                if await self.save_to_minio(img_data, object_key, content_type):
                    print(f"✅ MinIO 저장 성공: {object_key}")
                    file_info = {
                        'object_key': object_key,
                        'format': format_type.lower(),
                        'dimension_width': int(size) if size else None,
                        'dimension_height': int(size) if size else None,
                        'file_size': len(img_data),
                        'is_original': is_original,
                        'data_source': data_source
                    }
                    saved_files.append(file_info)
                    print(f"🔍 파일 정보 추가: {file_info}")
                else:
                    print(f"❌ MinIO 저장 실패: {object_key}")
            
            # 데이터베이스에 저장
            print(f"🔍 saved_files 개수: {len(saved_files)}")
            if not saved_files:
                print(f"❌ 저장할 파일이 없음: {infomax_code}")
                return False
                
            for file_info in saved_files:
                print(f"🔍 파일 저장: {file_info}")
                # DB 저장은 API 서버에서 처리하도록 함
                print(f"✅ 파일 저장 완료 (DB는 별도 처리): {infomax_code}")
                # DB 저장 비활성화 - API 서버에서 처리
                # save_to_database 함수 호출 완전 제거
            
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

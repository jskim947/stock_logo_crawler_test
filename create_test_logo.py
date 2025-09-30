#!/usr/bin/env python3
"""
테스트용 로고 파일 생성 및 업로드
- 간단한 테스트 이미지 생성
- MinIO에 업로드
- 로고 조회 테스트
"""

import requests
import json
from PIL import Image
import io
import base64

def create_test_logo():
    """테스트용 로고 이미지 생성"""
    
    # 간단한 테스트 이미지 생성 (240x240 PNG)
    img = Image.new('RGB', (240, 240), color='lightblue')
    
    # 텍스트 추가 (PIL의 기본 기능으로)
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    # 기본 폰트 사용
    try:
        font = ImageFont.load_default()
    except:
        font = None
    
    # 텍스트 그리기
    text = "TEST LOGO"
    if font:
        draw.text((120, 120), text, fill='darkblue', font=font, anchor='mm')
    else:
        draw.text((120, 120), text, fill='darkblue', anchor='mm')
    
    # PNG로 변환
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_data = img_buffer.getvalue()
    
    print(f"✅ 테스트 로고 생성: {len(img_data)} bytes")
    return img_data

def upload_test_logo():
    """테스트 로고 업로드"""
    
    base_url = "http://localhost:8005"
    
    print("🔍 테스트 로고 업로드")
    print("=" * 50)
    
    # 1. 테스트 이미지 생성
    print("1️⃣ 테스트 이미지 생성...")
    img_data = create_test_logo()
    
    # 2. 업로드할 종목 선택 (AMX:AAA 사용)
    infomax_code = "AMX:AAA"
    print(f"2️⃣ '{infomax_code}' 종목에 로고 업로드...")
    
    # 3. 파일 업로드
    try:
        files = {
            'file': ('test_logo.png', img_data, 'image/png')
        }
        data = {
            'infomax_code': infomax_code,
            'format': 'png',
            'size': '240',
            'data_source': 'manual'
        }
        
        response = requests.post(f"{base_url}/api/v1/logos/upload", 
                              files=files, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 업로드 성공")
            print(f"   📊 상태: {result.get('status')}")
            print(f"   📊 메시지: {result.get('message')}")
            print(f"   📊 MinIO 키: {result.get('data', {}).get('minio_key')}")
            return True
        else:
            print(f"   ❌ 업로드 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ 업로드 오류: {e}")
        return False

def test_uploaded_logo():
    """업로드된 로고 테스트"""
    
    base_url = "http://localhost:8005"
    infomax_code = "AMX:AAA"
    
    print(f"\n3️⃣ 업로드된 로고 테스트 ('{infomax_code}')...")
    
    # 다양한 크기로 테스트
    test_sizes = [240, 300]
    
    for size in test_sizes:
        try:
            print(f"   {size}px 조회...")
            response = requests.get(f"{base_url}/api/v1/logos/{infomax_code}", 
                                  params={"format": "png", "size": size}, timeout=10)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"      ✅ 성공: {content_type}, {content_length} bytes")
            else:
                print(f"      ❌ 실패: {response.status_code}")
        except Exception as e:
            print(f"      ❌ 오류: {e}")

if __name__ == "__main__":
    success = upload_test_logo()
    if success:
        test_uploaded_logo()
    
    print("\n" + "=" * 50)
    print("🎯 테스트 로고 업로드 완료!")
    print("=" * 50)

#!/usr/bin/env python3
"""
MinIO 직접 테스트
- MinIO 클라이언트 직접 사용
- 파일 업로드/다운로드 테스트
"""

from minio import Minio
import io
from PIL import Image

def test_minio_direct():
    """MinIO 직접 테스트"""
    
    print("🔍 MinIO 직접 테스트")
    print("=" * 50)
    
    # MinIO 클라이언트 설정
    minio_client = Minio(
        'localhost:9000',  # MinIO 서버 주소
        access_key='minioadmin',
        secret_key='minioadmin123',
        secure=False
    )
    
    bucket_name = 'logos'
    
    try:
        # 1. 버킷 존재 확인
        print("1️⃣ 버킷 존재 확인...")
        if minio_client.bucket_exists(bucket_name):
            print(f"   ✅ 버킷 '{bucket_name}' 존재")
        else:
            print(f"   ❌ 버킷 '{bucket_name}' 없음")
            return
        
        # 2. 버킷 내용 확인
        print("\n2️⃣ 버킷 내용 확인...")
        objects = list(minio_client.list_objects(bucket_name))
        print(f"   📊 총 객체 수: {len(objects)}개")
        
        for i, obj in enumerate(objects[:5]):  # 처음 5개만
            print(f"   {i+1}. {obj.object_name} ({obj.size} bytes)")
        
        # 3. 테스트 이미지 생성 및 업로드
        print("\n3️⃣ 테스트 이미지 생성 및 업로드...")
        
        # 간단한 테스트 이미지 생성
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_data = img_buffer.getvalue()
        
        # MinIO에 업로드
        test_key = 'test_logo.png'
        minio_client.put_object(
            bucket_name,
            test_key,
            io.BytesIO(img_data),
            length=len(img_data),
            content_type='image/png'
        )
        print(f"   ✅ 테스트 이미지 업로드: {test_key}")
        
        # 4. 업로드된 파일 다운로드 테스트
        print("\n4️⃣ 업로드된 파일 다운로드 테스트...")
        try:
            obj = minio_client.get_object(bucket_name, test_key)
            downloaded_data = obj.read()
            obj.close()
            obj.release_conn()
            print(f"   ✅ 다운로드 성공: {len(downloaded_data)} bytes")
        except Exception as e:
            print(f"   ❌ 다운로드 실패: {e}")
        
        # 5. 기존 로고 파일들 확인
        print("\n5️⃣ 기존 로고 파일들 확인...")
        logo_objects = list(minio_client.list_objects(bucket_name, prefix='8485b1610697af8af71a8d8163c225e7'))
        print(f"   📊 로고 해시로 검색: {len(logo_objects)}개")
        
        for obj in logo_objects:
            print(f"   - {obj.object_name} ({obj.size} bytes)")
        
    except Exception as e:
        print(f"❌ MinIO 테스트 오류: {e}")

if __name__ == "__main__":
    test_minio_direct()
    
    print("\n" + "=" * 50)
    print("🎯 MinIO 직접 테스트 완료!")
    print("=" * 50)

#!/usr/bin/env python3
"""
MinIO 파일 정리 스크립트
- original 폴더의 콜론 포함 파일명을 logo_hash 기반으로 변경
- 폴더 없이 저장된 파일들을 정리
- 데이터베이스와 동기화
"""

import hashlib
import requests
from minio import Minio
import os

# MinIO 클라이언트 설정
minio_client = Minio(
    'minio:9000',
    access_key='minioadmin',
    secret_key='minioadmin123',
    secure=False
)

bucket_name = 'logos'
BASE_URL = "http://localhost:8005"

def generate_logo_hash(infomax_code: str) -> str:
    """infomax_code로부터 logo_hash 생성"""
    return hashlib.md5(infomax_code.encode('utf-8')).hexdigest()

def get_infomax_code_from_filename(filename: str) -> str:
    """파일명에서 infomax_code 추출"""
    # original/AMX:AAA.svg -> AMX:AAA
    if filename.startswith('original/'):
        return filename[9:].replace('.svg', '').replace('.png', '').replace('.webp', '')
    return None

def cleanup_original_files():
    """original 폴더의 콜론 포함 파일들을 정리"""
    print("🔧 original 폴더 파일 정리 시작...")
    
    try:
        # original 폴더의 파일들 조회
        objects = list(minio_client.list_objects(bucket_name, prefix='original/', recursive=True))
        
        for obj in objects:
            old_name = obj.object_name
            infomax_code = get_infomax_code_from_filename(old_name)
            
            if infomax_code and ':' in infomax_code:
                # logo_hash 생성
                logo_hash = generate_logo_hash(infomax_code)
                
                # 새 파일명 생성
                file_extension = old_name.split('.')[-1]
                new_name = f"{logo_hash}_original.{file_extension}"
                
                print(f"   {old_name} -> {new_name}")
                
                # 파일 복사
                try:
                    # 원본 파일 다운로드
                    response = minio_client.get_object(bucket_name, old_name)
                    file_data = response.read()
                    response.close()
                    response.release_conn()
                    
                    # 새 위치에 업로드
                    from io import BytesIO
                    minio_client.put_object(
                        bucket_name,
                        new_name,
                        BytesIO(file_data),
                        length=len(file_data),
                        content_type=f"image/{file_extension}"
                    )
                    
                    # 원본 파일 삭제
                    minio_client.remove_object(bucket_name, old_name)
                    
                    print(f"   ✅ {infomax_code} -> {logo_hash} 변환 완료")
                    
                except Exception as e:
                    print(f"   ❌ {infomax_code} 변환 실패: {e}")
        
        print("✅ original 폴더 정리 완료")
        
    except Exception as e:
        print(f"❌ original 폴더 정리 실패: {e}")

def cleanup_orphaned_files():
    """폴더 없이 저장된 파일들을 정리"""
    print("\\n🔧 고아 파일 정리 시작...")
    
    try:
        # 폴더 없이 저장된 파일들 조회
        objects = list(minio_client.list_objects(bucket_name, recursive=True))
        orphaned_files = []
        
        for obj in objects:
            if '/' not in obj.object_name and obj.object_name.endswith(('.png', '.svg', '.webp')):
                orphaned_files.append(obj.object_name)
        
        print(f"   발견된 고아 파일: {len(orphaned_files)}개")
        
        for filename in orphaned_files:
            print(f"   삭제: {filename}")
            try:
                minio_client.remove_object(bucket_name, filename)
                print(f"   ✅ {filename} 삭제 완료")
            except Exception as e:
                print(f"   ❌ {filename} 삭제 실패: {e}")
        
        print("✅ 고아 파일 정리 완료")
        
    except Exception as e:
        print(f"❌ 고아 파일 정리 실패: {e}")

def sync_with_database():
    """데이터베이스와 동기화"""
    print("\\n🔧 데이터베이스 동기화 시작...")
    
    try:
        # 현재 MinIO의 파일들 조회
        objects = list(minio_client.list_objects(bucket_name, recursive=True))
        file_info = []
        
        for obj in objects:
            if obj.object_name.endswith(('.png', '.svg', '.webp')):
                # logo_hash 추출
                if '_' in obj.object_name:
                    logo_hash = obj.object_name.split('_')[0]
                    file_extension = obj.object_name.split('.')[-1]
                    
                    file_info.append({
                        'logo_hash': logo_hash,
                        'filename': obj.object_name,
                        'extension': file_extension,
                        'size': obj.size
                    })
        
        print(f"   MinIO 파일 정보: {len(file_info)}개")
        
        # 각 파일에 대해 데이터베이스 확인
        for info in file_info:
            try:
                # API를 통해 로고 정보 조회
                response = requests.get(f"{BASE_URL}/api/v1/logos/search?logo_hash={info['logo_hash']}", timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('data'):
                        print(f"   ✅ {info['filename']} - DB에 존재")
                    else:
                        print(f"   ⚠️  {info['filename']} - DB에 없음")
                else:
                    print(f"   ❌ {info['filename']} - DB 조회 실패")
                    
            except Exception as e:
                print(f"   ❌ {info['filename']} - DB 조회 오류: {e}")
        
        print("✅ 데이터베이스 동기화 완료")
        
    except Exception as e:
        print(f"❌ 데이터베이스 동기화 실패: {e}")

def main():
    """메인 함수"""
    print("🚀 MinIO 파일 정리 시작\\n")
    
    # 1. original 폴더 정리
    cleanup_original_files()
    
    # 2. 고아 파일 정리
    cleanup_orphaned_files()
    
    # 3. 데이터베이스 동기화
    sync_with_database()
    
    print("\\n🎉 MinIO 파일 정리 완료!")

if __name__ == "__main__":
    main()

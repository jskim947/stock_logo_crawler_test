#!/usr/bin/env python3
"""
진행상황 파일 관리 유틸리티
- JSON 스키마 검증
- 오래된 파일 청소
- 진행상황 통계 생성
"""

import json
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import argparse

@dataclass
class ProgressStats:
    """진행상황 통계"""
    total_jobs: int
    completed_jobs: int
    running_jobs: int
    failed_jobs: int
    total_items: int
    completed_items: int
    success_items: int
    failed_items: int
    oldest_job: Optional[str]
    newest_job: Optional[str]

class ProgressManager:
    """진행상황 파일 관리자"""
    
    def __init__(self, progress_dir: str = "progress"):
        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(exist_ok=True)
        
    def validate_schema(self, file_path: Path) -> bool:
        """JSON 스키마 검증"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 필수 필드 검증
            required_fields = [
                'job_id', 'status', 'total', 'completed', 
                'success', 'failed', 'started_at'
            ]
            
            for field in required_fields:
                if field not in data:
                    print(f"❌ {file_path.name}: 필수 필드 '{field}' 누락")
                    return False
            
            # 타입 검증
            if not isinstance(data['total'], int) or data['total'] < 0:
                print(f"❌ {file_path.name}: 'total'은 0 이상의 정수여야 함")
                return False
                
            if not isinstance(data['completed'], int) or data['completed'] < 0:
                print(f"❌ {file_path.name}: 'completed'는 0 이상의 정수여야 함")
                return False
                
            if data['completed'] > data['total']:
                print(f"❌ {file_path.name}: 'completed'가 'total'보다 큼")
                return False
            
            # 상태 값 검증
            valid_statuses = ['running', 'completed', 'failed', 'cancelled']
            if data['status'] not in valid_statuses:
                print(f"❌ {file_path.name}: 'status'는 {valid_statuses} 중 하나여야 함")
                return False
            
            # 날짜 형식 검증
            try:
                datetime.fromisoformat(data['started_at'])
            except ValueError:
                print(f"❌ {file_path.name}: 'started_at' 날짜 형식 오류")
                return False
                
            if 'finished_at' in data and data['finished_at']:
                try:
                    datetime.fromisoformat(data['finished_at'])
                except ValueError:
                    print(f"❌ {file_path.name}: 'finished_at' 날짜 형식 오류")
                    return False
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ {file_path.name}: JSON 파싱 오류 - {e}")
            return False
        except Exception as e:
            print(f"❌ {file_path.name}: 검증 오류 - {e}")
            return False
    
    def get_all_progress_files(self) -> List[Path]:
        """모든 진행상황 파일 목록 반환"""
        crawl_files = list(self.progress_dir.glob("crawl_*.json"))
        missing_files = list(self.progress_dir.glob("missing_*.json"))
        return sorted(crawl_files + missing_files)
    
    def validate_all_files(self) -> Dict[str, bool]:
        """모든 파일 스키마 검증"""
        files = self.get_all_progress_files()
        results = {}
        
        print(f"🔍 {len(files)}개 파일 스키마 검증 중...")
        
        for file_path in files:
            results[file_path.name] = self.validate_schema(file_path)
        
        valid_count = sum(results.values())
        print(f"✅ {valid_count}/{len(files)} 파일 검증 통과")
        
        return results
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """오래된 파일 청소 (기본 30일)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        files = self.get_all_progress_files()
        removed_count = 0
        
        print(f"🧹 {days}일 이전 파일 청소 중...")
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                started_at = datetime.fromisoformat(data['started_at'])
                
                if started_at < cutoff_date:
                    file_path.unlink()
                    removed_count += 1
                    print(f"🗑️  삭제: {file_path.name} ({started_at.strftime('%Y-%m-%d %H:%M')})")
                    
            except Exception as e:
                print(f"❌ {file_path.name} 처리 오류: {e}")
        
        print(f"✅ {removed_count}개 파일 삭제 완료")
        return removed_count
    
    def get_statistics(self) -> ProgressStats:
        """진행상황 통계 생성"""
        files = self.get_all_progress_files()
        
        total_jobs = len(files)
        completed_jobs = 0
        running_jobs = 0
        failed_jobs = 0
        total_items = 0
        completed_items = 0
        success_items = 0
        failed_items = 0
        
        job_dates = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 작업 상태 카운트
                if data['status'] == 'completed':
                    completed_jobs += 1
                elif data['status'] == 'running':
                    running_jobs += 1
                elif data['status'] in ['failed', 'cancelled']:
                    failed_jobs += 1
                
                # 아이템 카운트
                total_items += data['total']
                completed_items += data['completed']
                success_items += data['success']
                failed_items += data['failed']
                
                # 날짜 수집
                started_at = datetime.fromisoformat(data['started_at'])
                job_dates.append((file_path.name, started_at))
                
            except Exception as e:
                print(f"❌ {file_path.name} 통계 생성 오류: {e}")
        
        # 날짜 정렬
        job_dates.sort(key=lambda x: x[1])
        oldest_job = job_dates[0][0] if job_dates else None
        newest_job = job_dates[-1][0] if job_dates else None
        
        return ProgressStats(
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            running_jobs=running_jobs,
            failed_jobs=failed_jobs,
            total_items=total_items,
            completed_items=completed_items,
            success_items=success_items,
            failed_items=failed_items,
            oldest_job=oldest_job,
            newest_job=newest_job
        )
    
    def print_statistics(self):
        """통계 출력"""
        stats = self.get_statistics()
        
        print("\n📊 진행상황 통계")
        print("=" * 50)
        print(f"총 작업 수: {stats.total_jobs}")
        print(f"  - 완료: {stats.completed_jobs}")
        print(f"  - 실행중: {stats.running_jobs}")
        print(f"  - 실패: {stats.failed_jobs}")
        print()
        print(f"총 아이템 수: {stats.total_items}")
        print(f"  - 완료: {stats.completed_items}")
        print(f"  - 성공: {stats.success_items}")
        print(f"  - 실패: {stats.failed_items}")
        print()
        if stats.oldest_job:
            print(f"가장 오래된 작업: {stats.oldest_job}")
        if stats.newest_job:
            print(f"가장 최근 작업: {stats.newest_job}")
        print("=" * 50)

def main():
    parser = argparse.ArgumentParser(description="진행상황 파일 관리 유틸리티")
    parser.add_argument("--dir", default="progress", help="진행상황 파일 디렉토리 (기본: progress)")
    parser.add_argument("--validate", action="store_true", help="스키마 검증 실행")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="N일 이전 파일 청소")
    parser.add_argument("--stats", action="store_true", help="통계 출력")
    
    args = parser.parse_args()
    
    manager = ProgressManager(args.dir)
    
    if args.validate:
        manager.validate_all_files()
    
    if args.cleanup:
        manager.cleanup_old_files(args.cleanup)
    
    if args.stats:
        manager.print_statistics()
    
    if not any([args.validate, args.cleanup, args.stats]):
        # 기본: 검증 + 통계
        manager.validate_all_files()
        manager.print_statistics()

if __name__ == "__main__":
    main()

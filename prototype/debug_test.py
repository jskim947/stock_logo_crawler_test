#!/usr/bin/env python3
"""
디버깅용 간단한 테스트 스크립트
"""

import sys

def main():
    print(f"Arguments: {sys.argv}")
    print(f"Length: {len(sys.argv)}")
    
    if len(sys.argv) > 1:
        print(f"Individual test: {sys.argv[1]}")
    else:
        print("All tests")

if __name__ == "__main__":
    main()

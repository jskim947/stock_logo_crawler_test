import sys
import requests


def main():
    if len(sys.argv) < 4:
        print("usage: python scripts/query_db.py <schema> <table> <querystring>")
        print("example: python scripts/query_db.py raw_data logos 'page=1&search_column=logo_hash&search=abcd' ")
        sys.exit(1)

    schema = sys.argv[1]
    table = sys.argv[2]
    query = sys.argv[3]

    base = "http://10.150.2.150:8004"
    url = f"{base}/api/schemas/{schema}/tables/{table}/query?{query}"
    try:
        r = requests.get(url, timeout=20)
        print("status:", r.status_code)
        print(r.text)
    except Exception as e:
        print("error:", e)


if __name__ == "__main__":
    main()



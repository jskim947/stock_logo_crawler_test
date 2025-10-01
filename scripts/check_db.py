import sys
import hashlib
import requests


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/check_db.py <INFOMAX_CODE> [provider]")
        sys.exit(1)

    infomax_code = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else "logo_dev"

    base = "http://10.150.2.150:8004"

    # Compute logo_hash = md5(f"{provider}_{infomax_code}")
    logo_hash = hashlib.md5(f"{provider}_{infomax_code}".encode()).hexdigest()
    print(f"logo_hash: {logo_hash}")

    try:
        logos_url = f"{base}/api/schemas/raw_data/tables/logos/query"
        params = {
            "page": 1,
            "search_column": "logo_hash",
            "search": logo_hash,
        }
        r = requests.get(logos_url, params=params, timeout=15)
        print("logos status:", r.status_code)
        print(r.text)

        logo_id = None
        try:
            body = r.json()
            data = body.get("data") if isinstance(body, dict) else None
            if isinstance(data, list) and data:
                logo_id = data[0].get("logo_id")
        except Exception as e:
            print("logos parse error:", e)

        if logo_id:
            files_url = f"{base}/api/schemas/raw_data/tables/logo_files/query"
            params = {
                "page": 1,
                "search_column": "logo_id",
                "search": str(logo_id),
            }
            r2 = requests.get(files_url, params=params, timeout=15)
            print("logo_files status:", r2.status_code)
            print(r2.text)
        else:
            print("logo_id not found from logos response")
    except Exception as e:
        print("request error:", e)


if __name__ == "__main__":
    main()



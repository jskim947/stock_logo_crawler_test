import requests
import json

response = requests.get('http://localhost:8005/api/v1/logo-info?infomax_code=AMX:AIM', timeout=10)
print(f'Status Code: {response.status_code}')
print(f'Content-Type: {response.headers.get("Content-Type")}')
print(f'Response Length: {len(response.content)}')
print(f'Response Content: {response.text[:200]}')

try:
    data = response.json()
    print(f'JSON Data: {data}')
except Exception as e:
    print(f'JSON Parse Error: {e}')

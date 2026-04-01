import urllib.request
from urllib.error import HTTPError
import json

try:
    resp = urllib.request.urlopen("https://ai-stock-market-scanner.onrender.com/api/overview")
    print(resp.read().decode('utf-8'))
except HTTPError as e:
    body = e.read().decode('utf-8')
    try:
        data = json.loads(body)
        print("TRACEBACK:")
        print(data.get("traceback", ""))
        print("ERROR:")
        print(data.get("error", ""))
    except Exception as parse_err:
        print("Raw Body:")
        print(body)

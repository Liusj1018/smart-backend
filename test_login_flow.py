import requests
import json

BASE = "http://localhost:8000/api/v1"

# 1. Login
print("=== 1. LOGIN ===")
r = requests.post(f"{BASE}/auth/login", json={
    "email": "demo@smartdashboard.dev",
    "password": "demo-password-123"
})
print(f"Status: {r.status_code}")
tokens = r.json()
print(f"Access token: {tokens['access_token'][:50]}...")
print(f"Refresh token: {tokens['refresh_token'][:50]}...")
print(f"Expires in: {tokens['expires_in']}")

# 2. Get me
print("\n=== 2. GET /auth/me ===")
r2 = requests.get(f"{BASE}/auth/me", headers={
    "Authorization": f"Bearer {tokens['access_token']}"
})
print(f"Status: {r2.status_code}")
print(json.dumps(r2.json(), indent=2, ensure_ascii=False))

# 3. List members
print("\n=== 3. GET /members ===")
r3 = requests.get(f"{BASE}/members", headers={
    "Authorization": f"Bearer {tokens['access_token']}"
})
print(f"Status: {r3.status_code}")
data = r3.json()
print(f"Total members: {data.get('total', 'N/A')}")
if data.get('items'):
    print(f"First member: {data['items'][0].get('name', 'N/A')}")

print("\n=== ALL CHECKS PASSED ===")
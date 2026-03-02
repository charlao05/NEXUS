"""Quick login test"""
import requests

r = requests.post(
    "http://127.0.0.1:8000/api/auth/login",
    json={"email": "charles.rsilva05@gmail.com", "password": "Admin@123"},
    timeout=10,
)
print(f"STATUS: {r.status_code}")
print(f"BODY: {r.text[:300]}")

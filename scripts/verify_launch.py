import requests
import concurrent.futures
import time

API_URL = "http://localhost:8000/api/runs/launch"

def launch():
    try:
        resp = requests.post(API_URL, timeout=5)
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def verify_atomic_launch():
    print("Testing concurrent launch (5 requests)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(launch) for _ in range(5)]
        results = [f.result() for f in futures]
    
    ids = [r.get("exp_id") for r in results if r.get("ok")]
    print(f"Results: {results}")
    print(f"Allocated IDs: {ids}")
    
    if len(set(ids)) == 5 and len(ids) == 5:
        print("PASS: 5 unique IDs allocated.")
    else:
        print("FAIL: Possible race condition or allocation error.")

if __name__ == "__main__":
    verify_atomic_launch()

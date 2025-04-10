import requests
from tools.retry_request import retry_request
import concurrent.futures
import os
import sys

MAX_WORKERS = 5
LAST_RUN_LIMIT = 10
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
HEADERS = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

def fetch_instance_tests(instance_id):
    instance_url = f"https://api.currents.dev/v1/instances/{instance_id}"
    try:
        response = retry_request(requests.get, instance_url, headers=HEADERS, timeout=30)
        instance_data = response.json().get("data", {})
        
        group_id = instance_data.get("groupId")
        spec_path = instance_data.get("spec")
        
        # Check if tests exist
        tests = instance_data.get("results", {}).get("tests", [])
        if not tests:
            print(f"No tests found for instance {instance_id}")  # Debug print
            return []

        # Process tests concurrently if there are many
        results = []
        if len(tests) > 10:  # Only use concurrency if there are enough tests to justify it
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tests))) as executor:
                def process_test(test):
                    test_name = " > ".join(test["title"]) if isinstance(test["title"], list) else str(test["title"])
                    return {
                        "name": test_name,
                        "testId": test.get("testId"),
                        "state": test.get("state"),
                        "groupId": group_id,
                        "spec": spec_path,
                        "signature": instance_data.get("signature")
                    }
                
                # Map tests to futures and collect results
                futures = {executor.submit(process_test, test): test for test in tests}
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())
        else:
            # Process sequentially for small number of tests
            for test in tests:
                test_name = " > ".join(test["title"]) if isinstance(test["title"], list) else str(test["title"])
                results.append({
                    "name": test_name,
                    "testId": test.get("testId"),
                    "state": test.get("state"),
                    "groupId": group_id,
                    "spec": spec_path,
                    "signature": instance_data.get("signature")
                })
                
        return results
    except requests.RequestException as e:
        print(f"Error fetching data for instance {instance_id}: {e}", file=sys.stderr)
        return []

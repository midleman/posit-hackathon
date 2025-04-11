import requests
from currents_api.fetch_instance_tests import fetch_instance_tests
from currents_api.retry_request import retry_request
import concurrent.futures
from tqdm import tqdm
import os
import sys


CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
HEADERS = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}
MAX_WORKERS = 5
LAST_RUN_LIMIT = 10

def get_test_results_for_run(run_id):
    run_url = f"https://api.currents.dev/v1/runs/{run_id}"
    headers = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

    try:
        # print(f"Fetching test results for run {run_id}...")
        run_response = retry_request(requests.get, run_url, headers=headers, timeout=10)
        run_data = run_response.json().get("data", {})
        specs = run_data.get("specs", [])
        
        if not specs:
            print(f"No specs found for run {run_id}")
            return []

    except requests.RequestException as e:
        print(f"Error fetching run data for run {run_id}: {e}", file=sys.stderr)
        return []

    # Collect test instance IDs
    instance_ids = [spec.get("instanceId") for spec in specs if spec.get("instanceId")]
    # print(f"Found {len(instance_ids)} test instances in run {run_id}")

    results = []
    
    # Process instance IDs sequentially instead of using ThreadPoolExecutor
    # Use ThreadPoolExecutor for parallel fetching of test instances
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(instance_ids))) as executor:
        # Submit all fetch tasks
        future_to_instance = {executor.submit(fetch_instance_tests, instance_id): instance_id for instance_id in instance_ids}
        
        # Process results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_instance), total=len(instance_ids), desc=f"    ↪ [{run_id}] {len(instance_ids)} tests"):
            instance_id = future_to_instance[future]
            try:
                test_instance = future.result()
                
                # Filter only relevant data from each test
                for test in test_instance:
                    results.append({
                        "name": test["name"],
                        "title": test["title"],
                        "testId": test["testId"],
                        "status": test["state"],
                        "groupId": test["groupId"],
                        "spec": test["spec"],
                        # "signature": test["signature"],
                        "attempts": test["attempts"],
                    })
            except Exception as e:
                print(f"Error processing instance {instance_id}: {e}", file=sys.stderr)

    return results
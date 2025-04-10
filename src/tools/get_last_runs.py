from tools.retry_request import retry_request
import requests
import os
import sys

MAX_WORKERS = 5
LAST_RUN_LIMIT = 10
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
HEADERS = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

def get_last_runs():
    limit = LAST_RUN_LIMIT
    url = f"https://api.currents.dev/v1/projects/{CURRENTS_PROJECT_ID}/runs?limit={limit}&tags[]=merge"

    # print(f"Fetching last {limit} runs from {url}")

    all_runs = []
    try:
        # Initial request to get the first page of runs
        response = retry_request(requests.get, url, headers=HEADERS)
        runs = response.json().get("data", [])
        all_runs.extend(runs)

        # Check if there are more runs using pagination
        while len(runs) == limit:
            # Use the last run's `cursor` for pagination
            next_cursor = response.json().get("meta", {}).get("next_cursor")
            if next_cursor:
                paginated_url = f"{url}&starting_after={next_cursor}"
                response = retry_request(requests.get, paginated_url, headers=HEADERS)
                runs = response.json().get("data", [])
                all_runs.extend(runs)
            else:
                break

    except requests.RequestException as e:
        print(f"Error fetching runs: {e}", file=sys.stderr)

    return all_runs

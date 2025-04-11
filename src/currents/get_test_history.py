import os
import requests
from currents.retry_request import retry_request

MAX_WORKERS = 5
LAST_RUN_LIMIT = 10
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
HEADERS = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}


def get_test_history(spec_path, test_title, run_timestamp, group_id):
    # print(f"GET_TEST_HISTORY spec: {spec}, test_name: {test_name}, run_timestamp: {run_timestamp}")
    from datetime import datetime, timedelta
    # Check if the run_timestamp is a valid value
    if run_timestamp == "unknown" or not run_timestamp or not isinstance(run_timestamp, str):
        # If the timestamp is "unknown", not provided, or not a valid string, use the current timestamp
        print(f"Warning: run_timestamp is invalid, using the current timestamp.{run_timestamp}")
        run_timestamp = datetime.utcnow().isoformat()  # Default to the current time in UTC
    else:
        # If the timestamp is provided, ensure it's in the right format
        try:
            run_timestamp = datetime.fromisoformat(run_timestamp.replace("Z", ""))
        except ValueError as e:
            print(f"Error: Invalid timestamp format for run_timestamp: {run_timestamp}")
            raise e

    spec_path = str(spec_path)
    test_title = str(test_title)

    try:
        headers = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

        # Retrieve signature dynamically
        signature_url = "https://api.currents.dev/v1/signature/test"
        signature_payload = {
            "projectId": CURRENTS_PROJECT_ID,
            "specFilePath": spec_path,
            "testTitle": test_title
        }
        try:
            signature_response = retry_request(requests.post, signature_url, headers=headers, json=signature_payload, timeout=10)
            signature_data = signature_response.json().get("data", {})
            signature = signature_data.get("signature")
            # print('Signature:', signature)
            if not signature:
                raise ValueError("Signature not found in response.")
        except Exception as e:
            return {"raw_history": [], "error": f"Failed to fetch signature: {e}"}

        # Set date range (last 5 days)
        date_end = run_timestamp
        date_start = date_end - timedelta(days=5)
        date_start_str = date_start.isoformat() + "Z"
        date_end_str = date_end.isoformat() + "Z"

        history_url = f"https://api.currents.dev/v1/test-results/{signature}"

        # Pagination logic - fetch all pages of results
        all_results = []
        params = {
            "date_start": date_start_str,
            "date_end": date_end_str,
        }

        # Initial request to fetch the first page of results
        while True:
            response = retry_request(requests.get, history_url, headers=headers, params=params, timeout=10)
            data = response.json().get("data", [])
            
            if not data:
                break  # No more results to fetch

            all_results.extend(data)

            # Check for the presence of pagination fields in the response
            next_cursor = response.json().get("meta", {}).get("next_cursor")
            if next_cursor:
                params["starting_after"] = next_cursor  # Use next_cursor to fetch the next page
            else:
                break  # No more pages, break the loop

        # Filter results by branch, tags, and group_id if filters are provided
        filter_branches = os.getenv("FILTER_BRANCHES", "").split(",") if os.getenv("FILTER_BRANCHES") else []
        filter_tags = os.getenv("FILTER_TAGS", "").split(",") if os.getenv("FILTER_TAGS") else []
        
        def matches_filters(result):
            # Check branch filter
            branch_match = not filter_branches or result.get("commit", {}).get("branch") in filter_branches
            
            # Check tags filter
            tags = result.get("tags", [])
            tag_match = not filter_tags or any(tag in tags for tag in filter_tags)
            
            # Check group_id filter - if provided in function arguments
            group_id_match = not group_id or result.get("groupId") == group_id
            
            return branch_match and tag_match and group_id_match

        all_results = [r for r in all_results if matches_filters(r)]

        # Now process the fetched history data
        latest_commit = all_results[0].get("commit", {}) if all_results else {}
        author = latest_commit.get("authorName")
        last_pass_commit_sha = None
        last_pass_date = None
        consecutive_failures = 0

        for result in all_results:
            if result.get("status") == "failed":
                consecutive_failures += 1
            elif result.get("status") == "passed":
                last_pass_commit_sha = result.get("commit", {}).get("sha")
                last_pass_date = result.get("createdAt")
                break

        return {
            "raw_history": all_results,
            "latest_author": author,
            "lastPassCommitSHA": last_pass_commit_sha,
            "lastPassDate": last_pass_date,
            "consecutiveFailures": consecutive_failures + 1 # + 1 to include the current failure
        }
    except Exception as e:
        return {"raw_history": [], "error": str(e)}
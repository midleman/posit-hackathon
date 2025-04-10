import concurrent.futures
import json
import sys
from tqdm import tqdm
from tools.get_test_history import get_test_history

MAX_WORKERS = 5

def build_test_diff(previous_results, current_results, current_run_author, current_run_timestamp):
    previous_map = {t["testId"]: t for t in previous_results if t.get("testId")}
    current_map = {t["testId"]: t for t in current_results if t.get("testId")}

    all_test_ids = set(previous_map) | set(current_map)

    diff = {
        "Resolved": [],
        "Still Failing": [],
        "New Failures": [],
        "New Tests": [],
    }

    history_futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for test_id in all_test_ids:
            prev = previous_map.get(test_id)
            curr = current_map.get(test_id)

            if prev and not curr:
                continue  # test disappeared

            if not prev and curr:
                # curr["author"] = curr.get("author") or current_run_author
                diff["New Tests"].append(curr)
            elif prev["status"] == "failed" and curr["status"] == "passed":
                diff["Resolved"].append(curr)
            elif prev["status"] == "failed" and curr["status"] == "failed":
                diff["Still Failing"].append(curr)
                if curr["testId"] not in history_futures:
                    history_futures[curr["testId"]] = executor.submit(get_test_history, str(curr["spec"]), str(curr["name"]), current_run_timestamp)
            elif prev["status"] == "passed" and curr["status"] == "failed":
                diff["New Failures"].append(curr)
                if curr["testId"] not in history_futures:
                    history_futures[curr["testId"]] = executor.submit(get_test_history, str(curr["spec"]), str(curr["name"]), current_run_timestamp)

        for test_id, future in history_futures.items():
            history = future.result()
            curr = current_map[test_id]
            curr["history"] = history
            curr["author"] = current_run_author
            curr["lastPassCommitSHA"] = history.get("lastPassCommitSHA")
            curr["lastPassDate"] = history.get("lastPassDate")
            curr["consecutiveFailures"] = history.get("consecutiveFailures")

            # print(f"Debug: consecutiveFailures: {curr['consecutiveFailures']}")

            # Check the logic for categorizing as "Still Failing" or "New Failure"
            # A test is a "Still Failing" if it failed in both runs AND has multiple consecutive failures
            if curr.get("consecutiveFailures") is not None and curr["consecutiveFailures"] > 1:
                # Set the commit SHA from the first (earliest) consecutive failure
                first_failure = min(history["raw_history"], key=lambda x: x["createdAt"])
                curr["firstFailureCommitSHA"] = first_failure.get("commit", {}).get("sha")

                # Debug print statement to confirm the commit SHA for the first failure
                # print(f"Debug: First failure commit SHA for '{curr['name']}': {curr['firstFailureCommitSHA']}")

    for key in diff:
        diff[key] = sorted(diff[key], key=lambda x: x["name"])

    # Write the diff to a JSON file for debugging and reference

    try:
        with open("output/diff.json", "w") as f:
            json.dump(diff, f, indent=2, default=str)
        # print(f"Test diff written to {output_file}")
    except Exception as e:
        print(f"Error writing diff to file: {e}", file=sys.stderr)

    return diff
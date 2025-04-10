import json
import sys
import os
import requests
import time
import random
from dotenv import load_dotenv
from openai import OpenAI
import concurrent.futures
from tqdm import tqdm

load_dotenv()

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
HEADERS = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}
CURRENTS_CURRENT_RUN_ID = 'b5b38a6560f9218d'  # you can set this dynamically as needed
# '149ca10cd4d57dad' # recovered
# '7210d6e74f883567' # passing
# '0603d0369cfd356f', 'c58b9ba2c5f1dd01' # new failure
# 'b5b38a6560f9218d' # persistent failure
# 'b150b33a8d808621' # new tests
# 'cd6f705cb1aed1d0' # many failures


# Initialize the OpenAI client
client = OpenAI()

# Define your tools
def retry_request(func, *args, **kwargs):
    retries = 3
    for attempt in range(retries):
        try:
            response = func(*args, **kwargs)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                continue
            response.raise_for_status()  # Raise an exception for bad status codes
            return response
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(random.uniform(1, 2 ** attempt))  # Exponential backoff
            else:
                raise e
            

# Define the tool to fetch test results
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
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(tests))) as executor:
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


def get_test_results_for_run(run_id):
    run_url = f"https://api.currents.dev/v1/runs/{run_id}"
    headers = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

    try:
        print(f"Fetching test results for run {run_id}...")
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
    print(f"Found {len(instance_ids)} test instances in run {run_id}")

    results = []
    # Process instance IDs sequentially instead of using ThreadPoolExecutor
    # Use ThreadPoolExecutor for parallel fetching of test instances
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(instance_ids))) as executor:
        # Submit all fetch tasks
        future_to_instance = {executor.submit(fetch_instance_tests, instance_id): instance_id for instance_id in instance_ids}
        
        # Process results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_instance), total=len(instance_ids), desc="Fetching test instances"):
            instance_id = future_to_instance[future]
            try:
                test_instance = future.result()
                
                # Filter only relevant data from each test
                for test in test_instance:
                    results.append({
                        "name": test["name"],
                        "testId": test["testId"],
                        "status": test["state"],
                        "groupId": test["groupId"],
                        "spec": test["spec"],
                        "signature": test["signature"]
                    })
            except Exception as e:
                print(f"Error processing instance {instance_id}: {e}", file=sys.stderr)

    return results

def get_test_history(spec, test_name, run_timestamp):
    print(f"GET_TEST_HISTORY spec: {spec}, test_name: {test_name}, run_timestamp: {run_timestamp}")
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

    spec = str(spec)
    test_name = str(test_name)

    try:
        headers = {"Authorization": f"Bearer {CURRENTS_API_KEY}"}

        # Retrieve signature dynamically
        signature_url = "https://api.currents.dev/v1/signature/test"
        signature_payload = {
            "projectId": CURRENTS_PROJECT_ID,
            "specFilePath": spec,
            "testTitle": test_name
        }
        try:
            signature_response = retry_request(requests.post, signature_url, headers=headers, json=signature_payload, timeout=10)
            signature_data = signature_response.json().get("data", {})
            signature = signature_data.get("signature")
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
        print(f"Fetching history for {spec} > {test_name}...")
        print(f"History URL: {history_url}")
        # print(f"Date range: {date_start_str} to {date_end_str}")
        params = {
            # "branch[]": ["main", "refs/heads/main"],
            # "tags[]": ["merge"],
            "date_start": date_start_str,
            "date_end": date_end_str,
        }

        response = retry_request(requests.get, history_url, headers=headers, params=params, timeout=10)
        data = response.json().get("data", [])
        latest_commit = data[0].get("commit", {}) if data else {}
        author = latest_commit.get("authorName")
        last_pass_commit_sha = None
        last_pass_date = None
        consecutive_failures = 0

        for result in data:
            if result.get("status") == "failed":
                consecutive_failures += 1
            elif result.get("status") == "passed":
                break

        return {
            "raw_history": data,
            "latest_author": author,
            "lastPassCommitSHA": last_pass_commit_sha,
            "lastPassDate": last_pass_date,
            "consecutiveFailures": consecutive_failures
        }
    except Exception as e:
        return {"raw_history": [], "error": str(e)}

# 🔄 Build test diff between previous and current results
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for test_id in all_test_ids:
            prev = previous_map.get(test_id)
            curr = current_map.get(test_id)

            if prev and not curr:
                continue  # test disappeared

            if not prev and curr:
                curr["author"] = curr.get("author") or current_run_author
                diff["New Tests"].append(curr)
            elif prev["status"] == "failed" and curr["status"] == "passed":
                diff["Resolved"].append(curr)
            elif prev["status"] == "failed" and curr["status"] == "failed":
                if curr["testId"] not in history_futures:
                    history_futures[curr["testId"]] = executor.submit(get_test_history, str(curr["spec"]), str(curr["name"]), current_run_timestamp)
            elif prev["status"] == "passed" and curr["status"] == "failed":
                if curr["testId"] not in history_futures:
                    history_futures[curr["testId"]] = executor.submit(get_test_history, str(curr["spec"]), str(curr["name"]), current_run_timestamp)

        for test_id, future in history_futures.items():
            history = future.result()
            curr = current_map[test_id]
            curr["history"] = history
            curr["author"] = history.get("latest_author") or current_run_author
            curr["lastPassCommitSHA"] = history.get("lastPassCommitSHA")
            curr["lastPassDate"] = history.get("lastPassDate")
            curr["consecutiveFailures"] = history.get("consecutiveFailures")

            # print(f"Debug: History for test '{curr['name']}':")
            print(f"Debug: consecutiveFailures: {curr['consecutiveFailures']}")

            # Check the logic for categorizing as "Still Failing" or "New Failure"
            # A test is a "Still Failing" if it failed in both runs AND has multiple consecutive failures
            if curr.get("consecutiveFailures") is not None and curr["consecutiveFailures"] > 1:
                # Set the commit SHA from the first (earliest) consecutive failure
                first_failure = min(history["raw_history"], key=lambda x: x["createdAt"])
                curr["firstFailureCommitSHA"] = first_failure.get("commit", {}).get("sha")

                # Debug print statement to confirm the commit SHA for the first failure
                print(f"Debug: First failure commit SHA for '{curr['name']}': {curr['firstFailureCommitSHA']}")

                diff["Still Failing"].append(curr)
                # print(f"⭐️{curr}")
            # A test is a "New Failure" if it failed in the current run but either:
            # - passed in the previous run
            # - failed in the previous run but this is the first failure in the sequence
            else:
                print(f"Debug: Adding to 'New Failures': {curr['name']}")
                diff["New Failures"].append(curr)

    for key in diff:
        diff[key] = sorted(diff[key], key=lambda x: x["name"])

    print(f"Diff: {diff}")

    return diff


def get_last_runs():
    limit = 20
    url = f"https://api.currents.dev/v1/projects/{CURRENTS_PROJECT_ID}/runs?limit={limit}"
    # print(f"Fetching last {limit} runs from {url}")
    try:
        response = retry_request(requests.get, url, headers=HEADERS)
        all_runs = response.json().get("data", [])
        return [
            r for r in all_runs
            if r.get("meta", {}).get("commit", {}).get("branch") in ["main", "refs/heads/main"]
            and "release" not in r.get("tags", [])
        ]
    except requests.RequestException as e:
        print(f"Error fetching runs: {e}", file=sys.stderr)
        return []

# Define the tools for OpenAI to use
tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_instance_tests",
            "description": "Fetch test results for a specific instance",
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_id": {
                        "type": "string",
                        "description": "ID of the test instance"
                    },
                },
                "required": ["instance_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_test_results_for_run",
            "description": "Get test results for a specific run",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "ID of the run"
                    },
                },
                "required": ["run_id"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_test_changes",
            "parameters": {
                "type": "object",
                "properties": {
                    "diff": {
                        "type": "object",
                        "description": "Test result diff data"
                    }
                },
                "required": ["diff"],
            },
        },
    },{
        "type": "function",
        "function": {
            "name": "get_last_runs",
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_test_history",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "string",
                        "description": "Path to the spec file"
                    },
                    "test_name": {
                        "type": "string",
                        "description": "Name of the test"
                    },
                    "run_timestamp": {
                        "type": "string",
                        "description": "Timestamp of the run"
                    }
                },
                "required": ["spec", "test_name", "run_timestamp"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_test_diff",
            "description": "Build a test diff between previous and current results",
            "parameters": {
                "type": "object",
                "properties": {
                    "previous_results": {
                        "type": "array",
                        "description": "Previous test results",
                        "items": {
                            "type": "object"
                        }
                    },
                    "current_results": {
                        "type": "array",
                        "description": "Current test results",
                        "items": {
                            "type": "object"
                        }
                    },
                    "current_run_author": {
                        "type": "string",
                        "description": "Author of the current run"
                    },
                    "current_run_timestamp": {
                        "type": "string",
                        "description": "Timestamp of the current run"
                    },
                },
                "required": ["previous_results", "current_results", "current_run_author", "current_run_timestamp"],
            },
        }
    }
]

# Global context to hold state
context = {
    "previous_run_id": None,
    "current_run_id": CURRENTS_CURRENT_RUN_ID,
    "previous_results": None,
    "current_results": None,
    "current_run_author": None,
    "current_run_timestamp": None,
}

def process_conversation(messages):
    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        message = response.choices[0].message
        messages.append(message.model_dump())

        if not message.tool_calls:
            # If there are no tool calls, we're done
            return message.content

        # Process all tool calls
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # Initialize content as empty dict or appropriate default
            content = {}

            if function_name == "get_last_runs":
                runs = get_last_runs()
                current_index = next((i for i, r in enumerate(runs) if r["runId"] == CURRENTS_CURRENT_RUN_ID), None)

                if current_index is None:
                    print("No CURRENTS_CURRENT_RUN_ID found", file=sys.stderr)
                    sys.exit(1)

                if current_index + 1 >= len(runs):
                    print("No previous run found for comparison.", file=sys.stderr)
                    sys.exit(1)

                previous_run_id = runs[current_index + 1]["runId"]
                current_run_id = runs[current_index]["runId"]

                # Store results in context
                # context["current_run_id"] = current_run_id
                context["previous_run_id"] = previous_run_id
                print(f"Current run ID: {context['current_run_id']}")
                print(f"Previous run ID: {context['previous_run_id']}")
                
                # Return both run IDs in the content
                content = {
                    "current_run_id": current_run_id,
                    "previous_run_id": previous_run_id,
                }
            elif function_name == "get_test_results_for_run":
                run_id = function_args.get("run_id")
                content = get_test_results_for_run(run_id)
                # print(f"Storing results for {run_id}")
                if run_id == context["current_run_id"]:
                    # print(f"Storing results as current for {run_id}")
                    context["current_results"] = content
                elif run_id == context["previous_run_id"]:
                    # print(f"Storing results as previous for {run_id}")
                    context["previous_results"] = content
            elif function_name == "build_test_diff":
                previous_run_results = context.get("previous_results")
                current_run_results = context.get("current_results")
                current_run_author = function_args.get("current_run_author")
                current_run_timestamp = function_args.get("current_run_timestamp")
                current_run_id = context.get("current_run_id")
                previous_run_id = context.get("previous_run_id")

                # print previous_run_results to file
                # with open(f"previous_run_results-{previous_run_id}.json", "w") as file:
                #     json.dump(previous_run_results, file, indent=2)
                # # print current_run_results to file
                # with open(f"current_run_results-{current_run_id}.json", "w") as file:
                #     json.dump(current_run_results, file, indent=2)

                # Ensure that previous and current results are not None
                if previous_run_results is None or current_run_results is None:
                    print("Error: previous_results or current_results are None")
                    return "Error: Missing test results"

                content = build_test_diff(previous_run_results, current_run_results, current_run_author, current_run_timestamp)
                print(content)

            elif function_name == "fetch_instance_tests":
                instance_id = function_args.get("instance_id")
                content = fetch_instance_tests(instance_id)
            elif function_name == "get_test_history":
                spec = function_args.get("spec")
                test_name = function_args.get("test_name")
                run_timestamp = function_args.get("run_timestamp")
                content = get_test_history(spec, test_name, run_timestamp)
            else:
                # If the function is unknown, return an error message
                content = f"Unknown function: {function_name}"
                print(f"Unknown function: {function_name}", file=sys.stderr)

            # Update the context with the results
            context["last_response"] = content  # Store the last response to pass forward if needed

            # Append the content to the messages for the next prompt
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(content) if not isinstance(content, str) else content,
                }
            )


# Initial conversation
messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant that can fetch Playwright test results from the Currents.dev API and analyze them. I'm going to need you to remember a few things: `previous_run_results`, `current_run_results`, `current_run_author`, and `current_run_timestamp`. These will be used to build a test diff. You can also use the `get_test_history` function to fetch test history for specific tests.",
    },
    {
        "role": "user",
        "content": f"First, let's retrieve the last 2 runs (use tool: get_last_runs). The project ID is {CURRENTS_PROJECT_ID}. Let's refer to the most 2 recent runs from these results as the `current_run_id` and `previous_run_id`. Next, let's fetch the test results (get_test_results_for_run) for both current run and previous run ids. Remember these tests results (current_test_results, previous_test_results), we need them later."
    },
    {
        "role": "user",
        "content": f"Next, let's build a test diff between the previous and current results. (build_test_diff). This will help us identify the following tests: New Failures, Still Failing, New Tests, and Resolved. The diff should include the test name, status, and any relevant metadata. We can ignore pending/skipped tests."
    },
    # {
    #     "role": "user",
    #     "content": "Can you share your current diff with me?",
    # }
    {
        "role": "user",
        "content": f"""Finally, let's summarize meaningful changes across tests. Categorize the tests and include 1-sentence insights where possible. Make it easy to scan. Use this format, with no bullets and one test per line. Make sure to count the items from the JSON data and ensure the section counts match the actual number of entries. If there are 5 or more 'New Failures', please identify any common themes, related features, or error messages that might indicate a broader issue. Only include a section if it has at least one test. Do not write anything about sections that are empty — completely omit the section header and any related commentary. If there are no sections to display (everything has PASSED), just say '✅ All tests passed.
        🧩 Common Themes (only show this section if there are 5+ New Failures)
        If there are 5 or more new failures, include a section called '🧩 Common Themes' summarizing any shared cause, errors or themes. Otherwise, omit it entirely.
        If there are more than one observations, separate them on a new line with a bullet point and make them very short minimal one liner summaries that are easy to scan.
        Just say '✅ All tests passed.' if there are NO failures, new tests, or resolved tests.

        🔴 New Failures (new_failures_count):
        (For each test that failed:
        - If the test has failed for 2 or more consecutive times: "failing for the last N runs".
        - Include very short error context if available, but omit stack traces or redundant info.)
        - Do not include author

        [e2e-group] Feature > Test name
        [e2e-browser] Feature2 > Test name (increased flakiness, 3+ failures in last 5 runs)

        🫠 Still Failing (still_failing_count):
        [e2e-win] Feature > Test name (failed X times) – since commit make_terminal_link('f9ae619de39b948eb5672f76808877d06b0db1d8', 'https://github.com/posit-dev/positron/commit/f9ae619de39b948eb5672f76808877d06b0db1d8')(shorthand version for title but full version for link).
        (first failure commit SHA: firstFailureCommitSHA')
    
        ⭐️ New Tests (new_test_count):
        [groupId] Feature > Test name (added by commit.authorName)
        [e2e-electron] Login > Should be able to login (added by Marie Idleman)

        ✅ Resolved (resolved_count):
        [e2e-electron] Feature > Test name (no recent passing history)"""
    },
]

# Start the conversation and process any tool calls
final_response = process_conversation(messages)

print("Analysis:\n\n", final_response)
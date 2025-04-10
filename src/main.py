import json
import sys
import os
from dotenv import load_dotenv
from openai import OpenAI

from tools.fetch_instance_tests import fetch_instance_tests
from tools.get_test_results_for_run import get_test_results_for_run
from tools.build_test_diff import build_test_diff
from tools.get_last_runs import get_last_runs
from tools.get_test_history import get_test_history
from helpers.resetOutputDir import resetOutputDir

load_dotenv()

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")

# Toggle for different scenarios
CURRENTS_CURRENT_RUN_ID = '82224ed471d13022' # new failure
CURRENTS_CURRENT_RUN_ID = '149ca10cd4d57dad' # recovered
# CURRENTS_CURRENT_RUN_ID = '324ac53e1fc63ec9' # new failure

# CURRENTS_CURRENT_RUN_ID = '7210d6e74f883567' # passing
# CURRENTS_CURRENT_RUN_ID = 'b5b38a6560f9218d' # persistent failure
# CURRENTS_CURRENT_RUN_ID = 'b150b33a8d808621' # new tests (set LAST_RUN_LIMIT to 30)
# CURRENTS_CURRENT_RUN_ID = 'cd6f705cb1aed1d0' # many failures

# Reset output directory to ensure we have a clean slate
resetOutputDir()

# Initialize the OpenAI client
client = OpenAI()

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
    "run_diff": None,
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
                print("📦 Loading run data...")
                runs = get_last_runs()
                # Write runs data to JSON file for debugging and reference
                try:
                    with open("output/runs.json", "w") as f:
                        json.dump(runs, f, indent=2, default=str)
                except Exception as e:
                    print(f"Error writing runs to file: {e}", file=sys.stderr)
                current_index = next((i for i, r in enumerate(runs) if r["runId"] == CURRENTS_CURRENT_RUN_ID), None)

                if current_index is None:
                    print(f"No CURRENTS_CURRENT_RUN_ID found: {CURRENTS_CURRENT_RUN_ID}", file=sys.stderr)
                    sys.exit(1)

                if current_index + 1 >= len(runs):
                    print(f'current_index {current_index}, total {len(runs)}')

                    print("No previous run found for comparison.", file=sys.stderr)
                    sys.exit(1)

                previous_run_id = runs[current_index + 1]["runId"]
                current_run_id = runs[current_index]["runId"]
                current_run_timestamp = runs[current_index]["createdAt"]

                # Store results in context
                context["previous_run_id"] = previous_run_id
                context["current_run_timestamp"] = current_run_timestamp

                print(f"   ↳ Current: {current_run_id}")
                print(f"   ↳ Previous: {previous_run_id}")
                
                # Return both run IDs in the content
                content = {
                    "current_run_id": current_run_id,
                    "previous_run_id": previous_run_id,
                    "current_run_timestamp": current_run_timestamp,
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
                print("🧠 Analyzing test runs with OpenAI...")
                previous_run_results = context.get("previous_results")
                current_run_results = context.get("current_results")
                current_run_author = function_args.get("current_run_author")
                current_run_timestamp = function_args.get("current_run_timestamp")
                current_run_id = context.get("current_run_id")
                previous_run_id = context.get("previous_run_id")

                # print previous_run_results to file
                with open(f"output/previous_run_results-{previous_run_id}.json", "w") as file:
                    json.dump(previous_run_results, file, indent=2)
                # print current_run_results to file
                with open(f"output/current_run_results-{current_run_id}.json", "w") as file:
                    json.dump(current_run_results, file, indent=2)

                # Ensure that previous and current results are not None
                if previous_run_results is None or current_run_results is None:
                    print("Error: previous_results or current_results are None")
                    return "Error: Missing test results"

                content = build_test_diff(previous_run_results, current_run_results, current_run_author, current_run_timestamp)
                context["run_diff"] = content

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
        "content": 
        f"""You are an assistant that can fetch Playwright test results from the Currents.dev API and analyze them using the provided `run_diff` data. 
        The following steps need to be completed in sequence:
        1. Fetch the last 2 runs for the project with {CURRENTS_PROJECT_ID}. Use `get_last_runs`. Refer to the most recent as `current_run_id` and the second most recent as `previous_run_id`.
        2. Fetch the test results for both runs using `get_test_results_for_run` for the `current_run_id` and `previous_run_id`.
        3. Build a test diff between the previous and current results using `build_test_diff`. Use {context.get('run_diff')} to categorize the tests:
            - Only include a section if it has at least one test. Do not include any commentary for empty sections or a high level summary, just the sections below should be included.
            - If there are no new failures, no new tests, no resolved issues, and no tests that are still failing, just return "All tests passed. ✅"

        🧩 Common Themes (only show this section if there are 5+ New Failures)
        If there are 5 or more new failures, include a section called '🧩 Common Themes' summarizing any shared causes, errors, or themes. If there is more than one observation, separate them on a new line with a bullet point.

        🔴 New Failures (run_diff[New Failures]):
        if len(diff["Still Failing"]) > 0:
        analysis += "🫠 Still Failing (X):\n" + "\n".join([test["name"] for test in diff["Still Failing"]])
        For each test that failed:
        - If the test has failed 2 or more consecutive times, note "failing for the last N runs".
        - Include very short error context if available, but omit stack traces or redundant info.
        - Do not include author.
        Example:
        [e2e-group] Feature > Test name
        [e2e-browser] Feature2 > Test name (increased flakiness, 3+ failures in last 5 runs)

        🫠 Still Failing (run_diff[Still Failing]):
        - Do not include error analysis.
        [e2e-win] Feature > Test name (X consecutive fails) – since commit [shorthand commitSHA]('https://github.com/posit-dev/positron/commit/fullcommitSHA')
    
        ⭐️ New Tests (run_diff[New Tests]):
        - No extra commentary.
        [groupId] Feature > Test name (added by commit.authorName)
        [e2e-electron] Login > Should be able to login (added by Marie Idleman)

        ✅ Resolved (run_diff[Resolved]):
        [e2e-electron] Feature > Test name
        """
    }]

# Start the conversation and process any tool calls
final_response = process_conversation(messages)

print("\n\n", final_response)
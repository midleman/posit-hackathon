import json
import sys
import os
from dotenv import load_dotenv
from openai import OpenAI

from currents_api.get_run_details import get_run_details
from currents_api.get_test_results_for_run import get_test_results_for_run
from currents_api.get_project_runs import get_previous_run
from currents_api.get_test_history import get_test_history
from helpers.compare_test_results import compare_test_results
from helpers.reset_output_dir import reset_output_dir

load_dotenv()

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Toggle for different scenarios
CURRENTS_CURRENT_RUN_ID = '8d295e14f8b6168c' # 12 resolved, 2 failures
# CURRENTS_CURRENT_RUN_ID = 'd2d5a69185f2ca69' # new tests
# CURRENTS_CURRENT_RUN_ID = 'c38c1f8033d08338' # passing
# CURRENTS_CURRENT_RUN_ID = 'b5b38a6560f9218d' # persistent failure 6x
# CURRENTS_CURRENT_RUN_ID = '324ac53e1fc63ec9' # new failure
# CURRENTS_CURRENT_RUN_ID = 'cd6f705cb1aed1d0' # 12 new failures, 2 still failing
# CURRENTS_CURRENT_RUN_ID = 'd2d5a69185f2ca69' # new test

# 🤖 Main
def main():
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv
    
    reset_output_dir()

    print("📦 Get test runs...")
    print(f"    ↪ current run id: {CURRENTS_CURRENT_RUN_ID}")
    current_run_details = get_run_details(CURRENTS_CURRENT_RUN_ID, CURRENTS_API_KEY)
    previous_run_details = get_previous_run(CURRENTS_CURRENT_RUN_ID)
    print(f"    ↪ previous run id: {previous_run_details['runId']}")

    if debug_mode:
        with open("output/previous_run_details.json", "w") as f:
            json.dump(previous_run_details, f, indent=2, default=str)
        with open("output/current_run_details.json", "w") as f:
            json.dump(current_run_details, f, indent=2, default=str)

    print("🧪 Get test results...")
    current_run_tests = get_test_results_for_run(CURRENTS_CURRENT_RUN_ID)
    previous_run_tests = get_test_results_for_run(previous_run_details["runId"])
        
    if debug_mode:
        with open("output/current_run_tests.json", "w") as f:
            json.dump(current_run_tests, f, indent=2, default=str)
        with open("output/previous_run_tests.json", "w") as f:
            json.dump(previous_run_tests, f, indent=2, default=str)

    # compare the test results
    test_run_diff = compare_test_results(previous_run_tests, current_run_tests)

    # for tests that are still failing, get the history of the test
    # and add it to the test object
    still_failing = test_run_diff.get("Still Failing", [])
    if still_failing:
        for test in still_failing:
            group_id = test.get("groupId") #e2e-browser, e2e-electron, e2e-win
            test_name = test.get("name")
            spec = test.get("spec")
            run_timestamp = current_run_details.get("createdAt")
            if test_name and spec and run_timestamp:
                test_history = get_test_history(spec, test_name, run_timestamp, group_id)
                test["history"] = test_history
                if debug_mode:
                    safe_test_name = test_name.replace("/", "_").replace(">", "_").replace(" ", "_")
                    with open(f"output/test_history_{group_id}_{safe_test_name}.json", "w") as f:
                        json.dump(test_history, f, indent=2, default=str)

    # use OpenAI to analyze the test results
    print("🧠 Analyzing data with OpenAI...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": 
                    f"""Analyze {test_run_diff} and provide a summary of the changes.
                    Only show sections that have data, do not comment about empty sections.
                    Do not format the output as a markdown code block.
                    Do not insert bullet points or any other formatting unless directed to do so.
                    If test title is more than 50 characters, truncate at 50 and add append "...

                    🔍 Patterns (only show this section if there are 4+ New Failures)
                    Summarize any similar or repetitive errors?. Do any particular features seem to have multiple failures?
                    If there is more than one observation, separate them on a new line with a bullet point.

                    🔴 New Failures ({len(test_run_diff["New Failures"])}):
                    Include very short error context if available, but omit stack traces or redundant info, summarize it in 35 characters or less.
                    Do not include author.
                    Do not include comment about consecutive failures/attempts.
                    Always keep it VERY brief and to one line.
                    Example:
                    [e2e-browser] Feature > Test name — Timeout waiting for 'Preview'
                    [e2e-electron] Feature > Test name — Timeout waiting for visibility
                    [e2e-window] Feature > Test name — Interrupted run

                    🫠 Still Failing ({len(test_run_diff["Still Failing"])}):
                    Include note "Yx since Z".
                    Do not include error analysis or observations.
                    Example:
                    [e2e-win] Feature > Test name (2x since [shorthand commitSHA])
                    [e2e-browser] Feature > Test name (3x since [shorthand commitSHA])

                    ⭐️ New Tests ({len(test_run_diff["New Tests"])}):
                    No extra commentary, but include author name.
                    Example:
                    [groupId] Feature > Test name (by {current_run_details.get("meta", {}).get("commit", {}).get("authorName")})
                    [e2e-electron] Login > Should be able to login (added by Marie Idleman)

                    ✅ Resolved ({len(test_run_diff["Resolved"])}):
                    If test title is more than 90 characters, truncate at 90 characters. (Resolved section only)
                    No extra commentary.
                    Example:
                    [e2e-electron] Feature > Test name
                    """
            }
        ],
        tools=[],
        tool_choice="auto",
    )
    analysis = response.choices[0].message.content.strip();
    print("\n\n", analysis)

    if debug_mode:
        with open("output/test_run_diff.json", "w") as f:
            json.dump(test_run_diff, f, indent=2, default=str)


if __name__ == "__main__":
    main()


                    # 🔴 New Failures ({len(test_run_diff["New Failures"])}):
                    # - Truncate test title at 60 characters.
                    # - Include very short error context if available, but omit stack traces or redundant info.
                    # - Do not include author.
                    # - Do not include comment about consecutive failures/attempts.
                    # - Always keep it VERY brief and to one line.

                    # [e2e-browser] Feature > Test name — Timeout waiting for 'Preview'
                    # [e2e-electron] Feature > Test name — Timeout waiting for visibility
                    # [e2e-window] Feature > Test name — Interrupted run

                    # [shorthand commitSHA]('https://github.com/posit-dev/positron/commit/fullcommitSHA'))
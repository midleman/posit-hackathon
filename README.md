# posit-hackathon

## Purpose

This project is designed to help you retrieve, analyze, and compare test results across multiple runs using the Currents.dev API. It provides actionable insights based on the success, failure, and resolution of tests over time. Specifically, it focuses on categorizing tests into the following groups:

- **New Failures**: Tests that failed for the first time in the current run.
- **Still Failing**: Tests that have failed in both the previous and current runs.
- **Resolved**: Tests that were previously failing but have passed in the current run.
- **New Tests**: Tests that were added in the current run.

## Installation

To get started with this project, follow these steps:

1. **Clone the repository:**

    ```bash
    git clone https://github.com/posit-dev/posit-hackathon.git
    ```

2. **Install dependencies:**

    Ensure you have `python` and `pip` installed. Then, install the necessary dependencies by running:

    ```bash
    pip install -r requirements.txt
    ```

3. **Set environment variables:**

    You will need to set the following environment variables for API access:

    ```bash
    CURRENTS_API_KEY=your_api_key
    CURRENTS_PROJECT_ID=your_project_id
    OPENAI_API_KEY=your_api_key
    ```

## How It Works

1. **Fetching Runs for the Currents Project**: The script retrieves the most recent test runs based on the project ID and filters them by the "merge" tag.
2. **Retrieving Test Results**: Test results for each run are fetched from the Currents.dev API.
3. **Generating the Test Diff**: A diff is generated by comparing the results from the previous and current runs. This diff categorizes tests as "New Failures," "Still Failing," and "Resolved."
4. **Detailed Analysis**: The analysis includes detailed insights about each test, including its status, consecutive failures, and overall trend.

## Examples

### A previously failing test is now passing

If a test that was previously failing has now passed in the most recent run, it will be categorized under "Resolved." Here's an example:

```bash
✅ Resolved (1):
[e2e-electron] New UV Environment > Python - Add new UV environment
```

### There are no notable diffs between the runs

If the results from the previous and current runs are essentially the same (i.e., all tests pass or fail in the same way), the output will indicate that all tests passed:

```bash
All tests passed. ✅
```


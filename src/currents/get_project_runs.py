import requests
import os

CURRENTS_PROJECT_ID = os.getenv("CURRENTS_PROJECT_ID")
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")

def get_project_runs(limit: int = 10, ending_after: str = None, tags: list = None, branches: list = None) -> dict:
    """
    Fetch a list of test runs for a given Currents project.

    Args:
        limit (int, optional): Number of runs to fetch (default is 10, max is 50).
        starting_before (str, optional): Cursor for pagination.
        ending_after (str, optional): Cursor for pagination.
        tags (list, optional): List of tag strings to filter by.
        branches (list, optional): List of branch names to filter by.

    Returns:
        dict: Response containing the list of filtered runs or an error message.
    """
    url = f"https://api.currents.dev/v1/projects/{CURRENTS_PROJECT_ID}/runs"
    headers = {
        "Authorization": f"Bearer {CURRENTS_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "limit": limit
    }
    if ending_after:
        params["ending_after"] = ending_after
    if tags:
        for tag in tags:
            params.setdefault("tags[]", []).append(tag)
    if branches:
        for branch in branches:
            params.setdefault("branches[]", []).append(branch)

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if "data" in data and (tags or branches):
            filtered_runs = []
            for run in data["data"]:
                run_tags = set(run.get("tags", []))
                run_branch = run.get("meta", {}).get("commit", {}).get("branch")

                if tags and not set(tags).issubset(run_tags):
                    continue
                if branches and run_branch not in branches:
                    continue

                filtered_runs.append(run)

            data["data"] = filtered_runs

        return data
    except requests.HTTPError as http_err:
        return {"error": str(http_err), "status_code": response.status_code}
    except Exception as err:
        return {"error": str(err)}


def get_previous_run(reference_run_id: str, tags: list = ['merge'], branches: list = ['main', 'refs/heads/main']) -> dict:
    """
    Fetch the immediate previous run for a given Currents project before a specific run ID.

    Args:
        reference_run_id (str): The run ID to look back from.

    Returns:
        dict: The previous run details or an error message.
    """

    cursor = None
    seen_reference = False

    while True:
        recent_runs = get_project_runs(limit=50, ending_after=cursor, tags = tags, branches = branches)
        runs = recent_runs.get("data", [])
        if not runs:
            break

        for run in runs:
            if seen_reference and run.get("runId") != reference_run_id:
                return run
            if run.get("runId") == reference_run_id:
                seen_reference = True

        if not recent_runs.get("has_more"):
            break

        cursor = runs[-1].get("cursor")
        if not cursor:
            break

    return {"error": f"Previous run not found for {reference_run_id}"}

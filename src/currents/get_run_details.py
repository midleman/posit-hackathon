import requests
import os

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")

def get_run_details(run_id: str) -> dict:
    """
    Fetch details for a given Currents run ID.

    Args:
        run_id (str): The ID of the run to retrieve.
        api_key (str): The API key for authentication.

    Returns:
        dict: The run details, or an error message if unsuccessful.
    """
    url = f"https://api.currents.dev/v1/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {CURRENTS_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        raw_data = response.json()
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return {"error": str(http_err), "status_code": response.status_code}
    except Exception as err:
        print(f"Unexpected error: {err}")
        return {"error": str(err)}
    
    if "data" not in raw_data:
        return {"error": raw_data.get("error", "No data found.")}

    data = raw_data["data"]
    # filtered = {
    #     "runId": data.get("runId"),
    #     "createdAt": data.get("createdAt"),
    #     "tags": data.get("tags"),
    #     "status": raw_data.get("status"),
    #     "groupId": None,
    #     "meta": {
    #         "commit": {
    #             "sha": None,
    #             "branch": None,
    #             "authorName": None
    #         }
    #     }
    # }

    # # Extract groupId if present
    # if "groups" in data and data["groups"]:
    #     filtered["groupId"] = data["groups"][0].get("groupId")

    # # Extract commit info
    # if "meta" in data and "commit" in data["meta"]:
    #     commit = data["meta"]["commit"]
    #     filtered["meta"]["commit"]["sha"] = commit.get("sha")
    #     filtered["meta"]["commit"]["branch"] = commit.get("branch")
    #     filtered["meta"]["commit"]["authorName"] = commit.get("authorName")

    return data;

from helpers.tools.write_debug_file import write_debug_file
from currents.get_run_details import get_run_details
from currents.get_project_runs import get_previous_run

def get_run_data(current_run_id, api_key, debug_mode=False):
    print("📦 Get test runs...")
    print(f"    ↪ current run id: {current_run_id}")
    
    current_run_details = get_run_details(current_run_id, api_key)
    previous_run_details = get_previous_run(current_run_id)
    print(f"    ↪ previous run id: {previous_run_details['runId']}")

    if debug_mode:
        write_debug_file("previous_run_details.json", previous_run_details)
        write_debug_file("current_run_details.json", current_run_details)
    
    return current_run_details, previous_run_details
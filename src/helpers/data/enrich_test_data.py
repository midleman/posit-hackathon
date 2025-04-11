
from currents.get_test_history import get_test_history
from helpers.tools.write_debug_file import write_debug_file

def enrich_test_data(test_run_diff, current_run_details, debug_mode=False):
    still_failing = test_run_diff.get("Still Failing", [])
    if still_failing:
        for test in still_failing:
            group_id = test.get("groupId")
            test_name = test.get("name")
            spec = test.get("spec")
            run_timestamp = current_run_details.get("createdAt")
            
            if test_name and spec and run_timestamp:
                test_history = get_test_history(spec, test_name, run_timestamp, group_id)
                test["history"] = test_history
                
                if debug_mode:
                    safe_test_name = test_name.replace("/", "_").replace(">", "_").replace(" ", "_")
                    write_debug_file(f"test_history_{group_id}_{safe_test_name}.json", test_history)
    
    return test_run_diff
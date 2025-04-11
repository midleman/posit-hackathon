from helpers.tools.write_debug_file import write_debug_file
from currents.get_test_results_for_run import get_test_results_for_run

def get_run_test_results(current_run_id, previous_run_id, debug_mode=False):
    print("🧪 Get test results...")
    current_run_tests = get_test_results_for_run(current_run_id)
    previous_run_tests = get_test_results_for_run(previous_run_id)
    
    if debug_mode:
        write_debug_file("current_run_tests.json", current_run_tests)
        write_debug_file("previous_run_tests.json", previous_run_tests)
    
    return current_run_tests, previous_run_tests


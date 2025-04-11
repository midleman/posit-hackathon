
import os
from dotenv import load_dotenv
from helpers.data.get_run_test_results import get_run_data
from helpers.data.get_test_data import get_run_test_results
from helpers.data.enrich_test_data import enrich_test_data
from helpers.data.compare_test_results import compare_test_results
from helpers.tools.reset_output_dir import reset_output_dir
from helpers.tools.write_debug_file import write_debug_file
from helpers.tools.is_debug_mode import is_debug_mode
from helpers.llm.analyze_test_results import analyze_test_results

# Configuration
def load_config():
    load_dotenv()
    return {
        "currents_api_key": os.getenv("CURRENTS_API_KEY"),
        "currents_project_id": os.getenv("CURRENTS_PROJECT_ID"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        # toggle scenario
        "currents_current_run_id": 'd2d5a69185f2ca69'  # new tests
        # "currents_current_run_id": '8d295e14f8b6168c'  # 12 resolved, 2 still failing
        # "currents_current_run_id": 'c38c1f8033d08338'  # passing" scenario
        # "currents_current_run_id": 'b5b38a6560f9218d'  # persistent failure 6x
        # "currents_current_run_id": '324ac53e1fc63ec9'  # new failure
        # "currents_current_run_id": 'cd6f705cb1aed1d0'  # 12 new failures, 2 still failing
        # "currents_current_run_id": 'd2d5a69185f2ca69'  # new test
    }

# Main function
def main():
    debug_mode = is_debug_mode()
    reset_output_dir()
    
    # Load configuration
    config = load_config()
    
    # Get run data
    current_run_details, previous_run_details = get_run_data(
        config["currents_current_run_id"], 
        debug_mode
    )
    
    # Get run test results
    current_run_tests, previous_run_tests = get_run_test_results(
        config["currents_current_run_id"], 
        previous_run_details["runId"], 
        debug_mode
    )
    
    # Compare and enrich test results
    test_run_diff = compare_test_results(previous_run_tests, current_run_tests)
    test_run_diff = enrich_test_data(test_run_diff, current_run_details, debug_mode)
    
    if debug_mode:
        write_debug_file("test_run_diff.json", test_run_diff)
    
    # Analyze results with OpenAI
    analysis = analyze_test_results(test_run_diff, current_run_details, config["openai_api_key"])
    print("\n\n", analysis)

if __name__ == "__main__":
    main()

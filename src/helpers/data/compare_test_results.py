from typing import List, Dict

TestResult = Dict[str, str]  # Expecting {'testId': str, 'status': 'PASSED' | 'FAILED'}

def compare_test_results(
    previous: List[TestResult], current: List[TestResult]
) -> Dict[str, List[TestResult]]:
    previous_map = {test['testId']: test for test in previous}
    result = {
        "Resolved": [],
        "Still Failing": [],
        "New Failures": [],
        "New Tests": [],
    }

    for current_test in current:
        test_id = current_test['testId']
        prev_test = previous_map.get(test_id)

        if not prev_test:
            result["New Tests"].append(current_test)
        else:
            if prev_test['status'] == 'failed' and current_test['status'] == 'failed':
                result["Still Failing"].append(current_test)
            elif prev_test['status'] == 'failed' and current_test['status'] == 'passed':
                result["Resolved"].append(current_test)
            elif prev_test['status'] == 'passed' and current_test['status'] == 'failed':
                result["New Failures"].append(current_test)

    return result
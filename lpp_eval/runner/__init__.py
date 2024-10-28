import shutil
from typing import Optional, Tuple
from ..config import OUTPUT_DIR, TEST_MAP
from .test_runner import TestResult, run_extract, run_tests


# Implementation of process_submission function
def process_submission(project_id: str, report_type: str) -> None:
    print(f"Processing {project_id} {report_type}")
    submission_root = OUTPUT_DIR / project_id / report_type

    if report_type not in TEST_MAP:
        print(f"Unknown report type: {report_type}")
        return

    test_names = TEST_MAP.get(report_type)

    shutil.rmtree(str(submission_root.resolve()), ignore_errors=True)
    submission_root.mkdir(parents=True, exist_ok=True)

    # Extract source code
    root = run_extract(submission_root)
    # print(f"Root: {root}")
    best_result: Tuple[Optional[TestResult], str, int] = (None, "", 0)
    for test_name in test_names:
        result = run_tests(root, test_name)
        passed_count = len([r for r in result.summary if r[1] == "passed"])
        # print(f"{test_name}: {passed_count}/{len(result.summary)}")
        if passed_count >= best_result[2]:
            best_result = (result, test_name, passed_count)

    # print(f"Best test: {best_result[1]} ({best_result[2]}/{len(result.summary)})")

    best_result_name = best_result[1]
    best_result_info = best_result[0]

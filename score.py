from dataclasses import dataclass
from typing import Dict, Optional

from models import Submission


def program01score(input_data: Dict[str, bool], submission: Submission) -> float:
    # 011 + 11p + 11pp + 13 + 14 + 15a + 18 + 19p
    can_compile = input_data.get("test_compile", False)
    case_ids = ["011", "11p", "11pp", "13", "14", "15a", "18", "19p"]
    score_cases = [f"test_run[sample{case_id}.mpl]" for case_id in case_ids]
    pass_count = sum(1 for case in score_cases if input_data.get(case, False))
    score = pass_count / len(score_cases) * 2  # 0 to 2 points
    extra_score = (
        pass_count / len(score_cases) if submission.testcase_id == "01test_ex" else 0
    )  # extra 0 to 1 point
    any_passed = 1 if pass_count > 0 else 0  # 1 point if any test passed
    compile_score = 1 if can_compile else 0  # 1 point for compilation
    submission_score = 1  # 1 point for submission
    total_score = score + extra_score + any_passed + compile_score + submission_score
    return total_score


def program02score(input_data: Dict[str, bool], submission: Submission) -> float:
    # 26a + 11pp + 15a + 18 + 21 + 25t + 28p + 29p
    can_compile = input_data.get("test_compile", False)
    case_ids = ["26a", "11pp", "15a", "18", "21", "25t", "28p", "29p"]
    pass_count = sum(
        1
        for case in case_ids
        if input_data.get(f"test_run[sample{case}.mpl]", False)
        and input_data.get(f"test_idempotency[sample{case}.mpl]", False)
    )
    score = pass_count / len(case_ids) * 2  # 0 to 2 points
    any_passed = 1 if pass_count > 0 else 0  # 1 point if any test passed
    compile_score = 1 if can_compile else 0  # 1 point for compilation
    submission_score = 1  # 1 point for submission
    total_score = score + any_passed + compile_score + submission_score
    return total_score


def program03score(input_data: Dict[str, bool], submission: Submission) -> float:
    # 11 + 14p + 16 + 18 + 29p + 31p + 33p + 35
    can_compile = input_data.get("test_compile", False)
    case_ids = ["11", "14p", "16", "18", "29p", "31p", "33p", "35"]
    score_cases = [f"test_cr_run[sample{case_id}.mpl]" for case_id in case_ids]
    pass_count = sum(1 for case in score_cases if input_data.get(case, False))
    score = pass_count / len(score_cases) * 2  # 0 to 2 points
    any_passed = 1 if pass_count > 0 else 0  # 1 point if any test passed
    compile_score = 1 if can_compile else 0  # 1 point for compilation
    submission_score = 1  # 1 point for submission
    total_score = score + any_passed + compile_score + submission_score
    return total_score


def program04score(input_data: Dict[str, bool], submission: Submission) -> float:
    # 11 + 13 + 14p + 15 +16 + 17 + 18 + 19p + 35
    can_compile = input_data.get("test_compile", False)
    case_ids = ["11", "13", "14p", "15", "16", "17", "18", "19p", "35"]

    score_cases = [f"test_mpplc_run[sample{case_id}.mpl]" for case_id in case_ids]
    pass_count = sum(1 for case in score_cases if input_data.get(case, False))

    score = pass_count / len(score_cases) * 2  # 0 to 2 points
    any_score_passed = 1 if pass_count > 0 else 0  # 1 point if any test passed
    compile_score = 1 if can_compile else 0  # 1 point for compilation
    submission_score = 1  # 1 point for submission
    total_score = score + any_score_passed + compile_score + submission_score
    return total_score


@dataclass
class TestResult:
    summary: Dict[str, bool]
    submission: Submission


def grand_score(
    input_data: Dict[str, TestResult],
) -> float:
    total_score = 0.0
    for testsuite, test_result in input_data.items():
        if testsuite == "program01":
            total_score += program01score(test_result.summary, test_result.submission)
        elif testsuite == "program02":
            total_score += program02score(test_result.summary, test_result.submission)
        elif testsuite == "program03":
            total_score += program03score(test_result.summary, test_result.submission)
        elif testsuite == "program04":
            total_score += program04score(test_result.summary, test_result.submission)
    return total_score

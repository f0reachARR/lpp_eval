from dataclasses import dataclass
from pathlib import Path
from typing import List
import lpp_collector

# Too dirty work...
TEST_CASE_DIR = Path(lpp_collector.__file__).parent / "testcases"


def get_testcase(testsuite: str, basename: str):
    testsuite_dir = f"input{testsuite[0:2]}"
    path = TEST_CASE_DIR / testsuite_dir / f"{basename}.mpl"
    return path.read_text()


@dataclass
class TestcasePair:
    name: str
    test_input: str
    test_output: str


def create_testcase_result_pair(testsuite: str, result_dir: Path) -> List[TestcasePair]:
    all_outputs = result_dir.glob("*.out")
    pairs = []
    for output in all_outputs:
        basename = output.stem
        test_input = get_testcase(testsuite, basename)
        test_output = output.read_text()
        pairs.append(TestcasePair(basename, test_input, test_output))

    return pairs

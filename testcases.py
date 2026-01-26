from dataclasses import dataclass
from pathlib import Path
from typing import List
import lpp_collector

# Too dirty work...
TEST_CASE_DIR = Path(lpp_collector.__file__).parent / "testcases"


def get_testcase(testsuite: str, basename: str):
    testcase_num = int(testsuite[1:2])
    # num = 2 -> dir target are input02, input01
    targets = [f"input{str(i).zfill(2)}" for i in range(1, testcase_num + 1)]
    for target in targets:
        path = TEST_CASE_DIR / target / f"{basename}.mpl"
        if path.exists():
            return path.read_text()
    if testcase_num == 4:
        return ""
    raise FileNotFoundError(f"Testcase {basename} not found in {testsuite}")


def get_testcase_expect(testsuite: str, basename: str, type: str):
    path = TEST_CASE_DIR / testsuite / "test_expects" / f"{basename}.{type}"
    if not path.exists():
        return ""
    return path.read_text()


@dataclass
class TestcasePair:
    name: str
    test_input: str
    test_output: str
    test_expect_stdout: str
    test_expect_stderr: str


def create_testcase_result_pair(testsuite: str, result_dir: Path) -> List[TestcasePair]:
    all_outputs = result_dir.glob("*.out")
    pairs = []
    for output in all_outputs:
        basename = output.stem
        if basename.endswith(".mpl"):
            basename = basename[:-4]
        test_input = get_testcase(testsuite, basename)
        test_output = output.read_text()
        test_expect_stdout = get_testcase_expect(testsuite, basename, "stdout")
        test_expect_stderr = get_testcase_expect(testsuite, basename, "stderr")
        pairs.append(
            TestcasePair(
                basename,
                test_input=test_input,
                test_output=test_output,
                test_expect_stdout=test_expect_stdout,
                test_expect_stderr=test_expect_stderr,
            )
        )

    return pairs


def shorten_testcase(name: str) -> str:
    if name.startswith("test_idempotency["):
        return f"id[{name[16:-1]}]".replace(".mpl", "").replace("sample", "")
    elif "[" in name and "]" in name:
        start = name.index("[")
        end = name.index("]")
        return name[start + 1 : end].replace(".mpl", "").replace("sample", "")
    return name

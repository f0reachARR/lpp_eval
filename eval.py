from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import List, Tuple

TEST_DOCKER_IMAGE = os.getenv("TEST_DOCKER_IMAGE")
TEST_TEMP_DIR = Path(os.getenv("TEST_TEMP_DIR", "/tmp")).resolve()


def _call_container(target_path: Path, args: List[str], timeout=30):
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    run_args = [
        "run",
        "-it",
        "--rm",
        "-v",
        f"{target_path}:/workspaces",
        "-v",
        f"{TEST_TEMP_DIR}:/lpp/data",
        "-w",
        "/workspaces",
        "--env",
        f"TARGET_UID={os.getuid()}",
        "--env",
        f"TARGET_GID={os.getgid()}",
        "--memory=512m",
        "--cpus=0.5",
        TEST_DOCKER_IMAGE,
        *args,
    ]

    result = subprocess.run(["docker", *run_args], timeout=timeout, capture_output=True)

    return (
        result.returncode,
        result.stdout.decode("utf-8"),
        result.stderr.decode("utf-8"),
    )


def run_extract(target_path: Path) -> Path:
    cmd = [
        "bash",
        "/extract.bash",
    ]

    _call_container(target_path, cmd, timeout=10)

    # Determine root directory of source code
    ## Step1. Find Makefile in root or sub directory
    makefile_list = list(target_path.glob("**/Makefile"))

    if len(makefile_list) == 1:
        return makefile_list[0].parent
    elif len(makefile_list) > 1:
        raise Exception("Multiple Makefiles found")

    ## Step2. Find c files and return most shortest path
    c_files = list(target_path.glob("**/*.c"))
    c_files_dir = [c.parent for c in c_files]
    c_files_dir.sort(key=lambda x: len(x.parts))

    if len(c_files_dir) == 0:
        raise Exception("No C files found")

    return c_files_dir[0]


@dataclass
class TestResult:
    summary: List[Tuple[str, str]]
    stdout: str


def run_tests(
    target_path: Path, test_dir: str, timeout=30, include_cases: List[str] = []
) -> TestResult:
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "lpptest",
        test_dir,
        "--json-report",
        "--json-report-file=/lpp/data/result.json",
    ]

    if len(include_cases) > 0:
        cmd.append("-k")
        cmd.append(" or ".join(include_cases))

    (returncode, stdout, stderr) = _call_container(target_path, cmd, timeout)

    if returncode != 0:
        raise Exception(f"Test failed: {returncode} {stdout} {stderr}")

    result_text = Path(TEST_TEMP_DIR / "result.json").read_text()
    result_json = json.loads(result_text)

    result_summary = []
    for test in result_json["tests"]:
        nodeid = test["nodeid"]
        case_name = nodeid.split("::")[-1]
        result_summary.append((case_name, test["outcome"]))

    return TestResult(result_summary, stdout)

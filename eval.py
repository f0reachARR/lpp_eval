import json
import os
from pathlib import Path
import subprocess

TEST_DOCKER_IMAGE = os.getenv("TEST_DOCKER_IMAGE")
TEST_TEMP_DIR = Path(os.getenv("TEST_TEMP_DIR", "/tmp"))


def run_evaluate_container(target_path: Path, test_dir: str, timeout=30):
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
        "lpptest",
        test_dir,
        "--json-report",
        "--json-report-file=/lpp/data/result.json",
    ]

    retcode = subprocess.call(["docker", *run_args], timeout=timeout)

    if retcode != 0:
        raise RuntimeError(f"Failed to run the evaluation container: {retcode}")

    result_text = Path(TEST_TEMP_DIR / "result.json").read_text()
    result_json = json.loads(result_text)

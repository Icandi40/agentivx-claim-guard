"""The committed BENCHMARK.md and README results must match what the script produces now."""

import re
import subprocess
import sys
from pathlib import Path

from benchmark.run import main

ROOT = Path(__file__).resolve().parent.parent


def test_benchmark_report_is_current() -> None:
    assert main(["--check"]) == 0


def test_readme_usage_example_runs_and_prints_what_it_says() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"```python\n(.*?)```", readme, re.DOTALL)
    assert block is not None
    code = block.group(1)
    assert len(code.strip().splitlines()) <= 10
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT
    )
    expected = [m.strip() for m in re.findall(r"#\s*->\s*(.*)", code)]
    printed = [line.strip() for line in done.stdout.splitlines()]
    for line in expected:
        assert line in printed

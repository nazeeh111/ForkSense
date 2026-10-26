"""Apply only candidate Flask source changes in a fresh evaluation repository.

The official test patch is held outside the agent workspace until evaluation.
Never use this command as an agent-visible repair verifier: it exposes tests and
feedback after the attempt. It is an offline final judge for a frozen pilot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from forksense import git as source_git


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-folder", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    folder = args.case_folder.resolve()
    candidate = args.candidate.resolve()
    out = args.output.resolve()
    if out.exists():
        parser.error("output must be fresh")
    out.mkdir(parents=True)
    metadata = json.loads((folder / "metadata.json").read_text())
    base = metadata["base_commit"]
    official = (folder / "test.patch").read_bytes()
    if hashlib.sha256(official).hexdigest() != metadata["test_patch_sha256"]:
        raise RuntimeError("official test patch changed")
    if git(candidate, "rev-parse", "HEAD").decode().strip() != base:
        raise RuntimeError("candidate HEAD differs from frozen base; leave repairs uncommitted")
    # Capture staged, unstaged and untracked source through a private Git index.
    # A final candidate must contain source changes only; test/config changes
    # cannot silently weaken the independent judge.
    try:
        candidate_patch, candidate_files = source_git.extract_patch(candidate, base, ["src/flask"])
    except source_git.GitError as exc:
        if "no source changes" not in str(exc):
            raise
        candidate_patch, candidate_files = b"", []
    (out / "candidate.patch").write_bytes(candidate_patch)
    repo = out / "repo"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(folder / "repo"), str(repo)], check=True)
    git(repo, "checkout", "--quiet", "--detach", base)
    if git(repo, "rev-parse", "HEAD").decode().strip() != base:
        raise RuntimeError("fresh judge differs from frozen base")
    if candidate_patch:
        git(repo, "apply", "--whitespace=nowarn", "-", data=candidate_patch)
    git(repo, "apply", "--whitespace=nowarn", "-", data=official)
    # Verify the exact issue regression and all dataset-recorded regressions.
    original_nodes = list(dict.fromkeys(metadata["FAIL_TO_PASS"] + metadata["PASS_TO_PASS"]))
    # Parameter node IDs can change between historical pytest versions.
    # Expand each recorded function to all its parameters on this pinned host.
    tests = list(dict.fromkeys(node.split("[", 1)[0] for node in original_nodes))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    started = time.monotonic()
    # Preserve a venv's executable path; resolving its symlink loses pyvenv.cfg.
    command = [str(args.python.absolute()), "-m", "pytest", "-q", "--tb=short", "-W", "ignore::DeprecationWarning", *tests]
    try:
        proc = subprocess.run(command, cwd=repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=args.timeout)
        code, output, status = proc.returncode, proc.stdout, "completed"
    except subprocess.TimeoutExpired as exc:
        code, output, status = None, str(exc.stdout or ""), "timeout"
    receipt = {"instance_id": metadata["instance_id"], "base_commit": base,
               "evaluation_kind": metadata["evaluation_kind"], "candidate_patch_sha256": hashlib.sha256(candidate_patch).hexdigest(),
               "official_test_patch_sha256": metadata["test_patch_sha256"], "test_nodes": tests,
               "dataset_test_nodes": original_nodes, "parameter_scope": "all parameters of dataset-recorded functions",
               "command": command, "pythonpath": env["PYTHONPATH"], "elapsed_seconds": time.monotonic() - started,
               "returncode": code, "status": status, "resolved": code == 0,
               "candidate_files": candidate_files,
               "untracked_candidate_files_included": git(candidate, "ls-files", "--others", "--exclude-standard").decode().splitlines(),
               "source_only_evaluation": True}
    (out / "pytest.txt").write_text(output)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"instance_id": receipt["instance_id"], "resolved": receipt["resolved"], "returncode": code, "output": str(out)}))


if __name__ == "__main__":
    main()

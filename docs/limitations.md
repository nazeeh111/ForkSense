# Limits and trust boundary

ForkSense v0.1.0 is a research preview for trusted local repositories. It provides an inspectable experiment engine, not proof that its decisions improve coding agents across real projects.

## Evidence limits

- The controlled study uses nine held-out synthetic tasks from three cause families, oracle-informed forecasts and prepared repairs. It has zero model calls. Its resolution rates are not agent scores.
- A recorded live Codex repair establishes one working path on a controlled fixture. It does not establish autonomous plan quality or superiority over ordinary Codex.
- The learned cost model did not outperform the heuristic. It does not learn correctness, calibrated likelihoods or optimal branching/stopping.
- Repeated seeds reuse the same tasks. Three family clusters provide little support for population-wide statistical conclusions.
- The root UCT proxy is weaker than a full search implementation and must not stand in for agent-mcts, Saplings or SWE-Search performance.
- A corrected live pilot repeats one Flask routes issue three times per mode: both ordinary Codex and ForkSense resolve 3/3 official evaluations at about 69.8 seconds. Manual-plan authoring cost is unmeasured, the exact configured model identifier was not independently recorded, and ordinary logs are truncated. Broader real-repository, parallel-agent and full tree-search comparisons remain open. The pilot is not a SWE-bench score.

## Worktrees isolate edits, not machines

`--trust-repo` is required because tests, diagnostic commands and installed agents execute on the host. Git worktrees share Git metadata and can access host files and services under ordinary permissions. They are not containers or security sandboxes. Do not use this mode to evaluate malicious repositories or untrusted patches.

The native agent CLI has its own account, configuration, hooks, tools and permission system. ForkSense supplies ordinary read-only/workspace-write modes and avoids permission-bypass flags. It cannot guarantee that every future CLI version or user configuration behaves identically. Native denials remain denials.

ForkSense does not read credential stores. It strips ambient provider keys and tokens from child environments, but preserves `HOME` so installed CLIs can use their own native login. This is not a guarantee that arbitrary trusted-host programs cannot read files. Project commands that require custom environment variables need a reviewed setup; those variables are not forwarded automatically.

There is no ForkSense telemetry or hosted report service. An invoked agent provider still has its own network behavior and data policy. Review outputs before sharing them: code, test data, paths or secrets emitted by trusted commands can appear in logs. Public evidence exports remove raw transcripts and machine-specific paths, but ordinary local reports are not automatically sanitized.

## Verification is only as strong as its contract

The verifier must represent the requested behavior and include independent tests. A patch may pass weak tests while still being wrong. Agent-generated tests cannot be the sole judge.

Candidates are restricted to declared source paths and checked for conventional test/fixture names. Unusual test layouts or executable source masquerading as a test still require user judgment. Test files in the base worktree are preserved during fresh verification; a candidate's modified tests do not become the judge.

External regular files explicitly referenced in verifier arguments are copied and hashed before baseline execution. The original paths execute to preserve `__file__`, sibling imports and fixture discovery. Hashes of the originals and evidence copies are checked before and after verification. Direct executable verifier scripts are included. Explicit external verifier directories are unsupported. Imported packages, dynamically discovered files, services, interpreter behavior and all dependencies are not recursively frozen. A hermetic evaluation environment is not implemented.

## Budgets and cleanup

The seconds budget bounds child executions against remaining elapsed time. Git operations have separate 15-second limits, and cleanup, file capture and report rendering can add overhead. It is not an exact global deadline.

Token caps are soft post-turn checks. An in-flight CLI call can exceed them. Missing usage is `null`, not zero; a token cap prevents subsequent calls when usage is unknown. Input counts may include cached tokens and cannot be treated as fresh-token spend or a dollar invoice.

Captured logs are bounded. Verbose output can be truncated or terminated, and an output-limit result is inconclusive even if its process exited zero. Candidate patches are size-limited; a worktree can be retained if a complete diff cannot be saved. Read the report before manually removing retained recovery material.

Process-group termination and Git child cleanup target POSIX systems. The current test matrix covers Linux and macOS. Windows behavior has not been verified. The tool does not restore arbitrary process state, background services or hidden model reasoning.

## Compatibility and workflow

Python 3.11+ and Git are required. Codex was exercised locally; the optional Claude Code adapter has not been executed because the CLI was unavailable. Documented options can change, so check native `--help` and report version-specific failures.

The repository must be clean, including untracked files, and have a commit. ForkSense does not automatically stash, discard or commit your work. Ignored files and local virtual environments are not copied into worktrees. Install dependencies so your verifier works from a fresh checkout.

Acceptance checks the original commit, clean state and exact patch bytes, then checks applicability before applying. It does not rerun the complete verifier, commit or push. Review and test the applied change before making your own commit.

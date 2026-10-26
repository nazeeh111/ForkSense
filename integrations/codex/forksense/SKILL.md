---
name: forksense
description: Use ForkSense for a trusted local repository when competing explanations justify executable diagnostic experiments before repair.
---

# ForkSense

Use the installed `forksense` CLI to investigate consequential uncertainty. Ordinary clear fixes do not need branching. This is an external experiment workflow, not a fork of your hidden reasoning or current session.

1. Inspect `forksense doctor --repo REPO`. Require an existing committed clean repository; preserve unrelated work. Do not commit the user's work just to satisfy this requirement.
2. Ask the user to choose a meaningful independent verifier and source change scope if they are missing. Read `forksense plan --help`. Propose a plan with an output path outside the target repo, an explicit verifier command and repeated `--editable` source paths. Only pass `--trust-repo` when the user has authorized execution of this trusted code.
3. Run `forksense inspect PLAN` and review commands, priors, predicted likelihoods, budget and test independence. A generated plan is a proposal. Fix malformed or misleading probes before running.
4. Run `forksense run PLAN --repo REPO --output FRESH_OUTPUT --agent codex --seconds 180 --agent-calls 2 --max-experiments 3 --trust-repo`. Adjust the explicit budget to the user's authority. The CLI keeps the default configured model. Native Codex permission controls stay in effect.
5. Read `report.json` and `report.html`. Explain observed evidence, failed attempts and limits. Success requires an independently verified patch. Hypothesis weights alone never establish success.
6. Show the diff using `forksense accept REPORT --repo REPO`. Apply with `--yes` only if patch application is authorized. This does not commit, push or publish.

Never add API keys, bypass flags, credentials, external services or automatic patch application. Worktrees isolate edits, not arbitrary program side effects. Use only trusted local repositories, or arrange a real external sandbox separately.

# Adoption through useful evidence

The first useful audience is developers already using a coding CLI who repeatedly encounter two or more plausible causes for the same failure. A concrete reproduction is the entry point: the same failing test, the same source base, one discriminating observation and a reviewable patch.

## Make first use inexpensive

Keep the no-account demo as the opening path. It should explain the failure and make the executed probe, independent tests and acceptance step easy to find. Follow it with a live-agent example that uses the developer's existing login and reports all additional model calls and costs.

Prefer source-level experiments that can finish quickly in the existing project environment. When the original test already passes or a direct repair is sufficient, avoid unnecessary branching. A tool earns repeat use when it saves work on a real uncertainty, not when it produces a larger tree.

## Invite reproducible cases

Useful contributions include:

- A clean base commit and minimal task description.
- A failing reproduction and independent tests written before repair.
- Two plausible explanations that can be separated by a cheap observation.
- An ordinary-agent run and a ForkSense run under the same stated budget.
- Exact commands, native CLI versions, failures, elapsed time and reported usage.

Use the benchmark issue template to make those cases inspectable. Keep private source, credentials and proprietary logs out of public reports. Retain failures and inconclusive cases alongside successful ones.

## Share results in context

Lead with one real debugging case and what its diagnostic established. Link the source, report and limits. Compare fairly to an ordinary installed agent, which is allowed to run its own diagnostics. Charge planning and probe overhead, and distinguish parallel wall time from total compute.

Participate in relevant discussions only when the case directly addresses the question and the maintainer or community welcomes it. No bulk outreach, artificial stars, automatic promotional issues, exaggerated performance claims or unsolicited repository changes. Publication of the project does not authorize messaging other people.

## Let evidence control the roadmap

Prioritize repeated independent reproductions, reliable CLI compatibility and a stronger real-task study over a hosted dashboard or a new orchestration hierarchy. A learned policy should replace the heuristic only after it improves held-out outcomes at comparable cost. Negative results belong in the release notes.

The immediate adoption asset is a tool that can be tried locally, inspected completely and removed without a service account. The next milestone is evidence that its extra experiments are worthwhile on tasks developers actually encounter.

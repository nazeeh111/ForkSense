# Third-party notices and research attribution

ForkSense's original source, controlled fixtures, brand SVGs and documentation are distributed under the [MIT license](LICENSE). The runtime package has no third-party Python dependencies. This release does not vendor third-party agent binaries, model weights, search-framework implementations or paper figures.

## Optional host tools

ForkSense invokes tools already installed by the user. Their own licenses, account terms and data policies continue to apply:

- [Git](https://git-scm.com/), for repository inspection, disposable worktrees and patch checking.
- [OpenAI Codex](https://github.com/openai/codex), through documented `codex exec` modes.
- [Claude Code](https://github.com/anthropics/claude-code), through documented `claude -p` modes; the adapter is locally unverified.
- [uv](https://github.com/astral-sh/uv), an optional installation/quickstart tool.

These tools are not included in the wheel. ForkSense is an independent project and is not endorsed by OpenAI or Anthropic. Product names identify compatibility targets.

## Research foundations

The [method document](docs/method.md) cites the original sources for rollout reuse, checkpoint comparison, tree search, runtime debugging and independent verification. In particular:

- Kim et al., [Scaling Test-Time Compute for Agentic Coding](https://arxiv.org/abs/2604.16529).
- Akewar and Ranjan, [RippleCP: Measuring Counterfactual Checkpoint Advantage in Coding Agents](https://arxiv.org/abs/2610.09088).
- [agent-mcts](https://pypi.org/project/agent-mcts/) and its [source repository](https://github.com/natsu0529/mcts-llm-agent).
- [Saplings](https://github.com/shobrook/saplings).
- Antoniades et al., [SWE-Search](https://arxiv.org/abs/2410.20285).
- Tao et al., [ExecCritic](https://arxiv.org/abs/2609.09133).
- Garg and Huang, [Debug2Fix](https://arxiv.org/abs/2602.18571).
- Alaboudi and LaToza, [Using Hypotheses as a Debugging Aid](https://arxiv.org/abs/2005.13652).

These works are cited as prior art and motivation. Their reported performance numbers are not ForkSense measurements. No paper text, figures, reference solutions or framework code are redistributed here. In particular, the noncommercial license associated with the test-time-compute paper is not treated as a license to transplant its content into this MIT project.

[SWE-bench](https://github.com/SWE-bench/SWE-bench) supplies the reference task format and official evaluation framework discussed in the documentation. The controlled benchmark in this repository is original synthetic material and is not a SWE-bench result. The selected Flask issue pilot preserves upstream commit, issue and test-patch identities. Flask source and tests are fetched externally, retain their BSD-3-Clause terms, and are attributed in [the retained Flask license](benchmarks/real_cases/FLASK_LICENSE.txt). The dataset-wide license was not independently established; original issue prose and official test patches are obtained at runtime rather than bundled in the public evidence.

## Presentation tools and assets

ForkSense's editable diagrams and chart geometry are original source. The chart script optionally uses [Pillow](https://python-pillow.org/) to rasterize its own geometry; Pillow is a development tool and is not included in the runtime wheel.

The demo media is accompanied by retained capture/encoding provenance under [docs/assets/demo-source](docs/assets/demo-source). Screenshots and footage show actual local project output. Presentation assets and controlled fixtures must not be mistaken for comparative agent-performance evidence.

## CI dependencies

The workflow pins official [actions/checkout](https://github.com/actions/checkout) and [actions/setup-python](https://github.com/actions/setup-python) revisions. They execute in GitHub Actions and are not incorporated into the Python package. Building uses setuptools; installation and test tooling retain their own licenses.

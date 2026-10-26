# Optional agent skills

These opt-in skills call the same external CLI. They do not intercept model state, run hooks automatically, install themselves, or change authentication.

- Codex: copy `codex/forksense` into the trusted repository's `.agents/skills/forksense` folder, or your own user skill directory if preferred.
- Claude Code: copy `claude-code/forksense` into the trusted repository's `.claude/skills/forksense` folder.

Install the CLI first using the root quickstart. Read each skill before enabling it. No global configuration is changed by this repository. Keep skills outside the source checkout used for experiments, or commit your intentional project configuration before running; ForkSense requires a clean tree.

Codex uses documented `codex -a never exec --ephemeral --sandbox workspace-write --json`. Claude uses documented `claude -p --output-format json` with scoped tools, disabled hooks, explicit empty MCP configuration and ordinary permission mode. Claude's `--bare` requires API authentication and is intentionally not used. The Claude adapter is not a claim of live compatibility on a machine without that CLI.

Sources: [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), [Codex skills](https://developers.openai.com/codex/skills), [Claude headless CLI](https://code.claude.com/docs/en/headless), [Claude skills](https://code.claude.com/docs/en/skills).

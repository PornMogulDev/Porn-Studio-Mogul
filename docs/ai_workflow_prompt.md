# AI-assisted workflow prompt

Copy the prompt below into a new chat from the PSM checkout. Fill in the parts you know. A save, preset, seed, log excerpt, or exact click sequence is often enough to start.

## Implementation prompt

> Work on one PSM workflow. Read `AGENTS.md` first and follow the established setup and verification commands.
>
> - **Workflow** — [Player action or simulation step]
> - **Current behavior** — [What happens and where it goes wrong]
> - **Expected behavior** — [What the player should see and what state should be saved]
> - **Reproduction** — [Steps, save, preset, seed, logs, or a test. Include the build and platform if relevant.]
> - **Constraints** — [Game rules, supported saves or presets, and any scope limits]
>
> 1. Check the working tree and preserve existing edits. Trace the workflow from its normal entry point through the relevant presenter, service, and database operation. Identify where the rule is applied and who owns the commit and UI refresh.
> 2. Reproduce the behavior using isolated player data. Use the development game for the production loop or a small explicit fixture for a rule that depends on particular data. When feasible, add a focused regression check and verify that it fails for the reported reason before editing the implementation.
> 3. Make the smallest change that solves the workflow. Reuse the existing rules and services so preview and commit agree where applicable. For stateful changes, check failure and retry behavior, signal delivery after commit, and the round trip for existing saves or presets. If a test and the implementation disagree about a gameplay rule, use the design notes and surrounding behavior to establish the intended rule before changing the test.
> 4. Run the focused check and the full suite. For a production-loop change, also run `python src/dev_game.py --smoke`. Update the closest documentation if a command, a game rule, or a contract between layers changed.
> 5. Report what was reproduced, the change, and the commands and results that verify it. Call out any remaining uncertainty or platform check you could not perform.

## Review prompt

> Review this change against the original workflow and its expected behavior. Start with the diff and trace it through the normal entry point. Look for regressions in saved state, failed or repeated operations, stale UI callbacks, and older saves or presets where applicable. Check whether the tests exercise the behavior that could fail. Report actionable findings with file and line references, the player impact, and a reproduction or test when possible.

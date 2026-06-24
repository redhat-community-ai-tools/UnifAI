# Revision Loop Protocol

This is a parameterized protocol. The mode file sets the following variables before invoking this loop:

- **REVIEWER_SKILL**: path to the reviewer skill file
- **AUTHOR_SKILL**: path to the author/producer skill file
- **ITERATION_COUNTER**: which state field to increment (`Design Iterations` / `Code Iterations` / `QA Iterations`)
- **MAX_ITERATIONS**: 2
- **VERDICT_APPROVE**: the exact token that means approval (e.g., `CLEAN`, `APPROVE`, `PASS`)
- **VERDICT_BLOCK**: list of tokens that block (e.g., `NEEDS_REVISION`, `REJECT`)
- **PHASE_HEADER**: the header to use for the revised output (e.g., `## PHASE 1: DESIGN (Revision <N>)`)
- **REVIEW_HEADER**: the header to use for the re-review (e.g., `## PHASE 2: DESIGN REVIEW`)

## Execution

After the reviewer produces output, locate the `PIPELINE_VERDICT:` line. The token after the colon is the verdict.

```
IF verdict == VERDICT_APPROVE:
    Update state: Blocking Verdict = NONE
    EXIT this loop. Proceed to the next phase (or pipeline summary).

IF verdict matches any VERDICT_BLOCK token:
    Update state: Blocking Verdict = <verdict>
    Update state: Feedback Items To Address = <every item from the review>
    Increment ITERATION_COUNTER.

    IF ITERATION_COUNTER > MAX_ITERATIONS:
        Update state: EXIT_STATUS = REVISION_LIMIT
        STOP. Display the pipeline state. Tell the user:
        "The <artifact> has been revised <MAX_ITERATIONS> times but the reviewer still has concerns.
        Here are the remaining issues: <list them>
        You can run `/pipeline debug` to start a debug session, or provide guidance."
        WAIT for user response. Do NOT continue.

    ELSE:
        Display: "## REVISION LOOP <N>/<MAX_ITERATIONS>: Addressing Feedback"
        Display: "The reviewer identified the following issues that must be resolved:"
        List EVERY feedback item as a numbered checklist.

        THEN execute ALL steps in order:

        Step A: Read the AUTHOR_SKILL file using the Read tool.
        Step B: Apply the instructions from that skill file. Orchestrator rules remain in effect.
        Step C: For EACH feedback item, state what you are changing and why.
        Step D: Produce the revised artifact under PHASE_HEADER.
                - For design artifacts: produce the COMPLETE revised design.
                - For code artifacts: apply fixes to files, then present a summary of changed files.
        Step E: Verify every feedback item is addressed by checking them off.
        Step F: Update and display the pipeline state tracker.
        Step G: If REVIEWER_SKILL uses Scout + Judge dispatch (arch-reviewer.md or code-reviewer.md),
                follow the Scout + Judge Re-Review Extension below. Otherwise continue to Step G-alt.
        Step G-alt: Read the REVIEWER_SKILL file using the Read tool.
        Step H: Apply the instructions from that skill file. Orchestrator rules remain in effect.
        Step I: Re-review the revised artifact. Present under REVIEW_HEADER.
        Step J: Locate the new PIPELINE_VERDICT: line. Return to the top of this protocol.
```

## Scout + Judge Re-Review Extension

When the REVIEWER_SKILL is `arch-reviewer.md` or `code-reviewer.md`, Steps G–I are replaced with the Agent Dispatch Protocol from `pipeline.md`:

1. Re-run the Scout on the updated diff (scope = files changed in the revision).
2. Receive the fresh Evidence Pack.
3. Include the previous review's findings in the Judge prompt so it can perform Revision Loop Verification (§8 in code-reviewer).
4. Spawn the appropriate Judge with the fresh evidence pack + previous findings.
5. Present the Judge's output under REVIEW_HEADER.
6. Locate the new `PIPELINE_VERDICT:` line and return to the top of this protocol.

The Scout must re-run because the code has changed — the previous evidence pack is stale.

## QA-Specific Extension

When the QA phase fails, separate failures into:
- **CODE BUGS**: issues in the implementation (Coder must fix)
- **TEST BUGS**: issues in the tests (QA will fix in next iteration)

If there are CODE BUGS:
1. Read `.cursor/skills/pipeline/phases/coder.md`. Apply its instructions.
2. Fix each CODE BUG, stating what changed and why.
3. Present fixes under: `## PHASE 3: IMPLEMENTATION (QA Fix <N>)`
4. Read `.cursor/skills/pipeline/phases/code-reviewer.md`. Apply its instructions.
5. Review ONLY the code changes just made (not the full codebase).
6. Present under: `## PHASE 4: CODE REVIEW (QA Fix <N>)`
7. If code review verdict is not approval, apply fixes immediately and present under `## PHASE 3: IMPLEMENTATION (QA Fix <N> - CR Fix)`. Do NOT loop code review again — proceed to QA re-run.

THEN (whether or not there were code bugs):
1. Read `.cursor/skills/pipeline/phases/qa.md`. Apply its instructions.
2. Fix any TEST BUGS, re-run all tests.
3. Present results under: `## PHASE 5: QA (Revision <N>)`
4. Locate the new `PIPELINE_VERDICT:` line and return to the top of this protocol.

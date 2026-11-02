# Contributing to Cerberus AI

## Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Code Style

- Backend: Black + Ruff + mypy
- Frontend: ESLint + Prettier

## Pentest-tool beginner guide

Whenever an external pentest tool is added, removed, or its setup or execution
changes, update `docs/HOW_TO_RUN_THE_TOOLS_AS_BEGINNER.md` in the same change.
Document whether it is real or simulated, its prerequisites, safe individual
and combined lab commands (or clearly state if no safe lab is available), and
any limitations. Update the lab runner and tests when appropriate; regenerate
and review `docs/how to run the tools as beginner.pdf` using
`scripts/render_beginner_tools_guide.py`. The backend tests check that every
registered external tool has a guide marker and that the PDF matches the
current guide source. A marker is a reminder, not a substitute for testing.

The same tool addition also requires updating `docs/REAL_RESULTS.md` and
`docs/real_results.json`, then regenerating `docs/real result.pdf`. Record a
real, timestamped result only after checking the target operator's permission,
scope and limits; otherwise state clearly that the tool was not tested. Update
the fixed public-test runner and its tests as appropriate. Public scans must
remain explicit, opt-in actions and must never be part of ordinary automated
tests. Tests check registered-tool coverage and the report source/data hash,
but cannot certify authorization or whether an online result is correct.

## Commit Messages

Follow conventional commits: feat:, fix:, docs:, style:, refactor:, test:, chore:

# AGENTS.md

afk-looper is the `afk` CLI. It has no runtime dependencies beyond the standard
library, and it shells out to `git`, `gh`, `claude` and `uv`.

- Everything in the repository is in English.
- Commits follow Conventional Commits, with no co-author trailer or attribution line.
- Tests run the CLI as a process against a real local git origin. Only `gh`, `claude`,
  `uv` and the macOS helpers are faked, in `tests/fakes/`. No unit tests.
- A comment is at most three lines, and says what is surprising.
- Run `uv run pytest` before pushing.

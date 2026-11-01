# afk-looper

`afk` works through a repository's `ready-for-agent` GitHub issues one at a time.
Claude Code implements an issue and only commits. A second agent reviews the
branch. `afk` owns the gate, the push, the pull request and the merge, and asks you
in the terminal when a human is needed.

**It merges to the default branch with no human reading the code.** Run it only on
repositories where you accept that.

## Install

Needs [uv](https://docs.astral.sh/uv/), `git`, `gh` (logged in) and `claude`.

```sh
uv tool install git+https://github.com/kryptamine/afk-looper
```

`afk` lands in `uv tool dir --bin`; `uv tool update-shell` adds that to your `PATH`.

## Use

Run from anywhere inside the target repository:

```sh
afk list      # show the labelled issues and which are blocked
afk run       # work through them, merging each
afk run --danger  # the same, with no permission checks on the agent
afk update    # upgrade afk itself to the latest commit on main
afk --version
```

At a prompt, reply with an answer, `skip` for the next issue, or `stop` to quit.

Work happens in a worktree beside the checkout (`../<repo>-afk`), and logs go to
`.afk-logs/` in the checkout. An issue with open blockers waits for them.

The terminal shows each phase, the agent's tool calls and failed results, the gate's
refusals, and each agent run's time and cost. The logs hold the full agent stream.

## Configure

An optional `.afk.toml` at the repository root. These are the defaults:

```toml
label = "ready-for-agent"
install = "make install"      # run before each issue
check = "make check"          # must pass before a merge
budget_usd = 30               # cap on one agent run; AFK_BUDGET_USD overrides it
allow = []                    # extra Claude tools, e.g. ["Bash(cargo *)"]
```

## Danger mode

`afk run --danger` passes `--dangerously-skip-permissions` to every agent run, so the
agent can do anything your user can on this machine, including what an issue's text
talks it into. `allow` is ignored. `git push` and the `gh pr` commands that change a
pull request stay denied, so the base branch still moves only through the gate. It is a flag and not a config key, because
`.afk.toml` lives in the repository the agent edits.

## The gate

A branch merges only when it is named `<type>/<kebab-summary>`, is clean, sits on top
of the default branch, has commits, carries no `Co-authored-by` trailer, and passes
`check`. It runs after the implementation and again after the review.

## Develop

```sh
uv run pytest
```

def implement_prompt(issue: int, base: str, check: str) -> str:
    return f"""\
You are working AFK on GitHub issue #{issue}, in a git worktree detached at origin/{base}.
A second agent reviews your branch, and it then merges with no human reading it.

1. Read the issue with `gh issue view {issue} --comments`, and any spec it links.
   AGENTS.md or CLAUDE.md, where present, governs how you work.
2. Cut a branch named <type>/<kebab-summary> and build every acceptance criterion, with
   tests. Commit by the repository's convention, with no co-author trailer or attribution
   line, and leave nothing uncommitted.
3. Make `{check}` pass.

You cannot push, open or merge a pull request, and you do not close the issue: afk does
that once you report done. A criterion that asks to record a result on the issue is done
with `gh issue comment`.

Decide for yourself wherever the spec, the code and the repository's rules give an answer
or a sensible default. Report status needs_human, with a self-contained question, only
when you are blocked on what a human alone can give: a decision the spec leaves open and
that is costly to get wrong, a credential or account, or a check in a real environment you
cannot reach. Never fake such a check or mark it done. Build everything else first, then ask.

When finished, report status done with pr_title (a commit-style subject) and pr_body
(why and how it was tested, no attribution, no closing keyword)."""


def review_prompt(issue: int, base: str, check: str) -> str:
    return f"""\
You review the branch checked out here before it merges with no human reading it.
Read issue #{issue} with `gh issue view {issue} --comments`, any spec it links, and
`git diff origin/{base}...HEAD`.

Check each acceptance criterion against the code and its tests, and the diff against the
repository's rules. Look for real defects: a criterion not met, a test that proves nothing,
a broken rule, a bug. Fix what you find in new commits on this branch, with no co-author
trailer, and keep `{check}` passing. Do not widen the scope or restyle working code.

Report status done when the branch is fit to merge, leaving pr_title and pr_body out.
Report needs_human, with a self-contained question, only for what a human alone can give."""

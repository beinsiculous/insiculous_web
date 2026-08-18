#!/usr/bin/env bash
# PreToolUse hook (Bash matcher) for Claude Code and Kimi Code CLI: before a
# `git commit`, if the pending diff is big, require an adversarial code review
# (scripts/request-review.sh code ...) before committing.
#
#   --harness=claude (default)  deny via Claude's permissionDecision JSON
#   --harness=kimi              deny via stderr + exit 2 (kimi's block protocol)
#
# Silent (exit 0, no output) for: non-commit commands, non-repo dirs, repos
# without the adversarial-review skill marker (kimi hooks live in the GLOBAL
# config, so they fire in every project — the marker keeps them project-scoped),
# diffs under THRESHOLD changed lines, and commits prefixed with ADV_REVIEWED=1
# (set by the agent only after a code-mode review was adjudicated with the
# user, or the user explicitly skipped review). Otherwise DENIES the commit
# with instructions — informing alone can't stop the triggering command.
set -euo pipefail

THRESHOLD=100
HARNESS=claude
for arg in "$@"; do
    case "$arg" in
        --harness=claude|--harness=kimi) HARNESS="${arg#--harness=}" ;;
        *) echo "error: unknown argument '$arg'" >&2; exit 1 ;;
    esac
done
# The counterpart CLI that reviews this harness's work.
REVIEWER=kimi
[ "$HARNESS" = "kimi" ] && REVIEWER=claude

# Degrade gracefully where jq is missing (review-3 F1): a reminder gate must
# never break basic shell use on a machine without the dependency.
command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
# All matching runs against the command with quoted segments removed, so
# commit-message text can neither smuggle the ADV_REVIEWED=1 bypass
# (deion_assets review-1 F3) nor trigger the staging fallback below
# (review-1 F2).
stripped=$(printf '%s' "$cmd" | sed "s/'[^']*'//g; s/\"[^\"]*\"//g")
# Detect the commit itself on the RAW command so `bash -c "git commit ..."` /
# `eval "git commit ..."` cannot slip past by hiding it inside quotes
# (FortKnight review-1 F2). A commit message that merely mentions "git commit"
# trips the gate too — a harmless false positive.
case "$cmd" in
    *"git commit"*) ;;
    *) exit 0 ;;
esac
# Bypass token counts only as a leading env assignment (or one right after
# && / ;) — never as free text inside a commit message (review-3 F3).
case "$stripped" in
    "ADV_REVIEWED=1 "* | *"&& ADV_REVIEWED=1 "* | *"; ADV_REVIEWED=1 "*) exit 0 ;;
esac

top="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$top"
# Repo guard: only repos that carry the adversarial-review skill participate.
[ -f .kimi-code/skills/adversarial-review/SKILL.md ] && : || \
[ -f .claude/skills/adversarial-review/SKILL.md ] || exit 0

changed_lines() {
    # numstat: insertions<TAB>deletions<TAB>path; "-" for binary counts as 0
    git diff ${1:-} --numstat 2>/dev/null | awk '{a += $1 + $2} END {print a + 0}'
}

lines=$(changed_lines --cached)
# When this command also stages (`commit -a` or a `git add` in the same
# compound), what lands is the whole working tree vs HEAD — so size exactly
# that (`git diff HEAD`), not the max of staged-vs-HEAD and unstaged-vs-index,
# which undercounts when both exist (deion_assets review-1 F1, FortKnight
# review-1 F1). Without such staging, a pathspec/--only commit with unrelated
# local changes must not be gated by working-tree size (review-3 F2) — if we
# can't size what is being committed, pass silently.
case "$stripped" in
    *"git add"* | *" -a"* | *"--all"*)
        wt=$(changed_lines HEAD)
        [ "${wt:-0}" -gt "${lines:-0}" ] && lines=$wt
        ;;
esac
[ "${lines:-0}" -eq 0 ] && exit 0
[ "${lines:-0}" -lt "$THRESHOLD" ] && exit 0

reason="Blocked by project convention: big commits get an adversarial CODE review before landing. The pending diff is ${lines} changed lines (threshold ${THRESHOLD}). Write the diff (git diff --cached > review/draft.diff; use git diff if staging happens in the same command), run scripts/request-review.sh code review/draft.diff --reviewer=${REVIEWER}, present and adjudicate every finding with the user, apply accepted fixes — then retry the commit with the command prefixed ADV_REVIEWED=1 (also use that prefix if the user explicitly skips review, or if this exact diff was already reviewed this session). Clear review/ artifacts first ONLY if they belong to a previous, settled review subject."

if [ "$HARNESS" = "kimi" ]; then
    printf '%s\n' "$reason" >&2
    exit 2
fi
jq -n --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'

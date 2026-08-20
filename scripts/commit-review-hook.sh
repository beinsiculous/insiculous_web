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
# diffs under THRESHOLD changed lines, and the two doors past the gate below.
# Otherwise DENIES the commit with instructions — informing alone can't stop
# the triggering command.
#
# The two doors, and they mean different things:
#   ADV_REVIEWED=1 prefix   the review HAPPENED — code mode ran and every
#                           finding was adjudicated with the user.
#   a signed skip trailer   the review did NOT happen and a developer said so
#                           in writing, in the commit message (see below).
# ADV_REVIEWED=1 used to cover both, which let an agent skip a review on its
# own reading of a conversation and leave no trace that it had. It no longer
# does: skipping now costs a sentence and a name, written into the history it
# skipped review for.
#
# Be clear about what that buys (review-1 F1): friction and a paper trail, not
# proof of authorship. Nothing here can verify that a human typed the trailers
# — an agent that writes them forges a person's name into the record, which is
# worse than the old silent self-skip, not better. The only thing standing in
# that spot is the instruction, in both SKILL.md files and in the denial below,
# that an agent never writes them. The mechanism makes a skip visible and
# attributable; it does not make it honest.
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
# Door 1: the review happened. The token counts only as a leading env
# assignment (or one right after && / ;) — never as free text inside a commit
# message (review-3 F3).
case "$stripped" in
    "ADV_REVIEWED=1 "* | *"&& ADV_REVIEWED=1 "* | *"; ADV_REVIEWED=1 "*) exit 0 ;;
esac

# Door 2: a signed skip. The only way to land a big diff with no review, and
# it lives in the commit message rather than in a shell variable nobody will
# ever read again — a skip belongs in the history it skipped review for:
#
#     Adversarial-Review-Skipped: <reason, more than 10 characters>
#     Skip-Signed-Off-By: <the developer's name>
#
# Any reason over ten characters is accepted — "just because" is a perfectly
# good reason, and this hook is not the judge of it. What is not optional is
# that a person signs it. Both trailers are required and case-sensitive.
SKIP_REASON_MINIMUM=10
# Git keeps trailers in the last block of a message and so do we: only the tail
# is scanned. Prose that quotes the trailer format — this repo's own docs, or
# the commit that lands them — then reads as prose instead of as a skip nobody
# asked for (review-1 F2, which fired on the very command that wrote the docs).
SKIP_TRAILER_TAIL_LINES=12

# Where a -F/--file message lives, in every spelling git accepts: -F path,
# -Fpath, --file=path, --file path, quoted or not (review-1 F3). `-F -` yields
# "-", which is not a file, so a stdin heredoc falls through to the command
# string, where its body already sits.
#
# Only the part of the command BEFORE any -m/--message is searched (review-2
# F2). git takes its message from one place or the other, never both, so a
# -F that appears after -m is inside the message text — and the denial below
# hands out the string "-F .git/COMMIT_EDITMSG", which a commit describing
# this convention will quote. Reading that file would be the worst possible
# miss: it holds the PREVIOUS attempt's message, the one file on disk likely
# to carry skip trailers, so a stale signature could wave a fresh commit
# through. The earlier comment here claimed no such file would exist. It was
# wrong, and this hook created it.
message_file() {
    file_argument=''
    before_message="$cmd"
    for message_flag in ' -m' ' --message'; do
        case "$before_message" in
            *"$message_flag"*) before_message="${before_message%%$message_flag*}" ;;
        esac
    done
    if [[ "$before_message" =~ (--file=|--file[[:space:]]+|-F[[:space:]]*)(\"[^\"]+\"|\'[^\']+\'|[^[:space:]]+) ]]; then
        file_argument="${BASH_REMATCH[2]}"
        file_argument="${file_argument%\"}"; file_argument="${file_argument#\"}"
        file_argument="${file_argument%\'}"; file_argument="${file_argument#\'}"
    fi
    printf '%s' "$file_argument"
}

# The message as *this command* carries it. -m/--message text and heredoc
# bodies are already inside the command string; a message file is read from
# disk (relative to the shell's cwd, which is why this runs before the cd).
# A message composed in $EDITOR cannot be seen from here, so a skip that goes
# through the editor is denied rather than assumed — the denial says how to
# retry. Paths are read relative to THIS process's working directory, so
# `git -C elsewhere commit -F msg.txt` cannot be seen either (review-2 F3);
# that fails closed, and the denial says which directory it looked in.
message_tail() {
    path=$(message_file)
    {
        printf '%s\n' "$cmd"
        if [ -n "${path:-}" ] && [ -f "$path" ]; then cat -- "$path"; fi
    } | tail -n "$SKIP_TRAILER_TAIL_LINES"
}

# The LAST occurrence wins, as it does in git's own trailer handling: a message
# that quotes the format and then signs for real is judged by the signature,
# not by the quotation (review-2 F1).
trailer_value() {
    message_tail | sed -n "s/^[[:space:]]*$1:[[:space:]]*//p" | tail -1 | sed 's/[[:space:]]*$//'
}

# A value that opens with '<' is the documented template — `<reason, more than
# 10 characters>` is thirty-three characters and would otherwise sail through
# the length check, signing a skip in the name of a placeholder (review-2 F1).
# Only the opening bracket disqualifies, so `Skip-Signed-Off-By: M <m@x.com>`
# is still a person signing their name.
is_placeholder() {
    case "$1" in '<'*) return 0 ;; *) return 1 ;; esac
}

skip_reason=$(trailer_value 'Adversarial-Review-Skipped')
skip_signer=$(trailer_value 'Skip-Signed-Off-By')
skip_problem=''
if [ -n "$skip_reason" ] || [ -n "$skip_signer" ]; then
    if is_placeholder "$skip_reason" || is_placeholder "$skip_signer"; then
        skip_problem="the trailers still hold the template ('${skip_reason}' / '${skip_signer}'), not a reason and a name. Quoting the format is not skipping a review."
    elif [ -z "$skip_reason" ]; then
        skip_problem="signed by '${skip_signer}' but no 'Adversarial-Review-Skipped:' trailer — sign a reason, not a blank."
    elif [ "${#skip_reason}" -le "$SKIP_REASON_MINIMUM" ]; then
        skip_problem="the reason '${skip_reason}' is ${#skip_reason} characters; more than ${SKIP_REASON_MINIMUM} are needed. Any reason over ${SKIP_REASON_MINIMUM} characters is accepted — even 'just because' — so say something."
    elif [ -z "$skip_signer" ]; then
        skip_problem="reason given, nobody signed it. Add 'Skip-Signed-Off-By: <your name>' — a skip goes on the record under a name."
    else
        exit 0
    fi
fi

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

skip_door="A developer can skip the review, in writing, in the last lines of the commit message: 'Adversarial-Review-Skipped: <reason>' (more than ${SKIP_REASON_MINIMUM} characters — any reason qualifies, even 'just because') and 'Skip-Signed-Off-By: <their name>', passed with -m or -F <file> so this hook can read them (already typed them in an editor? retry with -F .git/COMMIT_EDITMSG; message files are read from $(pwd), so run the commit from there rather than through git -C). This hook cannot tell who typed those lines, which is exactly why you must not type them: writing them yourself forges a person's name into the permanent record of a review that never happened. Ask the user, use their words and their name, or run the review."

if [ -n "$skip_problem" ]; then
    reason="Skip rejected: ${skip_problem} The pending diff is ${lines} changed lines (threshold ${THRESHOLD}). ${skip_door} Or run the review: scripts/request-review.sh code review/draft.diff --reviewer=${REVIEWER}, adjudicate every finding with the user, then retry prefixed ADV_REVIEWED=1."
else
    reason="Blocked by project convention: big commits get an adversarial CODE review before landing. The pending diff is ${lines} changed lines (threshold ${THRESHOLD}). Write the diff (git diff --cached > review/draft.diff; use git diff if staging happens in the same command), run scripts/request-review.sh code review/draft.diff --reviewer=${REVIEWER}, present and adjudicate every finding with the user, apply accepted fixes — then retry the commit with the command prefixed ADV_REVIEWED=1, which asserts the review HAPPENED and nothing else (if this exact diff was already reviewed this session, that counts). ${skip_door} Clear review/ artifacts first ONLY if they belong to a previous, settled review subject."
fi

if [ "$HARNESS" = "kimi" ]; then
    printf '%s\n' "$reason" >&2
    exit 2
fi
jq -n --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'

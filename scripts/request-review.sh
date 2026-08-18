#!/usr/bin/env bash
# One-shot adversarial review of an artifact by a headless counterpart CLI.
# Used by the interactive skill (.claude/skills/adversarial-review/) and by
# the fully-headless driver (adversarial-review.sh).
#
#   request-review.sh plan review/plan.md   --reviewer=kimi
#   request-review.sh code review/draft.diff --reviewer=claude [--out=path]
#
# Writes the review to --out (default: review/review-N.md, N auto-incremented)
# and prints the output path on stdout so callers can capture it.
#
# Reviewer invocation (re-verified against installed CLIs, Aug 2026):
#   claude: prompt piped on stdin to `claude -p`, response on stdout.
#   kimi:   prompt passed as the argument to `kimi -p` with --output-format text
#           (-p is already non-interactive and cannot be combined with --auto).
#           kimi-code dropped
#           --quiet/--print/--final-message-only and, importantly, --work-dir,
#           so the scoping that flag used to give is done by running kimi with
#           its cwd set to review/ instead. Same trade as before: kimi cannot
#           read the surrounding code (weaker regression context) but nothing
#           outside review/ is exposed to auto-approved tool use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
REVIEW_DIR="$REPO_ROOT/review"
PROMPTS_DIR="$REPO_ROOT/prompts"

usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") <plan|code> <artifact-path> --reviewer=claude|kimi [--out=path]

  plan mode: artifact is a plan document (uses prompts/adversarial-plan-review.md)
  code mode: artifact is a diff        (uses prompts/adversarial-code-review.md)
  --reviewer  which CLI critiques the artifact
  --out       output file (default: review/review-N.md, N auto-incremented)
EOF
    exit 1
}

MODE="${1:-}"; ARTIFACT="${2:-}"; REVIEWER=""; OUT=""
shift 2 2>/dev/null || usage
for arg in "$@"; do
    case "$arg" in
        --reviewer=claude|--reviewer=kimi) REVIEWER="${arg#--reviewer=}" ;;
        --out=*) OUT="${arg#--out=}" ;;
        *) echo "error: unknown argument '$arg'" >&2; usage ;;
    esac
done

[[ "$MODE" == "plan" || "$MODE" == "code" ]] || usage
[[ -n "$REVIEWER" ]] || usage
[[ -f "$ARTIFACT" ]] || { echo "error: artifact not found: $ARTIFACT" >&2; exit 1; }
command -v "$REVIEWER" >/dev/null || { echo "error: '$REVIEWER' not on PATH" >&2; exit 1; }
mkdir -p "$REVIEW_DIR"

if [[ "$MODE" == "plan" ]]; then
    PROMPT_FILE="$PROMPTS_DIR/adversarial-plan-review.md"
    LABEL="PLAN"
else
    PROMPT_FILE="$PROMPTS_DIR/adversarial-code-review.md"
    LABEL="DIFF"
fi

if [[ -z "$OUT" ]]; then
    n=1
    while [[ -e "$REVIEW_DIR/review-$n.md" ]]; do n=$((n+1)); done
    OUT="$REVIEW_DIR/review-$n.md"
fi

echo "==> reviewer ($REVIEWER) critiquing $ARTIFACT -> $OUT" >&2
PROMPT="$(
    cat "$PROMPT_FILE"
    printf '\n=== %s UNDER REVIEW ===\n' "$LABEL"
    cat "$ARTIFACT"
)"

case "$REVIEWER" in
    claude) printf '%s' "$PROMPT" | claude -p > "$OUT" ;;
    # cd into review/ so any auto-approved tool call is confined there.
    kimi)   ( cd "$REVIEW_DIR" && kimi --output-format text -p "$PROMPT" ) > "$OUT" ;;
esac

echo "$OUT"

#!/bin/sh
# Commit selected local changes, push branch, create GitHub PR or GitLab MR.

set -eu

BASE=""
BRANCH=""
MESSAGE=""
TITLE=""
BODY=""
PROVIDER="auto"
OPEN_RULE_INPUT=""
PYTHON_BIN="${PYTHON_BIN:-}"
STAGE_ALL=false
YES=false
SKIP_SECRET_SCAN=false
DRY_RUN=false

usage() {
    cat <<'EOF'
Usage: scripts/create-merge-request.sh -m MESSAGE [options] -- [paths...]

Options:
  -m, --message MSG       Commit message, required
  -b, --branch BRANCH     Branch to create/use
  -B, --base BRANCH       Target branch, default origin/HEAD or main
  -t, --title TITLE       PR/MR title, default commit message
  --body TEXT             PR/MR body
  --provider NAME         auto, github, gitlab
  --open-rule FILE        Apply open_rule YAML changes from flow JSON first
  --python BIN            Python command for --open-rule
  --all                   Stage all changes
  -y, --yes               Skip confirmation
  --skip-secret-scan      Skip staged diff secret scan
  --dry-run               Print actions only
  -h, --help              Show help

Examples:
  scripts/create-merge-request.sh -b fix/rule -m "fix: update rule" -- clusters/fw-core/objects.yaml
  scripts/create-merge-request.sh -b fix/segments -m "fix(open-rule): update segments" --all
  scripts/create-merge-request.sh -b fix/rule -m "fix: open firewall rule" --open-rule examples/flows.json
EOF
}

log() {
    printf '%s\n' "==> $*"
}

die() {
    printf '%s\n' "error: $*" >&2
    exit 1
}

default_base() {
    git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null |
        sed 's#^origin/##' || true
}

current_branch() {
    git rev-parse --abbrev-ref HEAD
}

choose_python() {
    for candidate in "$PYTHON_BIN" python3 python /opt/homebrew/opt/python@3.11/bin/python3.11; do
        [ -n "$candidate" ] || continue
        if { command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; } &&
            "$candidate" -c 'import yaml' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    die "python with PyYAML not found; install requirements or pass --python"
}

run() {
    log "$*"
    if [ "$DRY_RUN" = false ]; then
        "$@"
    fi
}

confirm() {
    [ "$YES" = true ] && return 0
    printf '%s' "Continue? [y/N] "
    read ans
    case "$ans" in
        y|Y|yes|YES) return 0 ;;
        *) die "cancelled" ;;
    esac
}

while [ $# -gt 0 ]; do
    case "$1" in
        -m|--message)
            MESSAGE="${2:-}"
            shift 2
            ;;
        -b|--branch)
            BRANCH="${2:-}"
            shift 2
            ;;
        -B|--base)
            BASE="${2:-}"
            shift 2
            ;;
        -t|--title)
            TITLE="${2:-}"
            shift 2
            ;;
        --body)
            BODY="${2:-}"
            shift 2
            ;;
        --provider)
            PROVIDER="${2:-}"
            shift 2
            ;;
        --open-rule)
            OPEN_RULE_INPUT="${2:-}"
            shift 2
            ;;
        --python)
            PYTHON_BIN="${2:-}"
            shift 2
            ;;
        --all)
            STAGE_ALL=true
            shift
            ;;
        -y|--yes)
            YES=true
            shift
            ;;
        --skip-secret-scan)
            SKIP_SECRET_SCAN=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repo"
[ -n "$MESSAGE" ] || die "commit message required"
[ "$STAGE_ALL" = true ] || [ $# -gt 0 ] || [ -n "$OPEN_RULE_INPUT" ] || die "pass paths, --all, or --open-rule"

BASE="${BASE:-$(default_base)}"
BASE="${BASE:-main}"
TITLE="${TITLE:-$MESSAGE}"

case "$PROVIDER" in
    auto|github|gitlab) ;;
    *) die "provider must be auto, github, or gitlab" ;;
esac

REMOTE_URL=$(git config --get remote.origin.url || true)
[ -n "$REMOTE_URL" ] || die "remote origin missing"

if [ "$PROVIDER" = auto ]; then
    case "$REMOTE_URL" in
        *gitlab*) PROVIDER="gitlab" ;;
        *) PROVIDER="github" ;;
    esac
fi

if [ -n "$BRANCH" ]; then
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        run git switch "$BRANCH"
    else
        run git switch -c "$BRANCH"
    fi
elif [ "$(current_branch)" = "$BASE" ]; then
    BRANCH="change/$(date +%Y%m%d-%H%M%S)"
    run git switch -c "$BRANCH"
else
    BRANCH="$(current_branch)"
fi

log "base: $BASE"
log "branch: $BRANCH"
log "provider: $PROVIDER"

OPEN_RULE_CHANGED=""
if [ -n "$OPEN_RULE_INPUT" ]; then
    log "apply open_rule: $OPEN_RULE_INPUT"
    if [ "$DRY_RUN" = false ]; then
        PYTHON_CMD=$(choose_python)
        OPEN_RULE_CHANGED=$(PYTHONPATH=. "$PYTHON_CMD" -m scripts.open_rule.apply "$OPEN_RULE_INPUT" --changed-files)
        if [ -n "$OPEN_RULE_CHANGED" ]; then
            printf '%s\n' "$OPEN_RULE_CHANGED"
        fi
    fi
fi

if [ "$STAGE_ALL" = true ]; then
    run git add -A
elif [ $# -gt 0 ]; then
    run git add "$@"
elif [ -n "$OPEN_RULE_CHANGED" ]; then
    run git add $OPEN_RULE_CHANGED
else
    log "no open_rule YAML changes to stage"
fi

if [ "$DRY_RUN" = true ]; then
    log "dry run complete"
    exit 0
fi

if git diff --cached --quiet; then
    log "no staged changes; will use existing branch commits"
else
    git diff --cached --stat
    if [ "$SKIP_SECRET_SCAN" = false ]; then
        if git diff --cached --unified=0 |
            grep '^+' |
            grep -v '^+++' |
            grep -iE '(AKIA|api[_-]?key|token|password|secret|credential|private[_-]?key|mongodb://|postgres://|mysql://|redis://|-----BEGIN)'; then
            die "secret-like staged content found"
        fi
    fi
    confirm
    run git commit -m "$MESSAGE"
fi

run git fetch origin "$BASE"
run git push -u origin HEAD

if [ -z "$BODY" ]; then
    BODY=$(printf '## Summary\n- %s\n\n## Test plan\n- [ ] CI pipeline\n' "$MESSAGE")
fi

case "$PROVIDER" in
    github)
        command -v gh >/dev/null 2>&1 || die "gh not found"
        if gh pr view "$BRANCH" >/dev/null 2>&1; then
            gh pr view "$BRANCH" --json url --jq .url
        else
            gh pr create --base "$BASE" --head "$BRANCH" --title "$TITLE" --body "$BODY"
        fi
        ;;
    gitlab)
        command -v glab >/dev/null 2>&1 || die "glab not found"
        glab mr create --target-branch "$BASE" --source-branch "$BRANCH" --title "$TITLE" --description "$BODY"
        ;;
esac

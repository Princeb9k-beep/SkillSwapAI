#!/usr/bin/env bash
#
# SkillSwap AI — one-command (re)deploy of the APP TIER on the app VPS.
#
#   deploy/deploy.sh              # pull, build, migrate, deploy, verify
#   deploy/deploy.sh --no-pull    # deploy the current working tree
#   deploy/deploy.sh --branch X   # deploy branch X on purpose (see below)
#   deploy/deploy.sh --rollback   # revert to the previously deployed image
#
# Safe by design:
#   * builds BEFORE touching the running container → a broken build is not downtime
#   * snapshots the current image as :rollback     → and auto-reverts if unhealthy
#   * migrates as a ONE-SHOT before the app starts → two workers never race DDL
#   * gates on the container healthcheck, which asserts "database":"up" rather
#     than merely a 200 — /health answers 200 with the database DOWN
#
# The DATA TIER lives on the other VPS. This script never starts, stops or
# migrates away from it beyond `alembic upgrade head`; use deploy/data-deploy.sh
# there.
set -euo pipefail

# ── config ───────────────────────────────────────────────────────────────
IMAGE="skillswap"
SERVICE="web"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"    # seconds to wait for web to report healthy
MIN_FREE_GB="${MIN_FREE_GB:-5}"
EDGE_NET="${EDGE_NET:-edge}"               # shared with Nova Flow's nginx
KEEP_IMAGES="${KEEP_IMAGES:-5}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE="${ROOT}/docker-compose.yml"
cd "$ROOT"

log()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

dc() { docker compose -f "$COMPOSE" "$@"; }

# THE dotenv parser — one definition, sourced, never copied. `source .env` is
# not an option: an unquoted value with a space is EXECUTED. See lib/dotenv.sh.
. "$SCRIPT_DIR/lib/dotenv.sh"
# `|| true` is load-bearing: the function returns 1 for an ABSENT key, every
# call here is `v=$(read_env X)`, and an assignment carries the rc and is not a
# guarded context — so under `set -e` a missing key would abort the deploy.
read_env() { skillswap_dotenv_value "${ROOT}/.env" "$1" || true; }

# ── the branch guard, as a function so a test can EXECUTE it ─────────────
#
# WHY THIS EXISTS. `git pull` fast-forwards THE CURRENT BRANCH. A checkout left
# on a feature branch therefore deploys happily forever, answering "Already up
# to date" — truthfully, about the wrong branch. In the sibling Nova Flow
# deployment that cost five days and three bug reports whose fixes were merged,
# green and sitting in main the whole time. Every proxy for "is it shipped"
# said yes; only the bytes the browser downloaded disagreed.
#
# So the branch is ASSERTED, not assumed. Deploying a feature branch stays
# possible — it is occasionally the point — but it has to be asked for.
#
# Prints the branch to deploy on stdout; diagnostics go to stderr.
assert_deployable_branch() {
  local requested="${1:-}" current default
  current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  default="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
  [ -n "$default" ] || default=main

  if [ -n "$requested" ]; then
    if [ "$current" != "$requested" ]; then
      printf '✗ --branch says %s but the checkout is on %s. git checkout %s\n' \
        "$requested" "$current" "$requested" >&2
      return 1
    fi
    printf '! deploying %s (not %s) — explicitly requested\n' "$current" "$default" >&2
  elif [ "$current" != "$default" ]; then
    printf '✗ REFUSING TO DEPLOY: this checkout is on %s, not %s.\n' "$current" "$default" >&2
    printf '  A deploy from here ships that branch, and git pull will report\n' >&2
    printf '  success while shipping nothing new. To ship %s:\n' "$default" >&2
    printf '    git fetch origin %s && git checkout %s && git pull --ff-only\n' "$default" "$default" >&2
    printf '  To deploy %s on purpose:\n    deploy/deploy.sh --branch %s\n' "$current" "$current" >&2
    return 1
  fi
  printf '%s' "$current"
}

# Sourcing this file (BRANCH_GUARD_LIB=1) defines the function and stops, so a
# test can drive it against a fake `git` on PATH. Reading shell cannot check
# shell semantics; executing it can.
[ "${BRANCH_GUARD_LIB:-0}" = 1 ] && return 0 2>/dev/null || true

# ── flags ────────────────────────────────────────────────────────────────
PULL=1; ROLLBACK_ONLY=0; DEPLOY_BRANCH="${DEPLOY_BRANCH:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-pull)  PULL=0 ;;
    --rollback) ROLLBACK_ONLY=1 ;;
    --branch)   shift; DEPLOY_BRANCH="${1:-}"
                [ -n "$DEPLOY_BRANCH" ] || die "--branch needs a branch name" ;;
    --branch=*) DEPLOY_BRANCH="${1#*=}" ;;
    "")         ;;
    *)          die "unknown arg: $1  (use --no-pull, --rollback or --branch <name>)" ;;
  esac
  shift
done

# ── rollback-only path ───────────────────────────────────────────────────
if [ "$ROLLBACK_ONLY" = 1 ]; then
  docker image inspect "${IMAGE}:rollback" >/dev/null 2>&1 \
    || die "no ${IMAGE}:rollback image exists to roll back to"
  # APP-IMAGE rollback only. The schema is NOT rolled back: alembic migrations
  # are forward-only here, and `alembic downgrade` against live data is a
  # deliberate, supervised act — not something a deploy script does at 2am.
  log "Rolling back to ${IMAGE}:rollback"
  docker image tag "${IMAGE}:rollback" "${IMAGE}:latest"
  dc up -d --remove-orphans "$SERVICE"
  dc ps
  exit 0
fi

# ── preflight ────────────────────────────────────────────────────────────
log "Preflight"
docker info >/dev/null 2>&1 || die "Docker engine is not running"
[ -f "${ROOT}/.env" ]        || die ".env not found in ${ROOT} (copy .env.example and fill it in)"

DATABASE_URL="$(read_env DATABASE_URL)"
REDIS_URL="$(read_env REDIS_URL)"
[ -n "$DATABASE_URL" ] || die "DATABASE_URL is not set in .env — the app cannot start without a database"
[ -n "$REDIS_URL" ]    || warn "REDIS_URL is not set — caching, rate limiting and locks will no-op (the app degrades, by design)"

dc config -q || die "docker-compose.yml is invalid"
ok "docker · .env · DATABASE_URL · compose config"

# ── free disk ────────────────────────────────────────────────────────────
# An unchecked precondition resurfaces downstream wearing someone else's
# symptom: a full disk shows up as `tee: No space left on device`, then
# `fatal: unable to write loose object file`, then this script's own "git pull
# failed" — which is where the debugging goes, and it is the wrong place.
# POSIX `df -Pk`, not GNU's --output=avail, so this still works from a BusyBox
# recovery shell.
_avail_kb="$(df -Pk "${ROOT}" 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -z "${_avail_kb}" ]; then
  warn "could not read free space for ${ROOT} — skipping the disk check"
else
  _avail_gb=$(( _avail_kb / 1024 / 1024 ))
  if [ "${_avail_gb}" -lt "${MIN_FREE_GB}" ]; then
    warn "reclaim safely, in this order:"
    warn "  docker builder prune -af       # build cache; touches no images"
    warn "  journalctl --vacuum-size=200M"
    warn "NEVER 'docker system prune -a': ${IMAGE}:rollback is not attached to a"
    warn "  running container, so -a deletes the auto-revert target the health"
    warn "  gate below depends on."
    die "not enough free disk to build (${_avail_gb}G < ${MIN_FREE_GB}G). Override with MIN_FREE_GB= if you know better."
  fi
  ok "disk: ${_avail_gb}G free (floor ${MIN_FREE_GB}G)"
fi

# ── data tier reachability ───────────────────────────────────────────────
# url_host / url_port pull the host and port out of a URL of the shape
# scheme://[user[:pass]@]host[:port][/path]. Password characters cannot
# confuse it: everything up to and including the LAST @ is stripped first.
url_host() { printf '%s' "$1" | sed -E 's#^[a-z+]+://##I; s#^.*@##; s#[:/?].*$##'; }
url_port() { printf '%s' "$1" | sed -E 's#^[a-z+]+://##I; s#^.*@##; s#^[^:/?]*##; s#^:([0-9]+).*#\1#; s#^[^0-9].*##'; }

tcp_open() {  # $1=host $2=port $3=timeout-seconds
  timeout "${3:-5}" bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null
}

PG_HOST="$(url_host "$DATABASE_URL")"; PG_PORT="$(url_port "$DATABASE_URL")"; PG_PORT="${PG_PORT:-5432}"
case "$PG_HOST" in
  10.77.0.*)
    # Tunnel address space — check wg0 before blaming the database.
    if systemctl is-active --quiet wg-quick@wg0 2>/dev/null; then
      hs="$(wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}' | head -1)"
      now="$(date +%s)"
      if [ -n "${hs:-}" ] && [ "$hs" -gt 0 ] 2>/dev/null && [ $(( now - hs )) -lt 180 ]; then
        ok "wg0 up — peer handshake $(( now - hs ))s ago"
      else
        warn "wg0 is active but has no recent peer handshake — the tunnel may be stale (wg show wg0)"
      fi
    else
      warn "wg-quick@wg0 is NOT active — 10.77.0.x is unreachable until it is: systemctl start wg-quick@wg0"
    fi ;;
esac

# POSTGRES IS NOT FAIL-OPEN. Redis going dark degrades the app (the code is
# written for it); the database going dark IS the app being down. So this is a
# hard stop, taken BEFORE anything is built or replaced — the currently running
# container keeps serving.
if tcp_open "$PG_HOST" "$PG_PORT" 8; then
  ok "postgres reachable at ${PG_HOST}:${PG_PORT}"
else
  die "cannot reach Postgres at ${PG_HOST}:${PG_PORT} — NOTHING was changed.
      On the data VPS:  deploy/data-deploy.sh   (and check wg-quick@wg0 both ends)"
fi

if [ -n "$REDIS_URL" ]; then
  R_HOST="$(url_host "$REDIS_URL")"; R_PORT="$(url_port "$REDIS_URL")"; R_PORT="${R_PORT:-6379}"
  if tcp_open "$R_HOST" "$R_PORT" 5; then
    ok "redis reachable at ${R_HOST}:${R_PORT}"
  else
    warn "redis at ${R_HOST}:${R_PORT} did not answer — the app is fail-open (cache,"
    warn "rate limits and locks no-op), so this is a warning, not a blocker."
  fi
fi

# ── which branch are we about to ship? ───────────────────────────────────
CURRENT_BRANCH="$(assert_deployable_branch "$DEPLOY_BRANCH")" \
  || die "refusing to deploy (see above)"

# ── pull ─────────────────────────────────────────────────────────────────
if [ "$PULL" = 1 ]; then
  log "Pulling latest code"
  git pull --ff-only || die "git pull failed (local changes? use --no-pull to deploy the working tree)"
fi
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
# Say what is being shipped, EVERY run. The five-day incident above was
# invisible because no deploy ever printed the branch it was on.
log "Deploying ${CURRENT_BRANCH} @ ${SHA}"

# ── the shared edge network ──────────────────────────────────────────────
# Nova Flow's nginx and this app both attach to it; neither compose project
# owns it, which is why it is `external: true` on both sides. Creating it is
# idempotent and must happen before any `up` or `run`.
if docker network inspect "$EDGE_NET" >/dev/null 2>&1; then
  ok "network ${EDGE_NET} exists"
else
  docker network create "$EDGE_NET" >/dev/null && ok "created network ${EDGE_NET}"
fi

# ── snapshot + trim BEFORE the build ─────────────────────────────────────
if docker image inspect "${IMAGE}:latest" >/dev/null 2>&1; then
  docker image tag "${IMAGE}:latest" "${IMAGE}:rollback"
  ok "snapshotted current image as ${IMAGE}:rollback"
fi

# Trim BEFORE building, not in housekeeping afterwards: the BUILD is what needs
# the free space, so reclaiming after it is too late for the run that ran out.
#
# `docker image prune -f` reclaims DANGLING images only, and a ${IMAGE}:${SHA}
# image is tagged by definition — so it is never dangling and never collected.
# Left alone that is one full image per release, forever, and the disk crosses
# the line all at once.
#
# `tail -n +${KEEP_IMAGES}` selects from line KEEP_IMAGES onward, so it KEEPS
# the newest KEEP_IMAGES-1 — deliberate, because the tag added after the build
# takes the remaining slot. `latest` and `rollback` are excluded BY NAME and
# must stay that way: rollback is the auto-revert target below and is attached
# to no running container.
log "Trimming image history (keeping ${KEEP_IMAGES})"
_stale="$(docker image ls "${IMAGE}" --format '{{.CreatedAt}}'$'\t''{{.Tag}}' 2>/dev/null \
            | sort -r \
            | awk -F'\t' '$2 != "latest" && $2 != "rollback" && $2 != "<none>" { print $2 }' \
            | tail -n +"${KEEP_IMAGES}" || true)"
if [ -n "${_stale}" ]; then
  printf '%s\n' "${_stale}" | while IFS= read -r _tag; do
    [ -n "${_tag}" ] || continue
    docker image rm "${IMAGE}:${_tag}" >/dev/null 2>&1 \
      && ok "dropped ${IMAGE}:${_tag}" \
      || warn "could not drop ${IMAGE}:${_tag} (in use?) — left in place"
  done
else
  ok "nothing to trim"
fi

# ── build (does NOT touch the running container) ─────────────────────────
log "Building image (git ${SHA})"
export SOURCE_COMMIT="${SHA}"
dc build
docker image tag "${IMAGE}:latest" "${IMAGE}:${SHA}" 2>/dev/null || true

# ── migrations: ONE SHOT, before the app tier ────────────────────────────
# Deliberately here and not at boot. Two gunicorn workers both running
# `alembic upgrade head` in their lifespan is two processes racing the same
# DDL, and alembic's version table is not a lock you get for free.
#
# Run on the image just built, so the schema always matches the code about to
# serve it. --no-deps: this compose project has no data services to start.
log "Applying migrations (alembic upgrade head)"
if ! dc run --rm --no-deps -T -w /app/backend "$SERVICE" alembic upgrade head; then
  die "migrations FAILED — the app tier was NOT restarted, so the previous
      container is still serving. Fix the migration and re-run."
fi

# ASSERT THE VALUE, NOT THE PRESENCE. `alembic upgrade head` exits 0 when it had
# nothing to do — including when it is pointed at a database that is not the one
# you think it is. `alembic current` prints the revision followed by "(head)"
# only when the schema really is at head.
mig_now="$(dc run --rm --no-deps -T -w /app/backend "$SERVICE" alembic current 2>&1 || true)"
if printf '%s' "$mig_now" | grep -q '(head)'; then
  ok "schema at head: $(printf '%s' "$mig_now" | grep '(head)' | tail -1)"
else
  warn "alembic current did not report (head):"
  printf '%s\n' "$mig_now"
  die "the database is not at head after a successful upgrade — check that
      DATABASE_URL points where you think it does."
fi

# ── deploy the app tier ──────────────────────────────────────────────────
# --remove-orphans on every `up`: an interrupted or overlapping deploy can leave
# a renamed leftover container still holding the service and serving STALE code,
# which a plain `up -d` will not dislodge. It only removes untracked/renamed
# leftovers, never the tracked service container, so it adds no downtime.
log "Starting ${SERVICE}"
dc up -d --remove-orphans "$SERVICE" || true   # failures surface in the gate below

# ── health gate (auto-rollback on failure) ───────────────────────────────
# The container's HEALTHCHECK asserts "database":"up" in the /health body, not
# merely a 200 — /health answers 200 with the database down, so a status-code
# gate would wave a database-less container straight through.
log "Waiting for ${SERVICE} to become healthy (≤ ${HEALTH_TIMEOUT}s)"
cid="$(dc ps -q "$SERVICE")"
[ -n "$cid" ] || die "${SERVICE} container was not created"
status=""; deadline=$(( SECONDS + HEALTH_TIMEOUT ))
while [ "$SECONDS" -lt "$deadline" ]; do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo none)"
  state="$( docker inspect --format '{{.State.Status}}'        "$cid" 2>/dev/null || echo none)"
  printf '  %s: %-9s (%s)\r' "$SERVICE" "$status" "$state"
  [ "$status" = healthy ] && break
  { [ "$state" = exited ] || [ "$state" = dead ]; } && break
  sleep 4
done
echo
if [ "$status" != healthy ]; then
  warn "${SERVICE} did not become healthy — last 40 log lines:"
  dc logs --tail 40 "$SERVICE" || true
  if docker image inspect "${IMAGE}:rollback" >/dev/null 2>&1; then
    warn "Auto-rolling back to the previous image"
    docker image tag "${IMAGE}:rollback" "${IMAGE}:latest"
    dc up -d --remove-orphans "$SERVICE"
    die "Deploy failed and was rolled back. The site is on the last good build."
  fi
  die "Deploy failed and there is no rollback image. Fix the errors above and retry."
fi
ok "${SERVICE} is healthy (database confirmed up)"

# ── edge check ───────────────────────────────────────────────────────────
# nginx lives in the Nova Flow stack on this same box. It resolves this app by
# the `skillswap-web` alias on the shared edge network, through Docker's
# embedded DNS with a short TTL — so a container recreated with a new IP is
# picked up without a reload. Confirm the alias actually resolves rather than
# assuming it: a missing alias is a 502 on a vhost nobody is watching.
if docker network inspect "$EDGE_NET" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
     | grep -q skillswap-web; then
  ok "skillswap-web is attached to ${EDGE_NET} (nginx can reach it)"
else
  warn "skillswap-web is NOT attached to ${EDGE_NET} — nginx will 502 on this"
  warn "vhost. Check the aliases block in docker-compose.yml."
fi

log "Deploy complete  (${CURRENT_BRANCH} @ ${SHA})"
dc ps

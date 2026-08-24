#!/usr/bin/env bash
#
# SkillSwap AI — (re)deploy the DATA TIER on the Redis VPS (80.190.73.191).
# Run as root ON THAT BOX, after deploy/setup-data-vps.sh has provisioned it.
#
#   deploy/data-deploy.sh              # pull, tune, start, health-gate
#   deploy/data-deploy.sh --no-pull    # deploy the working tree
#   deploy/data-deploy.sh --status     # report only; change nothing
#
# This is the boring half on purpose. Postgres and Redis are pulled images with
# a config file in front of them, so a "deploy" here is: bring the config up to
# date, restart if it changed, prove both services answer. It never migrates a
# schema (the app VPS does that, against the code that will serve it) and it
# never takes a backup.
set -euo pipefail

PG_HEALTH_TIMEOUT="${PG_HEALTH_TIMEOUT:-120}"
REDIS_HEALTH_TIMEOUT="${REDIS_HEALTH_TIMEOUT:-60}"
BASE="${SKILLSWAP_BASE:-/srv/skillswap}"
MNT="${PGDATA_HOST_PATH:-${BASE}/pgdata}"
WG_ADDR="${WG_ADDR:-10.77.0.1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE="${ROOT}/docker-compose.data.yml"
cd "$ROOT"

log()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

dc() { docker compose -f "$COMPOSE" "$@"; }

. "$SCRIPT_DIR/lib/dotenv.sh"
read_env() { skillswap_dotenv_value "${ROOT}/.env" "$1" || true; }

# health_gate <service> <timeout> — poll docker's own health status.
health_gate() {
  local svc="$1" limit="$2" cid status state deadline
  cid="$(dc ps -q "$svc")"
  [ -n "$cid" ] || { warn "${svc} container was not created"; return 1; }
  status=""; deadline=$(( SECONDS + limit ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo none)"
    state="$( docker inspect --format '{{.State.Status}}'        "$cid" 2>/dev/null || echo none)"
    printf '  %s: %-9s (%s)\r' "$svc" "$status" "$state"
    [ "$status" = healthy ] && { echo; return 0; }
    { [ "$state" = exited ] || [ "$state" = dead ]; } && break
    sleep 3
  done
  echo
  warn "${svc} did not become healthy — last 40 log lines:"
  dc logs --tail 40 "$svc" || true
  return 1
}

PULL=1; STATUS_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-pull) PULL=0 ;;
    --status)  STATUS_ONLY=1 ;;
    "")        ;;
    *)         die "unknown arg: $1  (use --no-pull or --status)" ;;
  esac
  shift
done

# ── preflight ────────────────────────────────────────────────────────────
log "Preflight"
[ "$(id -u)" -eq 0 ] || die "run as root (it inspects mounts and systemd)"
docker info >/dev/null 2>&1 || die "Docker engine is not running"
[ -f "${ROOT}/.env" ] || die ".env not found in ${ROOT} — it holds POSTGRES_PASSWORD and REDIS_PASSWORD"
[ -n "$(read_env POSTGRES_PASSWORD)" ] || die "POSTGRES_PASSWORD is not set in .env"
[ -n "$(read_env REDIS_PASSWORD)" ]    || die "REDIS_PASSWORD is not set in .env — the redis service refuses to start authless, by design"

# The tunnel address must EXIST before anything tries to publish on it.
# Otherwise: "cannot assign requested address", and the container simply never
# starts — which at 03:00 after a reboot reads as "the database is gone".
if ip -brief addr show wg0 2>/dev/null | grep -q "$WG_ADDR"; then
  ok "wg0 holds ${WG_ADDR}"
else
  die "wg0 does not hold ${WG_ADDR} — the data containers cannot bind their
      published ports. Fix the tunnel first:  systemctl start wg-quick@wg0"
fi

# ── the PGDATA mount guard ───────────────────────────────────────────────
#
# Two failure modes, and the second is the dangerous one:
#   (a) the loopback filesystem is not mounted → Postgres writes to the bare
#       directory on the root filesystem, and the 10 GB ceiling silently is not
#       a ceiling any more.
#   (b) it IS mounted but EMPTY → Postgres cheerfully initdb's a blank cluster
#       beside the real data, the app connects, finds no tables, and the first
#       thing anyone notices is that every account has disappeared.
#
# Both are indistinguishable from a healthy start unless something checks. A
# genuine first bring-up is the ONLY time (b) is legitimate, so it has to be
# asked for by name.
PGDATA_HOST_PATH="$(read_env PGDATA_HOST_PATH)"
PGDATA_HOST_PATH="${PGDATA_HOST_PATH:-$MNT}"
if [ "${PGDATA_HOST_PATH#/}" != "$PGDATA_HOST_PATH" ]; then   # absolute → a bind mount
  mountpoint -q "$PGDATA_HOST_PATH" \
    || die "PGDATA_HOST_PATH=${PGDATA_HOST_PATH} is NOT a mountpoint. The 10 GB
      loopback filesystem is not mounted (reboot?), so Postgres would write to
      the host root filesystem with no ceiling at all.
        mount ${PGDATA_HOST_PATH}     (or re-run deploy/setup-data-vps.sh)"
  if [ ! -f "${PGDATA_HOST_PATH}/18/docker/PG_VERSION" ] && [ "${PGDATA_ALLOW_EMPTY:-0}" != 1 ]; then
    die "PGDATA_HOST_PATH=${PGDATA_HOST_PATH} is mounted but holds NO cluster
      (no 18/docker/PG_VERSION). If the real data is in the named 'pgdata'
      volume from an earlier bring-up, move it before starting — a start here
      would initdb an empty cluster beside it.
      Only a genuine FIRST bring-up may proceed:
        PGDATA_ALLOW_EMPTY=1 $0"
  fi
  ok "PGDATA: ${PGDATA_HOST_PATH} mounted, cluster present (or explicitly allowed empty)"
  df -h "$PGDATA_HOST_PATH" | tail -1 | sed 's/^/    /'

  # A database on a hard 10 GB ceiling should say so before it is full, not
  # after. Postgres does not fail gracefully at ENOSPC: it refuses writes and,
  # if WAL cannot be written, it stops.
  _used_pct="$(df -P "$PGDATA_HOST_PATH" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
  if [ "${_used_pct:-0}" -ge 90 ]; then
    warn "PGDATA is ${_used_pct}% full. At 100% Postgres stops accepting writes."
    warn "  du -sh ${PGDATA_HOST_PATH}/18/docker/*  |  check for un-recycled WAL"
  elif [ "${_used_pct:-0}" -ge 75 ]; then
    warn "PGDATA is ${_used_pct}% full — plan the resize now, not at 99%."
  fi
else
  warn "PGDATA_HOST_PATH is unset or not absolute → the UNCAPPED named volume is"
  warn "in use. Correct for local dev; wrong on this box, where the 10 GB ceiling"
  warn "is the whole point."
fi

if [ "$STATUS_ONLY" = 1 ]; then
  log "Status only"
  dc ps
  exit 0
fi

# ── pull ─────────────────────────────────────────────────────────────────
# No branch guard here, unlike the app deploy: this box runs config, not code,
# and the config is the same on every branch. If that stops being true, copy
# assert_deployable_branch from deploy/deploy.sh rather than reinventing it.
if [ "$PULL" = 1 ] && [ -d "${ROOT}/.git" ]; then
  log "Pulling latest config"
  git -C "$ROOT" pull --ff-only || warn "git pull failed — deploying the working tree"
fi

# ── tuning ───────────────────────────────────────────────────────────────
# The single edit-point on a resize. Exported so compose's ${...} interpolation
# in docker-compose.data.yml picks them up; absent, the in-file fallbacks are
# the same 256M profile, so this file is optional-but-preferred.
PG_TUNING="${ROOT}/deploy/postgres/pg-tuning.env"
if [ -f "$PG_TUNING" ]; then
  set -a; . "$PG_TUNING"; set +a
  ok "tuning: mem=${PG_MEM_LIMIT:-?} cpus=${PG_CPUS:-?} shared_buffers=${PG_SHARED_BUFFERS:-?} redis=${REDIS_MAXMEMORY:-?}"
else
  warn "no ${PG_TUNING} — using the in-compose fallbacks (same 256M profile)"
fi
export PGDATA_HOST_PATH WG_ADDR
dc config -q || die "docker-compose.data.yml is invalid"

# ── start, health-gated ──────────────────────────────────────────────────
log "Starting postgres"
dc up -d --remove-orphans postgres || true
health_gate postgres "$PG_HEALTH_TIMEOUT" \
  || die "Postgres is not healthy. The app tier was not touched; fix this first."
ok "postgres is healthy"

log "Starting redis"
dc up -d --remove-orphans redis || true
if health_gate redis "$REDIS_HEALTH_TIMEOUT"; then
  ok "redis is healthy"
else
  # Redis is fail-open for this app by design (cache, rate limits and locks all
  # no-op without it), so an unhealthy Redis must not stop a Postgres that came
  # up fine. It is still loud.
  warn "redis is NOT healthy — the app degrades rather than failing, but fix it."
fi

# ── prove it from the outside ────────────────────────────────────────────
# The healthchecks above run INSIDE each container, over its own loopback. They
# say nothing about whether the published tunnel address works — which is the
# only path the app actually uses. Assert the thing the app depends on.
log "Verifying the published tunnel endpoints"
PG_PORT="${POSTGRES_HOST_PORT:-5432}"
REDIS_PORT="${REDIS_HOST_PORT:-6380}"
if timeout 5 bash -c "exec 3<>/dev/tcp/${WG_ADDR}/${PG_PORT}" 2>/dev/null; then
  ok "postgres accepting on ${WG_ADDR}:${PG_PORT}"
else
  die "postgres is healthy INSIDE its container but nothing is listening on
      ${WG_ADDR}:${PG_PORT} — check the ports: entry in docker-compose.data.yml"
fi
if timeout 5 bash -c "exec 3<>/dev/tcp/${WG_ADDR}/${REDIS_PORT}" 2>/dev/null; then
  ok "redis accepting on ${WG_ADDR}:${REDIS_PORT}"
else
  warn "nothing listening on ${WG_ADDR}:${REDIS_PORT}"
fi

# And confirm they are NOT on the public interface. This is cheap, and the
# failure it catches is silent: Docker's DNAT bypasses ufw, so a publish that
# lost its bind address is reachable from the internet while `ufw status` still
# reports the port closed.
_pub="$(ss -ltnp 2>/dev/null | awk '{print $4}' | grep -E ":(${PG_PORT}|${REDIS_PORT})\$" || true)"
if printf '%s' "$_pub" | grep -qE '^(0\.0\.0\.0|\[::\]|\*)'; then
  warn "─────────────────────────────────────────────────────────────────"
  warn "A DATA PORT IS BOUND TO ALL INTERFACES:"
  printf '%s\n' "$_pub" | sed 's/^/      /'
  warn "ufw will NOT save you — Docker DNATs before filter/INPUT. Restore the"
  warn "'${WG_ADDR}:' prefix on the ports: entry and re-run."
  warn "─────────────────────────────────────────────────────────────────"
else
  ok "data ports are tunnel-bound, not public"
fi

log "Data tier up"
dc ps

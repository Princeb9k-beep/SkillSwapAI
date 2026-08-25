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
PGDATA_IMAGE="${PGDATA_IMAGE:-${BASE}/pgdata.img}"
PGDATA_SIZE="${PGDATA_SIZE:-10G}"
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

# ── the PGDATA image ─────────────────────────────────────────────────────
#
# The 10 GB ceiling is a filesystem in a FILE, mounted by Docker's local driver
# (`type: ext4, o: loop` on the pgdata volume). The `bootstrap` service in the
# compose file creates and formats it before anything mounts it, so there is
# nothing to provision here — only the two things worth knowing BEFORE we start:
# is there room on the host to create it, and does it already carry data.
if [ -f "$PGDATA_IMAGE" ]; then
  ok "PGDATA image present: ${PGDATA_IMAGE} ($(du -h "$PGDATA_IMAGE" 2>/dev/null | cut -f1) allocated)"
else
  warn "no PGDATA image at ${PGDATA_IMAGE} — bootstrap will create it (${PGDATA_SIZE})."
  warn "This is a FIRST BRING-UP. Postgres will initdb an empty cluster into it."
  _need_kb=$(( $(printf '%s' "$PGDATA_SIZE" | tr -dc '0-9') * 1024 * 1024 ))
  _free_kb="$(df -Pk "$(dirname "$PGDATA_IMAGE")" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [ -n "${_free_kb:-}" ] && [ "$_free_kb" -lt "$_need_kb" ]; then
    die "only $(( _free_kb / 1024 / 1024 ))G free where the image would go, and it
      needs $(( _need_kb / 1024 / 1024 ))G. Free space or lower PGDATA_SIZE."
  fi
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
export PGDATA_IMAGE PGDATA_SIZE WG_ADDR
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

# ── is the ceiling actually in effect? ───────────────────────────────────
# ASSERT THE VALUE, NOT THE CONFIG. Everything above proves the compose file
# ASKS for a 10 GB loop-backed volume. This asks the running container what it
# actually got — because the way this breaks is someone deleting the
# driver_opts, at which point Docker silently hands out an ordinary volume on
# the host root filesystem and the "ceiling" becomes the size of the whole box.
# Nothing errors. df is the only thing that ever knows.
log "Verifying the storage ceiling"
_df="$(docker exec skillswap-postgres df -Pk /var/lib/postgresql 2>/dev/null | awk 'NR==2 {print $2" "$5}')"
if [ -n "$_df" ]; then
  _size_kb="${_df%% *}"; _pct="${_df##* }"; _pct="${_pct%\%}"
  _size_gb=$(( _size_kb / 1024 / 1024 ))
  _want_gb="$(printf '%s' "$PGDATA_SIZE" | tr -dc '0-9')"
  # A loop-mounted 10G ext4 reports slightly under 10G (journal + metadata), so
  # compare loosely against the request and loudly against the host disk.
  if [ "$_size_gb" -gt $(( _want_gb + 2 )) ]; then
    warn "─────────────────────────────────────────────────────────────────"
    warn "PGDATA reports ${_size_gb}G, but the ceiling is meant to be ${PGDATA_SIZE}."
    warn "The volume is almost certainly NOT the loop-backed one — check the"
    warn "driver_opts on the pgdata volume in docker-compose.data.yml. Postgres"
    warn "can now fill this whole box, and Nova Flow's Redis lives on it."
    warn "─────────────────────────────────────────────────────────────────"
  else
    ok "PGDATA ceiling in effect: ${_size_gb}G usable, ${_pct}% used"
  fi
  if   [ "${_pct:-0}" -ge 90 ]; then
    warn "PGDATA is ${_pct}% full. At 100% Postgres stops accepting writes."
    warn "  docker exec skillswap-postgres du -sh /var/lib/postgresql/18/docker/*"
  elif [ "${_pct:-0}" -ge 75 ]; then
    warn "PGDATA is ${_pct}% full — plan the resize now, not at 99%."
  fi
else
  warn "could not read df inside skillswap-postgres — ceiling unverified"
fi

log "Data tier up"
dc ps

#!/usr/bin/env bash
#
# SkillSwap AI — ONE command per box, either box, every time.
#
#   deploy/install.sh                 # auto-detects which VPS this is
#   deploy/install.sh --role=data     # the data VPS: Postgres + Redis
#   deploy/install.sh --role=app      # the app VPS: pull, build, migrate, serve
#   deploy/install.sh --rollback      # app VPS: back to the previous image
#
# Modelled on Nova Flow's deploy/install-app.sh, which is the proven shape on
# these two boxes: one script, a --role flag, idempotent, safe to re-run. This
# replaces deploy.sh + data-deploy.sh + setup-data-vps.sh, which were three
# scripts doing what that one does.
#
# EVERY SECRET AND SIZE COMES FROM THE REPO'S .env. Nothing is baked into a
# generated file, nothing is prompted for, nothing is written to /opt. The
# compose files interpolate ${POSTGRES_PASSWORD}, ${REDIS_PASSWORD},
# ${PG_MEM_LIMIT} and the rest straight out of it, so `.env` is the single
# place to look and the single place to change.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

IMAGE="skillswap"
APP_COMPOSE="${ROOT}/docker-compose.yml"
DATA_COMPOSE="${ROOT}/docker-compose.data.yml"
WG_ADDR_DEFAULT="10.77.0.1"

log()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# THE dotenv parser — sourced, never copied. `source .env` is not an option: an
# unquoted value with a space is EXECUTED, and .env holds secrets, not code.
. "$SCRIPT_DIR/lib/dotenv.sh"
# `|| true` is load-bearing: the function returns 1 for an ABSENT key, and an
# assignment carries the rc, so under `set -e` a missing key would abort.
read_env() { skillswap_dotenv_value "${ROOT}/.env" "$1" || true; }

ROLE=""; ROLLBACK_ONLY=0; PULL=1; DEPLOY_BRANCH="${DEPLOY_BRANCH:-}"
CEILING="${PGDATA_CEILING:-}"          # e.g. --ceiling=10G → a hard-capped filesystem
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"
PG_HEALTH_TIMEOUT="${PG_HEALTH_TIMEOUT:-120}"
KEEP_IMAGES="${KEEP_IMAGES:-5}"
EDGE_NET="${EDGE_NET:-edge}"

while [ $# -gt 0 ]; do
  case "$1" in
    --role=app|--role=data) ROLE="${1#--role=}" ;;
    --role)     shift; ROLE="${1:-}" ;;
    --rollback) ROLLBACK_ONLY=1 ;;
    --no-pull)  PULL=0 ;;
    --branch)   shift; DEPLOY_BRANCH="${1:-}" ;;
    --branch=*) DEPLOY_BRANCH="${1#*=}" ;;
    --ceiling)  shift; CEILING="${1:-}" ;;
    --ceiling=*) CEILING="${1#*=}" ;;
    "")         ;;
    *) die "unknown arg: $1
     use --role=app|--role=data, --rollback, --no-pull, --branch <name>, --ceiling <N>G" ;;
  esac
  shift
done

# ── the branch guard, defined early so a test can EXECUTE it ─────────────
assert_deployable_branch() {
  local requested="${1:-}" current default
  current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  default="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
  [ -n "$default" ] || default=main
  if [ -n "$requested" ]; then
    [ "$current" = "$requested" ] || {
      printf '✗ --branch says %s but the checkout is on %s\n' "$requested" "$current" >&2; return 1; }
    printf '! deploying %s (not %s) — explicitly requested\n' "$current" "$default" >&2
  elif [ "$current" != "$default" ]; then
    # git pull fast-forwards THE CURRENT BRANCH, so a box left on a feature
    # branch deploys forever while answering "Already up to date" — truthfully,
    # about the wrong branch. In the sibling deployment that cost five days.
    printf '✗ REFUSING TO DEPLOY: this checkout is on %s, not %s.\n' "$current" "$default" >&2
    printf '  git fetch origin %s && git checkout %s && git pull --ff-only\n' "$default" "$default" >&2
    printf '  or deliberately:  deploy/install.sh --role=app --branch %s\n' "$current" >&2
    return 1
  fi
  printf '%s' "$current"
}
[ "${BRANCH_GUARD_LIB:-0}" = 1 ] && return 0 2>/dev/null || true

# ── which box is this? ───────────────────────────────────────────────────
# By the WireGuard address, because that is the one thing that is already true
# on both machines and cannot be got wrong by editing a file. Nova Flow's
# install-app.sh detects by public IP for the same reason: a role you have to
# declare is a role someone declares wrong at 2am.
detect_role() {
  local addrs; addrs="$(ip -4 -brief addr show 2>/dev/null || true)"
  case "$addrs" in
    *" 10.77.0.1/"*) printf 'data' ;;
    *" 10.77.0.2/"*) printf 'app'  ;;
    *) printf '' ;;
  esac
}
[ -n "$ROLE" ] || ROLE="$(detect_role)"
[ -n "$ROLE" ] || die "could not tell which VPS this is (no 10.77.0.1 or 10.77.0.2 on wg0).
     Pass --role=app or --role=data, and check: systemctl status wg-quick@wg0"

# ── shared preflight ─────────────────────────────────────────────────────
docker info >/dev/null 2>&1 || die "Docker engine is not running"
[ -f "${ROOT}/.env" ] || die ".env not found in ${ROOT} — copy .env.example and fill it in"

WG_ADDR="$(read_env WG_ADDR)"; WG_ADDR="${WG_ADDR:-$WG_ADDR_DEFAULT}"

tcp_open() { timeout "${3:-5}" bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; }
url_host() { printf '%s' "$1" | sed -E 's#^[a-z+]+://##I; s#^.*@##; s#[:/?].*$##'; }
url_port() { printf '%s' "$1" | sed -E 's#^[a-z+]+://##I; s#^.*@##; s#^[^:/?]*##; s#^:([0-9]+).*#\1#; s#^[^0-9].*##'; }

# health_gate <compose-file> <service> <timeout>
health_gate() {
  local f="$1" svc="$2" limit="$3" cid status state deadline
  cid="$(docker compose -f "$f" ps -q "$svc")"
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
  echo; warn "${svc} did not become healthy — last 40 log lines:"
  docker compose -f "$f" logs --tail 40 "$svc" || true
  return 1
}

##############################################################################
# DATA ROLE — Postgres + Redis, tunnel-bound, on this box
##############################################################################
install_data() {
  log "SkillSwap data tier  (this box: ${WG_ADDR})"
  [ "$(id -u)" -eq 0 ] || die "run as root (it touches mounts and ufw)"

  [ -n "$(read_env POSTGRES_PASSWORD)" ] || die "POSTGRES_PASSWORD is not set in .env"
  [ -n "$(read_env REDIS_PASSWORD)" ]    || die "REDIS_PASSWORD is not set in .env — the redis
     service refuses to start authless, by design"
  ok ".env carries both credentials"

  # The tunnel address must EXIST before anything publishes on it. A container
  # that cannot bind does not retry into success; it is simply down, and after a
  # reboot that reads as "the database is gone".
  ip -4 addr show 2>/dev/null | grep -q "inet ${WG_ADDR}/" \
    || die "wg0 does not hold ${WG_ADDR} — Postgres and Redis publish on it and
     cannot start without it:  systemctl start wg-quick@wg0"
  ok "wg0 holds ${WG_ADDR}"

  # ── storage ────────────────────────────────────────────────────────────
  # DEFAULT: a plain directory, exactly like Nova Flow's /var/lib/nova-redis.
  # Ten gigabytes of storage is then an allocation you size the box for and
  # watch, which is what that phrase usually means and what Nova does.
  #
  # --ceiling=10G instead builds a filesystem in a file and mounts it, so
  # Postgres hits ENOSPC at exactly that size rather than filling a box that
  # also holds Nova Flow's production Redis. That is a real guarantee and it
  # costs a loop device; opt into it deliberately.
  local mount; mount="$(read_env PGDATA_HOST_PATH)"
  mount="${mount:-/var/lib/skillswap-postgres}"
  mkdir -p "$mount"
  if [ -n "$CEILING" ]; then
    PGDATA_HOST_PATH="$mount" PGDATA_SIZE="$CEILING" \
      bash "${SCRIPT_DIR}/ensure-pgdata.sh" --size "$CEILING" \
      || die "could not build the ${CEILING} filesystem"
  else
    ok "PGDATA: ${mount} (plain directory — pass --ceiling=10G for a hard cap)"
  fi
  df -h "$mount" | tail -1 | sed 's/^/    /'

  # Tuning lives in one file so a resize is one edit. Missing is fine: the
  # compose fallbacks are the same profile.
  local tuning="${ROOT}/deploy/postgres/pg-tuning.env"
  if [ -f "$tuning" ]; then set -a; . "$tuning"; set +a
    ok "tuning: mem=${PG_MEM_LIMIT:-?} cpus=${PG_CPUS:-?} redis=${REDIS_MAXMEMORY:-?}"
  fi
  export PGDATA_HOST_PATH="$mount" WG_ADDR

  docker compose -f "$DATA_COMPOSE" config -q || die "docker-compose.data.yml is invalid"

  log "Starting postgres"
  docker compose -f "$DATA_COMPOSE" up -d --remove-orphans postgres || true
  health_gate "$DATA_COMPOSE" postgres "$PG_HEALTH_TIMEOUT" \
    || die "Postgres is not healthy. The app tier was not touched."
  ok "postgres is healthy"

  log "Starting redis"
  docker compose -f "$DATA_COMPOSE" up -d --remove-orphans redis || true
  # Redis is fail-open for this app by design (cache, rate limits and locks all
  # no-op without it), so an unhealthy Redis must not stop a healthy Postgres.
  health_gate "$DATA_COMPOSE" redis 60 \
    && ok "redis is healthy" \
    || warn "redis is NOT healthy — the app degrades rather than failing, but fix it"

  # ── prove it from outside the containers ───────────────────────────────
  # The healthchecks above run INSIDE each container over its own loopback.
  # They say nothing about the published tunnel address, which is the only path
  # the app actually uses.
  log "Verifying the tunnel endpoints"
  local pgp rp
  pgp="$(read_env POSTGRES_HOST_PORT)"; pgp="${pgp:-5432}"
  rp="$(read_env REDIS_HOST_PORT)";     rp="${rp:-6380}"
  tcp_open "$WG_ADDR" "$pgp" 5 && ok "postgres on ${WG_ADDR}:${pgp}" \
    || die "postgres is healthy INSIDE its container but nothing is listening on
     ${WG_ADDR}:${pgp} — check the ports: entry in docker-compose.data.yml"
  tcp_open "$WG_ADDR" "$rp" 5 && ok "redis on ${WG_ADDR}:${rp}" \
    || warn "nothing listening on ${WG_ADDR}:${rp}"

  # A data port on a public interface is the failure that never announces
  # itself: Docker DNATs before ufw's INPUT chain, so the firewall does not
  # stop it and `ufw status` still reports the port closed.
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "^(0\.0\.0\.0|\[::\]|\*):(${pgp}|${rp})$"; then
    warn "─────────────────────────────────────────────────────────────────"
    warn "A DATA PORT IS BOUND TO ALL INTERFACES. ufw will NOT save you."
    warn "Restore the '${WG_ADDR}:' prefix on the ports: entry and re-run."
    warn "─────────────────────────────────────────────────────────────────"
  else
    ok "data ports are tunnel-bound, not public"
  fi

  # Defence in depth, never the wall. Idempotent; ufw dedupes.
  if command -v ufw >/dev/null 2>&1; then
    ufw allow in on wg0 from 10.77.0.2 to any port "$pgp" proto tcp >/dev/null 2>&1 || true
    ufw allow in on wg0 from 10.77.0.2 to any port "$rp"  proto tcp >/dev/null 2>&1 || true
    ok "ufw: ${pgp} and ${rp} allowed on wg0 from the app peer only"
  fi

  log "Data tier up"
  docker compose -f "$DATA_COMPOSE" ps
  printf '\n  On the APP VPS, .env wants:\n'
  printf '    DATABASE_URL=postgresql://%s:<password>@%s:%s/%s\n' \
    "$(read_env POSTGRES_USER || echo skillswap)" "$WG_ADDR" "$pgp" \
    "$(read_env POSTGRES_DB || echo skillswapaidb)"
  printf '    REDIS_URL=redis://%s:%s/0\n    REDIS_PASSWORD=<the same one>\n\n' "$WG_ADDR" "$rp"
}

##############################################################################
# APP ROLE — pull, build, migrate, serve, health-gate, roll back
##############################################################################

install_app() {
  log "SkillSwap app tier"
  if [ "$ROLLBACK_ONLY" = 1 ]; then
    docker image inspect "${IMAGE}:rollback" >/dev/null 2>&1 \
      || die "no ${IMAGE}:rollback image to roll back to"
    docker image tag "${IMAGE}:rollback" "${IMAGE}:latest"
    docker compose -f "$APP_COMPOSE" up -d --remove-orphans web
    docker compose -f "$APP_COMPOSE" ps; return 0
  fi

  local dburl redisurl
  dburl="$(read_env DATABASE_URL)"; redisurl="$(read_env REDIS_URL)"
  [ -n "$dburl" ] || die "DATABASE_URL is not set in .env"
  docker compose -f "$APP_COMPOSE" config -q || die "docker-compose.yml is invalid"

  # POSTGRES IS NOT FAIL-OPEN. Redis dark degrades the app; the database dark IS
  # the app being down. Hard stop, taken BEFORE anything is rebuilt, so the
  # currently running container keeps serving.
  local h p; h="$(url_host "$dburl")"; p="$(url_port "$dburl")"; p="${p:-5432}"
  tcp_open "$h" "$p" 8 && ok "postgres reachable at ${h}:${p}" \
    || die "cannot reach Postgres at ${h}:${p} — NOTHING was changed.
     On the data VPS:  deploy/install.sh --role=data"
  if [ -n "$redisurl" ]; then
    local rh rp2; rh="$(url_host "$redisurl")"; rp2="$(url_port "$redisurl")"; rp2="${rp2:-6379}"
    tcp_open "$rh" "$rp2" 5 && ok "redis reachable at ${rh}:${rp2}" \
      || warn "redis at ${rh}:${rp2} did not answer — the app is fail-open"
  fi

  local branch; branch="$(assert_deployable_branch "$DEPLOY_BRANCH")" || die "refusing to deploy"
  [ "$PULL" = 1 ] && { log "Pulling"; git pull --ff-only || die "git pull failed (use --no-pull)"; }
  local sha; sha="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
  log "Deploying ${branch} @ ${sha}"

  docker network inspect "$EDGE_NET" >/dev/null 2>&1 \
    || { docker network create "$EDGE_NET" >/dev/null && ok "created network ${EDGE_NET}"; }

  docker image inspect "${IMAGE}:latest" >/dev/null 2>&1 \
    && docker image tag "${IMAGE}:latest" "${IMAGE}:rollback" \
    && ok "snapshotted ${IMAGE}:rollback"

  # Trim BEFORE the build — the build is what needs the space. `image prune -f`
  # only reclaims DANGLING images, and a tagged :sha never is, so this ran
  # unbounded until a disk filled.
  local stale
  stale="$(docker image ls "${IMAGE}" --format '{{.CreatedAt}}'$'\t''{{.Tag}}' 2>/dev/null \
           | sort -r | awk -F'\t' '$2!="latest" && $2!="rollback" && $2!="<none>" {print $2}' \
           | tail -n +"${KEEP_IMAGES}" || true)"
  [ -n "$stale" ] && printf '%s\n' "$stale" | while IFS= read -r t; do
    [ -n "$t" ] && docker image rm "${IMAGE}:${t}" >/dev/null 2>&1 && ok "dropped ${IMAGE}:${t}"
  done

  log "Building (git ${sha})"
  SOURCE_COMMIT="$sha" docker compose -f "$APP_COMPOSE" build

  # ONE SHOT, before the app tier. Two gunicorn workers both running
  # `alembic upgrade head` in their lifespan is two processes racing one DDL.
  log "Applying migrations"
  docker compose -f "$APP_COMPOSE" run --rm --no-deps -T -w /app/backend web alembic upgrade head \
    || die "migrations FAILED — the previous container is still serving. Fix and re-run."
  # ASSERT THE VALUE: `upgrade head` exits 0 when it had nothing to do,
  # including against a database that is not the one you think it is.
  docker compose -f "$APP_COMPOSE" run --rm --no-deps -T -w /app/backend web alembic current 2>&1 \
    | grep -q '(head)' || die "the schema is not at head after a successful upgrade —
     check that DATABASE_URL points where you think it does"
  ok "schema at head"

  log "Starting web"
  docker compose -f "$APP_COMPOSE" up -d --remove-orphans web || true
  # The container's own HEALTHCHECK greps "database":"up" out of /health rather
  # than trusting the status code — /health answers 200 with the database down.
  if ! health_gate "$APP_COMPOSE" web "$HEALTH_TIMEOUT"; then
    if docker image inspect "${IMAGE}:rollback" >/dev/null 2>&1; then
      warn "Auto-rolling back"
      docker image tag "${IMAGE}:rollback" "${IMAGE}:latest"
      docker compose -f "$APP_COMPOSE" up -d --remove-orphans web
      die "Deploy failed and was rolled back. The site is on the last good build."
    fi
    die "Deploy failed and there is no rollback image."
  fi
  ok "web is healthy (database confirmed up)"

  log "Deploy complete  (${branch} @ ${sha})"
  docker compose -f "$APP_COMPOSE" ps
  printf '\n  curl -fsS localhost:%s/health\n\n' "$(read_env APP_HOST_PORT || echo 8001)"
}

case "$ROLE" in
  data) install_data ;;
  app)  install_app  ;;
  *)    die "unknown role: ${ROLE}" ;;
esac

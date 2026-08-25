#!/usr/bin/env bash
#
# setup-data-vps.sh — ONE-TIME provisioning of the data tier on the Redis VPS
# (80.190.73.191). Run as root, ON THAT BOX. Idempotent: safe to re-run, and it
# refuses every step that would destroy data rather than "fixing" it.
#
#   deploy/setup-data-vps.sh
#   deploy/setup-data-vps.sh --size 20G      # a bigger ceiling on a fresh box
#
# What it does:
#   1. installs Docker if the box has none (today it runs Redis natively from apt)
#   2. creates the ENFORCED 10 GB filesystem PGDATA lives on
#   3. opens 5432 + 6380 on the tunnel, from the app VPS peer only
#   4. installs the systemd unit that starts the stack AFTER wg0 exists
#
# It does NOT start Postgres or Redis — deploy/data-deploy.sh does that, and
# keeping "provision" and "deploy" apart is what makes the second one safe to
# run on every release.
set -euo pipefail

# ── config ───────────────────────────────────────────────────────────────
APP_WG_ADDR="${APP_WG_ADDR:-10.77.0.2}"      # the app VPS inside the tunnel
WG_ADDR="${WG_ADDR:-10.77.0.1}"              # this box inside the tunnel
PG_PORT="${POSTGRES_HOST_PORT:-5432}"
REDIS_PORT="${REDIS_HOST_PORT:-6380}"        # 6379 here is Nova Flow's native Redis
SIZE="${PGDATA_SIZE:-10G}"
BASE="${SKILLSWAP_BASE:-/srv/skillswap}"
IMG="${PGDATA_IMAGE:-${BASE}/pgdata.img}"
DO_FILESYSTEM=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

log()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --size)   shift; SIZE="${1:-}"; [ -n "$SIZE" ] || die "--size needs a value (e.g. 10G)" ;;
    --size=*) SIZE="${1#*=}" ;;
    --filesystem) DO_FILESYSTEM=1 ;;
    *) die "unknown arg: $1  (use --size <N>G, --filesystem)" ;;
  esac
  shift
done

[ "$(id -u)" -eq 0 ] || die "run as root"

# ── capacity sanity ──────────────────────────────────────────────────────
# This box already runs Nova Flow's production Redis at maxmemory 2gb. Adding
# 640m of Redis and 256m of Postgres on top is fine on a 4 GB box and is not
# fine on a 2 GB one — and the way you find out is Nova's Redis being OOM-killed
# at 3am, which reads as a Nova incident, not a SkillSwap one.
_ram_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"
if [ "${_ram_mb:-0}" -gt 0 ] && [ "$_ram_mb" -lt 3800 ]; then
  warn "this box reports ${_ram_mb} MB of RAM. Nova Flow's Redis (2gb maxmemory)"
  warn "plus SkillSwap's Redis (640m) plus Postgres (256m) plus Docker wants ~4 GB."
  warn "Continuing, but watch for OOM kills — in BOTH apps."
else
  ok "RAM: ${_ram_mb} MB"
fi

_want_kb=$(( $(printf '%s' "$SIZE" | tr -dc '0-9') * 1024 * 1024 + 2 * 1024 * 1024 ))
_avail_kb="$(df -Pk / 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -n "${_avail_kb:-}" ] && [ "$_avail_kb" -lt "$_want_kb" ]; then
  die "only $(( _avail_kb / 1024 / 1024 ))G free on / — a ${SIZE} image plus headroom needs $(( _want_kb / 1024 / 1024 ))G"
fi
ok "disk: $(( ${_avail_kb:-0} / 1024 / 1024 ))G free on /"

# ── 1. Docker ────────────────────────────────────────────────────────────
log "Docker"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "docker + compose plugin already installed ($(docker --version))"
else
  warn "installing Docker CE from Docker's own apt repo"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
      || curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
      || die "could not fetch Docker's apt key"
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  ok "installed $(docker --version)"
fi

# ── 2. the PGDATA filesystem — NORMALLY NOT DONE HERE ────────────────────
#
# The 10 GB ceiling now lives in docker-compose.data.yml: the `pgdata` volume is
# `type: ext4, o: loop` over an image file, and the `bootstrap` service creates
# and formats that image before anything mounts it. So a plain
# `docker compose -f docker-compose.data.yml up -d` provisions its own storage
# and this script does not need to.
#
# The one reason to do it from the host instead is not wanting to grant
# `privileged` to the bootstrap container — mkfs and loop devices are
# kernel-level and no unprivileged container can do them. Pass --filesystem and
# this does the identical work as root, after which bootstrap finds everything
# in place and exits immediately.
if [ "$DO_FILESYSTEM" = 1 ]; then
  log "PGDATA filesystem (${SIZE}, enforced) — host-side, --filesystem"
  mkdir -p "$(dirname "$IMG")"
  if [ -f "$IMG" ]; then
    ok "image exists: ${IMG} ($(du -h "$IMG" | cut -f1) allocated)"
  else
    if command -v fallocate >/dev/null 2>&1 && fallocate -l "$SIZE" "$IMG" 2>/dev/null; then
      :
    else
      warn "fallocate unavailable here — falling back to dd (slower)"
      dd if=/dev/zero of="$IMG" bs=1M \
         count="$(( $(printf '%s' "$SIZE" | tr -dc '0-9') * 1024 ))" status=none
    fi
    ok "created ${IMG} (${SIZE})"
  fi
  # NEVER re-mkfs an image that already carries a filesystem. That single guard
  # is the difference between "re-running the setup script" and "erasing the
  # database", and re-running a setup script is exactly what people do.
  if blkid "$IMG" >/dev/null 2>&1; then
    ok "filesystem already present on ${IMG} — not touching it"
  else
    # -m 1: ext4 reserves 5% for root BY DEFAULT and Postgres is not root, so a
    # 10G volume would hand it 9.5G and refuse the rest with a confusing ENOSPC
    # while df still showed free space.
    mkfs.ext4 -q -m 1 -F "$IMG"
    ok "mkfs.ext4 on ${IMG} (1% reserve, not the 5% default)"
  fi
else
  ok "PGDATA filesystem: left to the compose `bootstrap` service (--filesystem to do it here)"
fi

# ── 3. firewall ──────────────────────────────────────────────────────────
#
# READ THIS BEFORE TRUSTING IT. These rules are DEFENCE IN DEPTH, not the wall.
# Docker publishes ports AROUND the firewall: for any non-loopback publish it
# inserts a DNAT rule into the nat table's DOCKER chain, and nat/PREROUTING is
# traversed BEFORE filter/INPUT where ufw lives. A ufw deny does not stop it and
# `ufw status` will happily report the port closed while it is open.
#
# What actually keeps this database off the internet is the BIND ADDRESS in
# docker-compose.data.yml — "10.77.0.1:5432:5432", never "5432:5432". Do not
# delete those nine characters.
log "Firewall (wg0, from ${APP_WG_ADDR} only)"
if command -v ufw >/dev/null 2>&1; then
  ufw allow in on wg0 from "$APP_WG_ADDR" to any port "$PG_PORT" proto tcp    >/dev/null
  ufw allow in on wg0 from "$APP_WG_ADDR" to any port "$REDIS_PORT" proto tcp >/dev/null
  ok "allowed ${PG_PORT}/tcp and ${REDIS_PORT}/tcp on wg0 from ${APP_WG_ADDR}"
  ufw status | sed 's/^/    /' | head -20
else
  warn "ufw is not installed — skipping. The bind address is still the real wall."
fi

# ── 4. WireGuard presence ────────────────────────────────────────────────
# The containers PUBLISH on ${WG_ADDR}, which does not exist until wg0 is up.
# Bind failures here are not subtle — "cannot assign requested address" and the
# container never starts — but they happen at REBOOT, hours after the change
# that "worked".
log "WireGuard"
if ip -brief addr show wg0 2>/dev/null | grep -q "$WG_ADDR"; then
  ok "wg0 holds ${WG_ADDR}"
else
  warn "wg0 does not currently hold ${WG_ADDR}. The data containers cannot bind"
  warn "until it does: systemctl status wg-quick@wg0  (see APP_LLM"
  warn "deploy/redis-vps/README.md for how this tunnel was set up)"
fi

# ── 5. boot ordering ─────────────────────────────────────────────────────
# Docker starts at boot and would try to bind ${WG_ADDR} before wg-quick@wg0 has
# created it. This unit is the same ordering the existing native Redis already
# gets from a drop-in on this box, for the same reason.
log "systemd unit"
UNIT_SRC="${SCRIPT_DIR}/skillswap-data.service"
[ -f "$UNIT_SRC" ] || die "missing ${UNIT_SRC}"
sed -e "s#@REPO_ROOT@#${ROOT}#g" "$UNIT_SRC" > /etc/systemd/system/skillswap-data.service
systemctl daemon-reload
systemctl enable skillswap-data.service >/dev/null 2>&1 || true
ok "installed + enabled skillswap-data.service (After=wg-quick@wg0, docker)"

cat <<EOF

======================================================================
 Data VPS provisioned.

   PGDATA image : ${IMG}  (${SIZE}, enforced ceiling)
   Postgres     : ${WG_ADDR}:${PG_PORT}   (tunnel only)
   Redis        : ${WG_ADDR}:${REDIS_PORT}   (tunnel only)

 Next, on THIS box:
   1. put POSTGRES_PASSWORD and REDIS_PASSWORD in ${ROOT}/.env
        openssl rand -hex 32     # hex, NOT base64: base64 emits / and +,
                                 # and a / in a password inside a URL is a
                                 # hard parse failure, not a warning
   2. docker compose -f docker-compose.data.yml up -d
        (or ${SCRIPT_DIR}/data-deploy.sh for the health-gated version)

 Then, on the APP VPS, point .env at this box:
   DATABASE_URL=postgresql://skillswap:<pw>@${WG_ADDR}:${PG_PORT}/skillswapaidb
   REDIS_URL=redis://default:<pw>@${WG_ADDR}:${REDIS_PORT}/0
======================================================================
EOF

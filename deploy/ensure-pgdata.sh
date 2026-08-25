#!/usr/bin/env bash
#
# ensure-pgdata.sh — the 10 GB filesystem PGDATA lives on. Run as root on the
# DATA host. Idempotent: safe to re-run, and it refuses anything that would
# destroy data rather than "fixing" it.
#
#   deploy/ensure-pgdata.sh              # 10G at /srv/skillswap/pgdata
#   deploy/ensure-pgdata.sh --size 20G
#
# WHY THIS IS A SCRIPT AND NOT IN THE COMPOSE FILE — measured twice, the hard
# way:
#
#   1. `driver_opts: {type: ext4, o: loop}` does NOT work. Docker's local driver
#      calls the mount SYSCALL; `loop` is a feature of the mount COMMAND, which
#      runs losetup first. The kernel gets "loop" as filesystem data and rejects
#      it:  `data: loop: invalid argument`.
#   2. Doing it from a privileged container instead needs the mount to escape
#      its namespace (rshared), and a container cannot honestly verify that it
#      did — the check reads its own mount table and vouches for a mount only it
#      can see.
#
# Loop-mounting is a root-on-the-host operation. So it happens here, once, and
# `deploy/toolkit` binds the result. deploy/toolkit deliberately does not manage
# storage, which is the same division Nova Flow draws with ensure-luks-pgdata.sh.
#
# WHY A FILESYSTEM AT ALL: Docker cannot size-limit a volume. There is no
# `--storage-opt size=` for volumes, and the one that exists applies to a
# container's writable layer and needs an xfs+pquota backend. A plain directory
# is not a ceiling, it is a hope — and this box also holds Nova Flow's
# production Redis, so a runaway table here is an outage over there.
set -euo pipefail

SIZE="${PGDATA_SIZE:-10G}"
BASE="${SKILLSWAP_BASE:-/srv/skillswap}"
IMG="${PGDATA_IMAGE:-${BASE}/pgdata.img}"
MNT="${PGDATA_HOST_PATH:-${BASE}/pgdata}"

ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --size)   shift; SIZE="${1:-}"; [ -n "$SIZE" ] || die "--size needs a value (e.g. 10G)" ;;
    --size=*) SIZE="${1#*=}" ;;
    *) die "unknown arg: $1  (use --size <N>G)" ;;
  esac
  shift
done
[ "$(id -u)" -eq 0 ] || die "run as root — mkfs and loop devices are kernel-level"

printf '\n\033[1;36m▶ PGDATA filesystem (%s, enforced)\033[0m\n' "$SIZE"
mkdir -p "$(dirname "$IMG")" "$MNT"

_need_kb=$(( $(printf '%s' "$SIZE" | tr -dc '0-9') * 1024 * 1024 ))
_free_kb="$(df -Pk "$(dirname "$IMG")" 2>/dev/null | awk 'NR==2 {print $4}')"
if [ ! -f "$IMG" ] && [ -n "${_free_kb:-}" ] && [ "$_free_kb" -lt "$_need_kb" ]; then
  die "only $(( _free_kb / 1024 / 1024 ))G free where the image would go, and it needs $(( _need_kb / 1024 / 1024 ))G"
fi

if [ -f "$IMG" ]; then
  ok "image exists: ${IMG} ($(du -h "$IMG" | cut -f1) allocated)"
else
  if command -v fallocate >/dev/null 2>&1 && fallocate -l "$SIZE" "$IMG" 2>/dev/null; then :; else
    warn "fallocate unavailable here — falling back to dd (slower)"
    dd if=/dev/zero of="$IMG" bs=1M count="$(( $(printf '%s' "$SIZE" | tr -dc '0-9') * 1024 ))" status=none
  fi
  ok "created ${IMG} (${SIZE})"
fi

# NEVER re-mkfs an image that already carries a filesystem. That single guard is
# the difference between re-running this script and erasing the database — and
# re-running a setup script is exactly what people do.
if blkid "$IMG" >/dev/null 2>&1; then
  ok "filesystem already present — not touching it"
else
  # -m 1: ext4 reserves 5% for root BY DEFAULT and Postgres is not root, so a
  # 10G volume would hand it 9.5G and refuse the rest with a confusing ENOSPC
  # while df still showed free space.
  mkfs.ext4 -q -m 1 -F "$IMG"
  ok "mkfs.ext4 (1% reserve, not the 5% default)"
fi

# fstab BEFORE mount, so a reboot brings it back. `nofail` keeps a missing image
# out of emergency mode; `noatime` is one less write per read on a DB volume.
if grep -qsF " ${MNT} " /etc/fstab; then
  ok "fstab entry present"
else
  printf '%s %s ext4 loop,nofail,noatime 0 2\n' "$IMG" "$MNT" >> /etc/fstab
  ok "added fstab entry (survives reboot)"
fi

if mountpoint -q "$MNT"; then
  ok "${MNT} already mounted"
else
  mount "$MNT" || die "could not mount ${MNT} — check /etc/fstab and losetup -a"
  ok "mounted ${MNT}"
fi
df -h "$MNT" | tail -1 | sed 's/^/    /'

printf '\nSet PGDATA_HOST_PATH=%s in .env, then:\n  sudo deploy/toolkit/deploy.sh up\n\n' "$MNT"

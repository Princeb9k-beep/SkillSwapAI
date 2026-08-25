# SkillSwap AI — deploy

**One command per box. Either box. Every time.**

```sh
deploy/install.sh          # auto-detects which VPS it is from the wg0 address
```

Modelled on Nova Flow's `deploy/install-app.sh`, which is the proven shape on
these two machines: one script, a `--role` flag, idempotent, safe to re-run.

```
app VPS  (wg 10.77.0.2)                   data VPS (wg 10.77.0.1)
┌────────────────────────────────┐  wg0   ┌──────────────────────────────┐
│ nginx :80 :443  (Nova Flow's)  │◄──────►│ redis-server  (Nova's, apt)  │
│   └── skillswap vhost ─────────┼───────►│                              │
│ skillswap-web  1 CPU / 1g      │        │ skillswap-postgres  256M     │
│   gunicorn · 127.0.0.1:8001    │        │   └ 10.77.0.1:5432           │
└────────────────────────────────┘        │ skillswap-redis     512M     │
                                          │   └ 10.77.0.1:6380           │
                                          └──────────────────────────────┘
```

## Everything comes from `.env`

Nothing is baked into a generated file, nothing is prompted for, nothing is
written to `/opt`. Both compose files interpolate straight out of the repo's
`.env`, so it is the single place to look and the single place to change.

**Data VPS** — four lines are all it needs:

```sh
POSTGRES_USER=skillswap
POSTGRES_PASSWORD=<openssl rand -hex 32>
POSTGRES_DB=skillswapaidb
REDIS_PASSWORD=<openssl rand -hex 32>
```

**App VPS**:

```sh
DATABASE_URL=postgresql://skillswap:<same PG password>@10.77.0.1:5432/skillswapaidb
REDIS_URL=redis://10.77.0.1:6380/0
REDIS_PASSWORD=<same Redis password>
GUNICORN_WORKERS=1
APP_SECRET_KEY=<openssl rand -hex 32>
GROQ_API_KEY=<your key>
```

Generate with **`openssl rand -hex 32`, not base64**: base64 emits `/`, and a
`/` in a password inside a URL is a hard parse failure — the parser reads the
text after it as the port. The symptom is "cannot reach Postgres", which points
at the tunnel rather than the password.

`POSTGRES_PASSWORD`, `POSTGRES_USER` and `POSTGRES_DB` are read **once**, during
the first `initdb` on an empty data directory. Change one later and the
container starts fine while the app gets "role does not exist". Pick them before
the first run.

## Bring-up

**Data VPS first** — the app refuses to deploy against a database it cannot
reach, deliberately, before touching anything:

```sh
git clone https://github.com/Princeb9k-beep/SkillSwapAI /srv/apps/SkillSwapAiApp/SkillSwapAI
cd /srv/apps/SkillSwapAiApp/SkillSwapAI
command -v docker || curl -fsSL https://get.docker.com | sh
$EDITOR .env                        # the four lines above
sudo deploy/install.sh              # detects --role=data from wg0
```

**App VPS:**

```sh
cd /srv/apps/SkillSwapAiApp/SkillSwapAI
$EDITOR .env
sudo deploy/install.sh              # detects --role=app
curl -fsS localhost:8001/health | python3 -m json.tool
```

**Every deploy after that is the same command.** On the app box it pulls,
builds, migrates as a one-shot, health-gates and rolls back on failure. On the
data box it re-reads `.env`, restarts only what changed, and re-proves the
tunnel endpoints.

```sh
sudo deploy/install.sh --rollback     # app VPS: back to the previous image
sudo deploy/install.sh --no-pull      # deploy the working tree
sudo deploy/install.sh --branch X     # deploy a feature branch ON PURPOSE
```

## The 10 GB

By default Postgres writes to `/var/lib/skillswap-postgres`, a plain directory
— exactly like Nova Flow's `/var/lib/nova-redis`. Ten gigabytes is then an
allocation you size the box for and watch.

For a **hard ceiling** Postgres cannot exceed, run the data install once with:

```sh
sudo deploy/install.sh --role=data --ceiling=10G
```

That builds a filesystem in a file and mounts it at that path, with an fstab
entry so it survives a reboot. Postgres then hits ENOSPC at exactly 10G instead
of filling a box that also holds Nova Flow's production Redis.

Docker cannot size-limit a volume, so this is the only way to make the number a
guarantee. Two attempts to do it from the compose file failed and are worth not
repeating: `driver_opts: {type: ext4, o: loop}` is rejected by the kernel
(Docker calls the mount *syscall*; `loop` is a feature of the mount *command*),
and doing it from a privileged container needs the mount to escape its
namespace — which a container cannot honestly verify.

## Things that are not obvious

**"2 threads" is 2 workers.** `--threads` is a no-op under `UvicornWorker`.

**Two workers currently break live messaging.** `app/realtime.py`'s hub and
`app/routers/rooms.py`'s room map are process-local dicts, and a WebSocket
cannot be routed to a chosen worker — so a message written by one worker never
reaches a socket held by the other, silently. Until that fans out over Redis
pub/sub (`realtime.py`'s own docstring names the fix), keep
`GUNICORN_WORKERS=1`.

**The bind is the wall, not the firewall.** Docker publishes ports *around* ufw:
a non-loopback publish gets a DNAT rule in `nat/PREROUTING`, traversed before
`filter/INPUT`. `"5432:5432"` would put the database on the internet while
`ufw status` reports the port closed. Every publish names `10.77.0.1` or
`127.0.0.1`, and the installer re-checks the actual listening sockets after it
starts.

**The health gate asserts the value.** `/health` returns 200 with
`"database":"down"`, so the container's healthcheck greps `"database":"up"`. The
installer also re-checks `alembic current` reports `(head)`, because `upgrade
head` exits 0 when it had nothing to do — including against the wrong database.

**`install.sh` refuses a non-default branch.** `git pull` fast-forwards the
*current* branch, so a box left on a feature branch deploys forever while
answering "Already up to date" — truthfully, about the wrong branch.

## The public URL

Needs the nginx vhost in the Nova Flow repo (only one container can hold
80/443), plus DNS and an Origin CA cert. Until then `127.0.0.1:8001` is the only
door, and deliberately so.

## When something is wrong

| symptom | look at |
|---|---|
| "could not tell which VPS this is" | `wg show wg0` — the role is detected from the tunnel address. Or pass `--role=` |
| "cannot reach Postgres … NOTHING was changed" | the data box: `sudo deploy/install.sh --role=data` |
| health gate failed | it already rolled back. `docker compose logs --tail=80 web` |
| `address already in use` on the data box | a port collides with Nova's. `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` in `.env` |
| everything green, browser shows old code | the installer prints `branch @ sha` every run. Read it before debugging anything else |

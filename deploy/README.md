# SkillSwap AI — Docker deploy

Two VPSes, already in use by the sibling Nova Flow deployment, already linked by
WireGuard. SkillSwap adds one container to each.

```
app VPS 82.197.64.18                      data VPS 80.190.73.191
┌────────────────────────────────┐  wg0   ┌──────────────────────────────┐
│ nginx  :80 :443  (Nova Flow's) │10.77.0.2│ redis-server  (Nova's, apt)  │
│   ├── nova-flow.pro ──► web    │◄───────►│   bind 127.0.0.1, 10.77.0.1  │
│   └── skillswap    ──► ────────┼─┐:51820 │                              │
│                                │ │  udp  │ docker:                      │
│ docker `edge` network          │ │       │   skillswap-postgres  256M   │
│   skillswap-web  1 CPU / 1g    │◄┘       │     └ 10.77.0.1:5432  10G    │
│     gunicorn, 2 workers        │────────►│   skillswap-redis     512M   │
└────────────────────────────────┘         │     └ 10.77.0.1:6380         │
                                           └──────────────────────────────┘
```

| | allocation | where it is set |
|---|---|---|
| app | 1.0 CPU, 1g, **2 gunicorn workers** | `docker-compose.yml`, `Dockerfile` |
| Postgres | 1.0 CPU, 256M, **10G enforced** | `docker-compose.data.yml`, `deploy/postgres/pg-tuning.env` |
| Redis | 512M maxmemory (640m container) | `docker-compose.data.yml` |

## Three things that are not obvious

**"2 threads" is 2 WORKERS.** `--threads` is a no-op under `UvicornWorker` — it
applies to gthread/sync workers only. Passing it would change nothing while
making the fleet read as if it had twice the lanes it has.

**Two workers currently break live messaging.** `backend/app/realtime.py`'s hub
and `app/routers/rooms.py`'s room map are process-local dicts, and a WebSocket
cannot be routed to a chosen worker — so a message written by worker A never
reaches a socket held by worker B, silently. Until that fans out over Redis
pub/sub (`realtime.py`'s own docstring names the fix), set `GUNICORN_WORKERS=1`
in `.env` if live messaging matters more than the second lane.

**The bind address is the wall, not the firewall.** Docker publishes ports
*around* ufw: a non-loopback publish gets a DNAT rule in `nat/PREROUTING`, which
is traversed before `filter/INPUT`. So `"5432:5432"` puts the database on the
internet while `ufw status` still reports the port closed, and nothing logs it.
Every publish here names `10.77.0.1` or `127.0.0.1`. Guarded by
`backend/tests/test_deploy_config.py`, and checked again at runtime by
`data-deploy.sh` reading the actual listening sockets.

## Bring-up

**1 — data VPS** (as root):

```sh
git clone <repo> /srv/skillswap/app && cd /srv/skillswap/app
cp .env.example .env && nano .env          # POSTGRES_PASSWORD, REDIS_PASSWORD
                                           # openssl rand -base64 32
deploy/setup-data-vps.sh                   # docker, the 10G mount, ufw, systemd
deploy/data-deploy.sh                      # start, health-gate, verify the tunnel
```

`setup-data-vps.sh` is one-time and idempotent; `data-deploy.sh` runs on every
change. The first bring-up starts with an empty mount, which `data-deploy.sh`
refuses by default — that guard exists because an empty mount is
indistinguishable from a detached one, and Postgres would happily `initdb` a
blank cluster beside real data. Say so explicitly the first time:

```sh
PGDATA_ALLOW_EMPTY=1 deploy/data-deploy.sh
```

**2 — app VPS** (as root). Prove the tunnel *before* deploying:

```sh
docker run --rm --network host postgres:18-alpine pg_isready -h 10.77.0.1 -p 5432
docker run --rm --network host redis:7-alpine redis-cli -u "$REDIS_URL" ping   # PONG

git clone <repo> /var/www/skillswap && cd /var/www/skillswap
cp .env.example .env && nano .env          # DATABASE_URL + REDIS_URL at 10.77.0.1
deploy/deploy.sh
```

**3 — the edge**, in the Nova Flow repo (`/var/www/app`):

```sh
echo 'SKILLSWAP_DOMAIN=skillswap.example.com' >> .env
deploy/deploy-docker.sh                    # rebuilds nginx with the new vhost
```

Until a Cloudflare Origin CA cert for that hostname exists, the vhost serves
**Nova's** cert and browsers show a name mismatch on the SkillSwap domain. That
is deliberate: naming a cert file that does not exist yet makes nginx refuse to
start, which would take `nova-flow.pro` down for a problem in the other app.
Once the cert is installed:

```sh
# deploy/install-origin-cert.sh, into /etc/nginx/ssl/skillswap/
echo 'SKILLSWAP_SSL_DIR=/etc/nginx/ssl/skillswap' >> .env
docker compose up -d --force-recreate nginx
```

## Day-to-day

```sh
deploy/deploy.sh                  # pull, build, migrate, health-gate, deploy
deploy/deploy.sh --no-pull        # deploy the working tree
deploy/deploy.sh --branch X       # deploy a feature branch ON PURPOSE
deploy/deploy.sh --rollback       # back to the previous image

deploy/data-deploy.sh --status    # data tier report, changes nothing
```

`deploy.sh` **refuses to run from a non-default branch**. `git pull`
fast-forwards *the current branch*, so a checkout left on a feature branch
deploys forever while answering "Already up to date" — truthfully, about the
wrong branch. In the sibling deployment that cost five days and three bug
reports whose fixes were merged, green and in `main` the whole time.

The health gate reads the container's healthcheck, which greps `"database":"up"`
out of `/health` rather than trusting the status code — `/health` answers **200
with the database down**, so a status-code gate waves a database-less container
straight through. A failed gate auto-rolls-back to the previous image.

Migrations run as a **one-shot before the app starts**, never in the app's
lifespan: two workers both running `alembic upgrade head` at boot is two
processes racing the same DDL.

## Local development

```sh
docker network create edge        # once; both stacks declare it external
docker compose -f docker-compose.yml -f docker-compose.data.yml \
               -f docker-compose.dev.yml up -d
curl -fsS localhost:8000/health
```

The dev overlay runs **one** worker, publishes on loopback, and gives Postgres
laptop-sized memory. It is not named `docker-compose.override.yml` on purpose:
compose auto-loads that name, and this is the same repo the VPS deploys from.

## When something is wrong

| symptom | look at |
|---|---|
| deploy dies at "cannot reach Postgres" | `systemctl status wg-quick@wg0` **both ends**; `wg show` for a recent handshake |
| container exits with "cannot assign requested address" | wg0 came up after Docker. `systemctl status skillswap-data` — that unit exists to order them |
| nginx 502 on the SkillSwap domain only | `docker network inspect edge` — is `skillswap-web` attached? |
| nginx will not start at all | it is Nova's nginx. `docker compose logs nginx` there; check `SKILLSWAP_SSL_DIR` names files that exist |
| Postgres OOM-killed | `deploy/postgres/pg-tuning.env`. `work_mem` is **per sort node**, not per connection — raising it is the usual cause |
| `PGDATA is 9x% full` | the ceiling is real and working. `du -sh` inside the mount; check for un-recycled WAL |
| everything green, browser shows old code | the deploy prints `branch @ sha` on every run. Compare it to what you expect before debugging anything else |

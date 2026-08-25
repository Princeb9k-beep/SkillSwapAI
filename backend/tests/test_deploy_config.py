"""Guards on the Docker deploy: the failures here are all SILENT ones.

Every assertion in this file corresponds to a way the deploy can be wrong while
looking right — a database published to the internet with the firewall still
reporting the port closed, a health gate that passes with no database, a deploy
that ships the wrong branch and says "Already up to date". None of them raise,
none of them log, and each is a one-word edit away.

Each was verified by restoring the defect and watching the test fail.

These run offline and touch nothing: they read the compose/Dockerfile/scripts,
and the branch guard is EXECUTED against a fake `git` — reading shell cannot
check shell semantics.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]

#  Loopback and the WireGuard address of the data VPS. `localhost` is
#  deliberately NOT here: Docker resolves it at container-create time and it can
#  carry an IPv6 answer, so it is not a reliable spelling of "not public".
_PRIVATE_BINDS = ("127.0.0.1", "::1", "10.77.0.1")

#  (compose file, service, container port) -> why it is deliberately public.
#  Nothing is, today. A companion test fails if an entry stops matching, so this
#  cannot rot into a blanket exemption.
_PUBLIC_ALLOWLIST: dict[tuple[str, str, str], str] = {}


def _compose_files() -> list[Path]:
    return sorted(_ROOT.glob("docker-compose*.yml"))


def _resolve(text: str) -> str:
    """Substitute `${VAR:-default}` with its DEFAULT.

    Compose interpolates at runtime; this file reads the source. So what it can
    check is the default that ships — which is the thing under review, and the
    thing a copy-paste edit gets wrong. It CANNOT see a `.env` that overrides
    WG_ADDR to 0.0.0.0 on the box; deploy/data-deploy.sh covers that end by
    reading the ACTUAL listening sockets (`ss -ltnp`) after start. Two halves,
    stated so neither is mistaken for the whole.
    """
    return re.sub(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}", r"\1", text)


def _published(entry) -> tuple[str | None, str]:
    """Return (host_ip, container_port) for one `ports:` entry, both syntaxes."""
    if isinstance(entry, dict):                     # long form
        host_ip = entry.get("host_ip")
        return (_resolve(str(host_ip)) if host_ip is not None else None,
                _resolve(str(entry.get("target", ""))))
    text = _resolve(str(entry))                     # short form
    # "10.77.0.1:5432:5432" | "127.0.0.1:8000:8000" | "5432:5432" | "5432"
    parts = text.split(":")
    if len(parts) >= 3:
        return (":".join(parts[:-2]), parts[-1])
    return (None, parts[-1])


class PublishedPortsAreNeverPublic(unittest.TestCase):
    """A published port binds privately, or it is on the internet.

    Docker does not publish ports THROUGH the host firewall, it publishes them
    AROUND it: for any non-loopback publish it inserts a DNAT rule into the nat
    table's DOCKER chain, and nat/PREROUTING is traversed BEFORE filter/INPUT
    where ufw's rules live. So on a box whose firewall denies 5432 the
    connection is accepted anyway, `ufw status` still reports 5432 closed, and
    nothing is logged.

    The difference between a database reachable only over WireGuard and one
    reachable from the entire internet is the ten characters `10.77.0.1:`, and
    deleting them produces no error and no symptom until someone else finds it.
    """

    def test_every_publish_binds_privately(self):
        seen = 0
        for f in _compose_files():
            spec = yaml.safe_load(f.read_text()) or {}
            for svc, body in (spec.get("services") or {}).items():
                for entry in (body or {}).get("ports", []) or []:
                    seen += 1
                    host_ip, port = _published(entry)
                    key = (f.name, svc, port)
                    if key in _PUBLIC_ALLOWLIST:
                        continue
                    with self.subTest(file=f.name, service=svc, entry=entry):
                        self.assertIsNotNone(
                            host_ip,
                            f"{f.name}:{svc} publishes {entry!r} with NO host IP — "
                            "Docker binds 0.0.0.0, i.e. every interface.",
                        )
                        self.assertIn(
                            host_ip,
                            _PRIVATE_BINDS,
                            f"{f.name}:{svc} publishes on {host_ip!r}. Allowed: "
                            f"{_PRIVATE_BINDS}.",
                        )
        self.assertGreater(seen, 0, "no ports: entries found at all — did the parser break?")

    def test_allowlist_has_no_stale_entries(self):
        """A budget that no longer matches anything has stopped guarding."""
        live = set()
        for f in _compose_files():
            spec = yaml.safe_load(f.read_text()) or {}
            for svc, body in (spec.get("services") or {}).items():
                for entry in (body or {}).get("ports", []) or []:
                    live.add((f.name, svc, _published(entry)[1]))
        for key in _PUBLIC_ALLOWLIST:
            self.assertIn(key, live, f"allowlist entry {key} matches nothing — delete it")


class DataTierIsSizedAsSpecified(unittest.TestCase):
    """The allocation is 1 CPU / 256M / 10G for Postgres and 512M for Redis.

    Pinned because these are the numbers the Postgres tuning was derived from:
    change mem_limit without changing shared_buffers/work_mem and the container
    is OOM-killed mid-query, which reads as a database fault rather than a
    config one.
    """

    def setUp(self):
        self.data = yaml.safe_load((_ROOT / "docker-compose.data.yml").read_text())
        self.app = yaml.safe_load((_ROOT / "docker-compose.yml").read_text())

    def _cmd(self, service: str) -> str:
        return " ".join(str(x) for x in self.data["services"][service]["command"])

    def test_postgres_limits(self):
        pg = self.data["services"]["postgres"]
        self.assertIn("256m", str(pg["mem_limit"]))
        self.assertIn("1.0", str(pg["cpus"]))

    def test_postgres_tuning_fits_inside_the_limit(self):
        cmd = self._cmd("postgres")
        self.assertIn("shared_buffers=${PG_SHARED_BUFFERS:-64MB}", cmd)
        self.assertIn("work_mem=${PG_WORK_MEM:-2MB}", cmd)
        # Parallel query off: a parallel worker is another backend inside the
        # same 256M cgroup AND it uses /dev/shm, which is charged to that limit.
        self.assertIn("max_parallel_workers_per_gather=0", cmd)
        # 512MB, not the 1GB default: checkpoints can leave ~2-3x max_wal_size
        # on a disk that is 10G in TOTAL.
        self.assertIn("max_wal_size=${PG_MAX_WAL_SIZE:-512MB}", cmd)

    def test_redis_maxmemory_and_the_fork_headroom(self):
        cmd = self._cmd("redis")
        self.assertIn("--maxmemory ${REDIS_MAXMEMORY:-512mb}", cmd)
        # mem_limit must exceed maxmemory: the AOF-rewrite fork's copy-on-write
        # pages need somewhere to go, and sizing the container AT maxmemory
        # means the OOM killer wins that race.
        self.assertIn("640m", str(self.data["services"]["redis"]["mem_limit"]))

    def test_redis_refuses_to_run_authless(self):
        self.assertIn("refusing to start authless", self._cmd("redis"))

    def test_app_gets_one_cpu(self):
        self.assertEqual(1.0, float(self.app["services"]["web"]["cpus"]))


class TheStorageCeilingIsDeclaredNotHoped(unittest.TestCase):
    """10 GB has to be a filesystem, not an intention.

    Docker cannot size-limit a volume — there is no `--storage-opt size=` for
    volumes, and the one that exists applies to a container's writable layer and
    needs an xfs+pquota backend. So an ordinary named volume, or a bind onto the
    root filesystem, is not a limit at all. This box also holds Nova Flow's
    production Redis, so a runaway table here fills that box too: SkillSwap's
    disk bug becomes Nova's outage.

    A filesystem in a FILE is a real ceiling. Deleting the three driver_opts
    below is a one-line edit that produces NO error and NO symptom — Docker just
    hands out an ordinary volume and Postgres can fill the host. `df` is the only
    thing that ever knows, which is why data-deploy.sh also checks it at runtime.
    """

    def setUp(self):
        self.data = yaml.safe_load((_ROOT / "docker-compose.data.yml").read_text())

    def test_pgdata_binds_a_mountpoint_and_never_asks_docker_to_loop_mount(self):
        """`type: ext4, o: loop` DOES NOT WORK, and shipped because it parses.

        Measured on a real daemon:

            failed to mount local volume: mount /srv/skillswap/pgdata.img:...,
            data: loop: invalid argument

        Docker's local driver calls the mount SYSCALL; `loop` is a feature of
        the mount COMMAND, which runs losetup for you first. The kernel gets
        "loop" as filesystem-specific data and rejects it. `docker compose
        config` validates it happily — parsing is not mounting, and that gap is
        the whole reason this assertion exists.

        So: userspace does the loop setup (the bootstrap service) and Docker
        binds the resulting mountpoint.
        """
        opts = (self.data["volumes"]["pgdata"] or {}).get("driver_opts") or {}
        self.assertEqual("none", opts.get("type"))
        self.assertEqual("bind", opts.get("o"))
        self.assertNotEqual("loop", opts.get("o"),
                            "o: loop is rejected by the kernel — see the docstring")
        device = _resolve(str(opts.get("device", "")))
        self.assertFalse(device.endswith(".img"),
                         f"a bind takes the MOUNTPOINT, not the image: {device!r}")

    def test_bootstrap_mounts_it_and_proves_the_host_can_see_it(self):
        """A mount inside a container is private to its namespace unless
        propagation is rshared. Without the check, an unpropagated mount leaves
        the bind pointing at a bare directory on the root filesystem: Postgres
        starts, everything reports healthy, and the ceiling silently is not
        there — on a box that also holds Nova Flow's production Redis."""
        bootstrap = self.data["services"]["bootstrap"]
        cmd = " ".join(str(x) for x in bootstrap["command"])
        self.assertIn("mount -o loop", cmd)
        self.assertIn("/proc/1/mountinfo", cmd)
        self.assertEqual("host", bootstrap.get("pid"),
                         "pid: host, or /proc/1/mountinfo is our own namespace")
        self.assertTrue(any(str(v).endswith(":rshared") for v in bootstrap["volumes"]),
                        "the host-data mount needs rshared or nothing propagates")

    def test_postgres_waits_for_the_image_to_exist(self):
        """Mounting a device that does not exist yet is the failure this
        ordering prevents — and `depends_on` alone is not enough: it must be
        service_completed_successfully, or postgres starts alongside a
        bootstrap that is still running mkfs."""
        dep = self.data["services"]["postgres"]["depends_on"]["bootstrap"]
        self.assertEqual("service_completed_successfully", dep["condition"])

    def test_bootstrap_never_reformats_an_existing_filesystem(self):
        """The difference between re-running this and erasing the database.
        Re-running is exactly what people do."""
        cmd = " ".join(str(x) for x in self.data["services"]["bootstrap"]["command"])
        self.assertIn("blkid", cmd)
        self.assertIn("not touching it", cmd)

    def test_bootstrap_reserves_only_one_percent(self):
        """ext4 reserves 5% for root by default and Postgres is not root, so a
        10G volume would hand it 9.5G and refuse the rest with an ENOSPC while
        df still showed free space."""
        cmd = " ".join(str(x) for x in self.data["services"]["bootstrap"]["command"])
        self.assertIn("mkfs.ext4 -q -m 1 -F", cmd)

    def test_bootstrap_is_the_only_privileged_service(self):
        """It needs it (mkfs and loop devices are kernel-level). Nothing else
        should acquire it by drift."""
        privileged = {n for n, b in self.data["services"].items() if (b or {}).get("privileged")}
        self.assertEqual({"bootstrap"}, privileged)

    def test_dev_uses_a_different_volume_rather_than_overriding_this_one(self):
        """MEASURED, and the reason the dev overlay looks redundant: compose
        MERGES a named volume's definition rather than replacing it. An overlay
        redeclaring `pgdata: {driver: local}` still emits the ext4/loop
        driver_opts, so a laptop would try to loop-mount /srv/skillswap/pgdata.img.
        Pointing at a separate volume is the only way to say 'not that one'."""
        dev = yaml.safe_load((_ROOT / "docker-compose.dev.yml").read_text())
        mounts = dev["services"]["postgres"]["volumes"]
        self.assertTrue(any(str(m).startswith("pgdata-dev:") for m in mounts), mounts)
        self.assertNotIn("pgdata", (dev.get("volumes") or {}),
                         "redeclaring `pgdata` here cannot strip driver_opts — it merges")


class WorkersNotThreads(unittest.TestCase):
    """Two lanes means two WORKER PROCESSES.

    `--threads` is a NO-OP under UvicornWorker — the flag applies to gthread and
    sync workers only, and an asyncio worker ignores it outright. Passing it
    changes nothing while making the fleet read as if it had twice the lanes it
    has, which is exactly the misreading the sibling Nova Flow deployment had to
    audit its way out of.
    """

    def setUp(self):
        self.dockerfile = (_ROOT / "Dockerfile").read_text()

    def test_two_workers(self):
        self.assertIn("--workers ${GUNICORN_WORKERS:-2}", self.dockerfile)

    def test_no_threads_flag(self):
        stripped = "\n".join(
            line for line in self.dockerfile.splitlines() if not line.lstrip().startswith("#")
        )
        self.assertNotIn(
            "--threads",
            stripped,
            "--threads is silently ignored by UvicornWorker. Comments explaining "
            "that are fine; a real flag is not.",
        )


class HealthGateReadsTheDatabase(unittest.TestCase):
    """The gate asserts the VALUE, not the presence.

    GET /health returns **200 with "database":"down"** when Postgres is
    unreachable — backend/app/routers/health.py builds a services map and always
    answers ok(). So `curl -f` alone calls a database-less container healthy, the
    deploy gate passes, and the first user request is what discovers it.
    """

    def test_health_endpoint_really_does_answer_200_when_the_db_is_down(self):
        """The premise, asserted rather than assumed — if /health ever starts
        returning 503 on a dead database, this whole guard is obsolete and
        should say so instead of quietly protecting nothing."""
        src = (_ROOT / "backend" / "app" / "routers" / "health.py").read_text()
        self.assertIn('services["database"] = "down"', src)
        self.assertIn("return ok(", src)
        self.assertNotIn("status_code=503", src)

    def test_dockerfile_healthcheck_greps_the_value(self):
        dockerfile = (_ROOT / "Dockerfile").read_text()
        self.assertIn('grep -q \'"database":"up"\'', dockerfile)

    def test_deploy_gates_on_container_health(self):
        deploy = (_ROOT / "deploy" / "deploy.sh").read_text()
        self.assertIn("{{.State.Health.Status}}", deploy)
        self.assertIn("Auto-rolling back", deploy)

    def test_deploy_asserts_the_schema_reached_head(self):
        """`alembic upgrade head` exits 0 when it had nothing to do — including
        against a database that is not the one you think it is."""
        deploy = (_ROOT / "deploy" / "deploy.sh").read_text()
        self.assertIn("alembic current", deploy)
        self.assertIn("(head)", deploy)


class BranchGuardIsExecuted(unittest.TestCase):
    """`git pull` fast-forwards THE CURRENT BRANCH.

    A checkout left on a feature branch deploys happily forever, answering
    "Already up to date" — truthfully, about the wrong branch. Every proxy for
    "is it shipped" says yes; only the bytes the browser downloads disagree.

    This EXECUTES the guard against a fake `git` rather than grepping the
    script, because reading shell cannot check shell semantics: a guard whose
    refusal path is never run is a guard nobody has tested.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        fake = Path(cls.tmp) / "bin"
        fake.mkdir()
        (fake / "git").write_text(
            "#!/bin/sh\n"
            'case "$*" in\n'
            '  "rev-parse --abbrev-ref HEAD") echo "$FAKE_BRANCH" ;;\n'
            '  "symbolic-ref --quiet --short refs/remotes/origin/HEAD") echo "origin/main" ;;\n'
            "  *) exit 1 ;;\n"
            "esac\n"
        )
        (fake / "git").chmod(0o755)
        cls.fake_bin = str(fake)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _run(self, branch: str, requested: str = ""):
        env = dict(os.environ, PATH=f"{self.fake_bin}:{os.environ['PATH']}", FAKE_BRANCH=branch)
        script = _ROOT / "deploy" / "deploy.sh"
        return subprocess.run(
            ["bash", "-c", f'BRANCH_GUARD_LIB=1 . "{script}"; assert_deployable_branch "{requested}"'],
            env=env, capture_output=True, text=True,
        )

    def test_default_branch_proceeds(self):
        r = self._run("main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("main", r.stdout.strip())

    def test_feature_branch_is_refused(self):
        r = self._run("claude/some-feature")
        self.assertNotEqual(0, r.returncode)
        self.assertIn("REFUSING TO DEPLOY", r.stderr)

    def test_feature_branch_with_explicit_flag_proceeds_but_warns(self):
        r = self._run("claude/some-feature", "claude/some-feature")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("claude/some-feature", r.stdout.strip())
        self.assertIn("explicitly requested", r.stderr)

    def test_flag_disagreeing_with_the_checkout_is_refused(self):
        """Not trusted, not silently corrected: --branch X on a checkout that is
        not X means one of the two is a mistake, and guessing which is worse."""
        r = self._run("main", "other")
        self.assertNotEqual(0, r.returncode)
        self.assertIn("checkout is on main", r.stderr)


class UrlParsingSurvivesRealPasswords(unittest.TestCase):
    """The preflight extracts host:port from DATABASE_URL to prove the database
    is reachable BEFORE anything is rebuilt. A password containing @ : or # is
    ordinary (openssl rand -base64 emits + / =, and operators pick worse), and a
    parser that trips on one reports the database unreachable and aborts a
    perfectly good deploy — while looking exactly like a real outage.

    The two functions are LIFTED OUT OF deploy.sh and executed, not copied here.
    A copy would pass forever after the original drifted, which is the failure
    mode this whole file exists to avoid.
    """

    @classmethod
    def setUpClass(cls):
        src = (_ROOT / "deploy" / "deploy.sh").read_text()
        cls.defs = [ln for ln in src.splitlines()
                    if ln.startswith("url_host()") or ln.startswith("url_port()")]
        if len(cls.defs) != 2:
            raise AssertionError(
                f"expected url_host()/url_port() as single-line definitions in "
                f"deploy.sh, found {len(cls.defs)} — the extractor is broken, "
                "not the script"
            )

    def _parse(self, url: str) -> tuple[str, str]:
        script = "\n".join(self.defs) + (
            f"\nprintf '%s %s' \"$(url_host '{url}')\" \"$(url_port '{url}')\"\n"
        )
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(0, r.returncode, r.stderr)
        host, _, port = r.stdout.strip().partition(" ")
        return host, port

    def test_ordinary_url(self):
        self.assertEqual(("10.77.0.1", "5432"), self._parse("postgresql://u:p@10.77.0.1:5432/db"))

    def test_password_containing_at_and_colon_and_hash(self):
        self.assertEqual(("10.77.0.1", "5432"),
                         self._parse("postgres://user:p@ss:w#rd@10.77.0.1:5432/db"))

    def test_async_scheme_and_no_explicit_port(self):
        self.assertEqual(("db.example.com", ""),
                         self._parse("postgresql+asyncpg://u:p@db.example.com/mydb"))

    def test_redis_url_with_db_index(self):
        self.assertEqual(("10.77.0.1", "6380"),
                         self._parse("redis://default:s3cr3t@10.77.0.1:6380/0"))

    def test_no_userinfo_at_all(self):
        self.assertEqual(("10.77.0.1", "6380"), self._parse("redis://10.77.0.1:6380"))


if __name__ == "__main__":
    unittest.main()

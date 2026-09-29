"""Project-only PostgreSQL 18 + pgvector bootstrap; never touches existing clusters."""

import argparse
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["start", "stop", "status"], nargs="?", default="start")
args = parser.parse_args()
pgconfig = shutil.which("pg_config")
if not pgconfig:
    raise SystemExit(
        "Install PostgreSQL 18 first (on macOS: brew install postgresql@18), or use Docker Compose."
    )


def output(*cmd):
    return subprocess.check_output(cmd, text=True).strip()


if not output(pgconfig, "--version").startswith("PostgreSQL 18"):
    raise SystemExit(
        "This isolated setup requires PostgreSQL 18. Put its bin directory first in PATH."
    )
bindir = Path(output(pgconfig, "--bindir"))
cluster = WORK / "pgdata"
port = os.getenv("DB_PORT", "55439")


def run(*cmd, **kw):
    subprocess.run([str(c) for c in cmd], check=True, **kw)


if args.command == "stop":
    run(bindir / "pg_ctl", "-D", cluster, "stop", "-m", "fast")
    raise SystemExit
source = WORK / "pgvector-0.8.2"
if not source.exists():
    archive = WORK / "pgvector.tar.gz"
    urllib.request.urlretrieve(
        "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.2.tar.gz", archive
    )
    with tarfile.open(archive) as f:
        f.extractall(WORK, filter="data")
library = source / ("vector.dylib" if os.uname().sysname == "Darwin" else "vector.so")
if not library.exists():
    cmd = ["make", "-C", str(source), "PG_CONFIG=" + pgconfig]
    if os.uname().sysname == "Darwin":
        cmd += ["PG_SYSROOT=" + output("xcrun", "--show-sdk-path")]
    with (WORK / "pgvector-build.log").open("w") as f:
        run(*cmd, stdout=f, stderr=subprocess.STDOUT)
ext = WORK / "pgext" / "extension"
ext.mkdir(parents=True, exist_ok=True)
for sql in (source / "sql").glob("vector--*.sql"):
    shutil.copy2(sql, ext / sql.name)
(ext / "vector.control").write_text(
    (source / "vector.control").read_text().replace("$libdir/vector", str(source / "vector"))
)
if not (cluster / "PG_VERSION").exists():
    run(bindir / "initdb", "-D", cluster, "-A", "trust", "-U", "habitpet")
config = cluster / "postgresql.conf"
lines = [
    line
    for line in config.read_text().splitlines()
    if not line.startswith("extension_control_path =")
]
lines.append("extension_control_path = '$system:" + str(WORK / "pgext") + "'")
config.write_text("\n".join(lines) + "\n")
connection = ["-h", "127.0.0.1", "-p", port, "-U", "habitpet"]
probe = subprocess.run(
    [str(bindir / "psql"), *connection, "-d", "postgres", "-Atc", "SHOW data_directory"],
    text=True,
    capture_output=True,
)
running = probe.returncode == 0 and Path(probe.stdout.strip()).resolve() == cluster.resolve()
if probe.returncode == 0 and not running:
    raise SystemExit("Port is used by a different cluster; refusing to change it.")
if args.command == "status":
    print("Project PostgreSQL is running." if running else "Project PostgreSQL is stopped.")
    raise SystemExit(0 if running else 1)
if not running:
    run(
        bindir / "pg_ctl",
        "-D",
        cluster,
        "-l",
        WORK / "postgres.log",
        "-o",
        f"-p {port} -h 127.0.0.1 -k /tmp",
        "start",
    )
connection = ["-h", "127.0.0.1", "-p", port, "-U", "habitpet"]
run(bindir / "psql", *connection, "-d", "postgres", "-c", "SELECT pg_reload_conf();")
names = output(
    str(bindir / "psql"),
    *connection,
    "-d",
    "postgres",
    "-Atc",
    "SELECT datname FROM pg_database WHERE datname='habitpet'",
)
if not names:
    run(bindir / "createdb", *connection, "habitpet")
print(
    f"Local PostgreSQL ready at 127.0.0.1:{port}; project data: {cluster}. Trust auth is LOCAL DEVELOPMENT ONLY."
)

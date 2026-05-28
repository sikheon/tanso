"""Initialize database: create DB+user (if missing), run migrations, apply seeds.

Usage:
    python -m src.scripts.init_db                       # full init
    python -m src.scripts.init_db --skip-create-db      # if db already exists
    python -m src.scripts.init_db --reset               # DROP and recreate

Prerequisites:
    - PostgreSQL 16+ with PostGIS available
    - A superuser account (default: postgres) — its password is read
      from the PGPASSWORD env var or prompted interactively.
"""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from src.core.config import get_settings

ROOT = Path(__file__).resolve().parents[3]
SEEDS_DIR = ROOT / "backend" / "seeds"
SEEDS_ORDER = [
    "01_emission_factors.sql",
    "02_speed_bin_factors.sql",
    "03_vehicles_sample.sql",
]


def parse_db_url(url: str) -> dict[str, str]:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    return {
        "user": parsed.username or "elo",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": (parsed.path or "/elo").lstrip("/"),
    }


def run_psql(
    *,
    superuser: str,
    super_password: str,
    host: str,
    port: str,
    db: str,
    sql: str | None = None,
    file: Path | None = None,
) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = super_password
    env["PGCLIENTENCODING"] = "UTF8"

    cmd = ["psql", "-U", superuser, "-h", host, "-p", port, "-d", db, "-v", "ON_ERROR_STOP=1"]
    if sql is not None:
        cmd.extend(["-c", sql])
    if file is not None:
        cmd.extend(["-f", str(file)])

    print(f"  > psql -U {superuser} -d {db}  ({sql[:60] + '...' if sql else file.name})")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"psql failed (exit {result.returncode})")
    if result.stdout.strip():
        print(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--superuser", default=os.environ.get("PGSUPERUSER", "postgres"))
    parser.add_argument("--skip-create-db", action="store_true")
    parser.add_argument("--skip-seeds", action="store_true")
    parser.add_argument("--reset", action="store_true", help="DROP and recreate database")
    args = parser.parse_args()

    settings = get_settings()
    db = parse_db_url(settings.database_url)
    print(f"Target: {db['user']}@{db['host']}:{db['port']}/{db['dbname']}")

    super_pw = os.environ.get("PGPASSWORD") or getpass.getpass(
        f"Password for superuser '{args.superuser}': "
    )

    # 1. Create role + database (idempotent)
    if not args.skip_create_db:
        print("\n[1/3] Ensuring role + database exist…")
        run_psql(
            superuser=args.superuser, super_password=super_pw,
            host=db["host"], port=db["port"], db="postgres",
            sql=(
                f"DO $$ BEGIN "
                f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{db['user']}') THEN "
                f"    CREATE ROLE {db['user']} LOGIN PASSWORD '{db['password']}' CREATEDB; "
                f"  END IF; "
                f"END $$;"
            ),
        )
        if args.reset:
            run_psql(
                superuser=args.superuser, super_password=super_pw,
                host=db["host"], port=db["port"], db="postgres",
                sql=f"DROP DATABASE IF EXISTS {db['dbname']};",
            )
        # CREATE DATABASE cannot run inside a transaction block — wrap separately
        check = subprocess.run(
            ["psql", "-U", args.superuser, "-h", db["host"], "-p", db["port"],
             "-d", "postgres", "-tAc",
             f"SELECT 1 FROM pg_database WHERE datname='{db['dbname']}'"],
            env={**os.environ, "PGPASSWORD": super_pw, "PGCLIENTENCODING": "UTF8"},
            capture_output=True, text=True,
        )
        if check.stdout.strip() != "1":
            run_psql(
                superuser=args.superuser, super_password=super_pw,
                host=db["host"], port=db["port"], db="postgres",
                sql=f"CREATE DATABASE {db['dbname']} OWNER {db['user']};",
            )
        # Ensure PostGIS in target DB (Alembic also creates it, but doing it here lets
        # us verify availability up-front and grant to the app role)
        run_psql(
            superuser=args.superuser, super_password=super_pw,
            host=db["host"], port=db["port"], db=db["dbname"],
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
        )

    # 2. Run Alembic migrations
    print("\n[2/3] Running Alembic migrations…")
    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    backend_dir = ROOT / "backend"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env, cwd=str(backend_dir), capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    # 3. Apply seed SQL (as the app user, which is fine since schema is theirs)
    if not args.skip_seeds:
        print("\n[3/3] Applying seed data…")
        for fname in SEEDS_ORDER:
            seed_path = SEEDS_DIR / fname
            if not seed_path.exists():
                print(f"  ! missing seed: {seed_path}")
                continue
            run_psql(
                superuser=db["user"], super_password=db["password"],
                host=db["host"], port=db["port"], db=db["dbname"],
                file=seed_path,
            )

    print("\n✓ Database initialized successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

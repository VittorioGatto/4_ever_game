"""Applica rokkini/schema.sql al database locale o a Turso.

Uso:
    uv run python scripts/init_db.py              # locale, data/local.db
    uv run python scripts/init_db.py --turso       # legge .streamlit/secrets.toml
"""

import argparse
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rokkini import db

SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turso", action="store_true", help="applica lo schema al DB Turso")
    args = parser.parse_args()

    if args.turso:
        if not SECRETS_PATH.exists():
            raise SystemExit(f"File secrets non trovato: {SECRETS_PATH}")
        secrets = tomllib.loads(SECRETS_PATH.read_text())
        turso_cfg = secrets["turso"]
        conn = db.connect(turso_cfg["database_url"], turso_cfg["auth_token"])
        print(f"Applico lo schema a Turso ({turso_cfg['database_url']})...")
    else:
        conn = db.connect()
        print(f"Applico lo schema al file locale ({db.LOCAL_DB_PATH})...")

    db.apply_schema(conn)
    print("Schema applicato.")


if __name__ == "__main__":
    main()

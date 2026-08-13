"""Crea un utente admin/super_admin (bootstrap: serve per creare il primo
super_admin, dato che la pagina di gestione utenti dell'app richiede gia'
un login da super_admin).

Uso:
    uv run python scripts/create_admin.py --username mario --password ... \\
        --nome "Mario Rossi" --ruolo super_admin
    uv run python scripts/create_admin.py --turso --username ... --password ... --ruolo admin
"""

import argparse
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rokkini import auth, db

SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turso", action="store_true")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--nome", required=True, help="Nome visualizzato")
    parser.add_argument("--email", default=None)
    parser.add_argument("--ruolo", choices=["admin", "super_admin"], default="super_admin")
    args = parser.parse_args()

    if args.turso:
        secrets = tomllib.loads(SECRETS_PATH.read_text())
        turso_cfg = secrets["turso"]
        conn = db.connect(turso_cfg["database_url"], turso_cfg["auth_token"])
    else:
        conn = db.connect()

    if db.fetch_utente_by_username(conn, args.username) is not None:
        raise SystemExit(f"L'utente '{args.username}' esiste gia'.")

    password_hash = auth.hash_password(args.password)
    utente_id = db.insert_utente(
        conn,
        username=args.username,
        nome_visualizzato=args.nome,
        password_hash=password_hash,
        ruolo=args.ruolo,
        email=args.email,
    )
    print(f"Utente '{args.username}' creato (id={utente_id}, ruolo={args.ruolo}).")


if __name__ == "__main__":
    main()

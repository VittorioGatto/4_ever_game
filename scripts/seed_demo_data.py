"""Popola il database locale con giocatori e partite finte, utile per provare
la UI durante lo sviluppo (non usare in produzione).

Uso:
    uv run python scripts/seed_demo_data.py
"""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rokkini import auth, db, rating_engine

NOMI_GIOCATORI = [
    "Marco",
    "Luca",
    "Andrea",
    "Paolo",
    "Carlo",
    "Matteo",
    "Giulia",
    "Sara",
    "Elena",
    "Francesca",
]


def main() -> None:
    conn = db.connect()
    db.apply_schema(conn)

    if db.fetch_utente_by_username(conn, "demo_admin") is None:
        admin_id = db.insert_utente(
            conn,
            username="demo_admin",
            nome_visualizzato="Admin Demo",
            password_hash=auth.hash_password("demo1234"),
            ruolo="super_admin",
        )
    else:
        admin_id = db.fetch_utente_by_username(conn, "demo_admin")["id"]

    giocatori_esistenti = {g["nome"]: g["id"] for g in db.fetch_giocatori(conn)}
    giocatore_ids = []
    for nome in NOMI_GIOCATORI:
        if nome in giocatori_esistenti:
            giocatore_ids.append(giocatori_esistenti[nome])
        else:
            giocatore_ids.append(db.insert_giocatore(conn, nome))

    random.seed(42)
    data_partita = date(2026, 1, 1)
    for _ in range(60):
        partecipanti = random.sample(giocatore_ids, 6)
        squadra_a, squadra_b = partecipanti[0:3], partecipanti[3:6]
        vincente = random.choice(["A", "B"])
        risultato = random.choice(["2-0", "2-1"])
        rating_engine.register_match(
            conn,
            data_partita.isoformat(),
            "3v3",
            risultato,
            vincente,
            squadra_a,
            squadra_b,
            admin_id,
        )
        data_partita += timedelta(days=random.randint(1, 4))

    print(f"Seed completato: {len(giocatore_ids)} giocatori, 60 partite in {db.LOCAL_DB_PATH}")
    print("Utente demo: demo_admin / demo1234 (super_admin)")


if __name__ == "__main__":
    main()

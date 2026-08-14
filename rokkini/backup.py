"""Esportazione/importazione completa dei dati (backup e restore).

L'import sostituisce interamente il contenuto del database con quello del
dump: non è un merge. Il dump include password_hash (bcrypt, non testo in
chiaro) perché senza non sarebbe possibile ripristinare gli accessi.
"""

from typing import Any

from rokkini import db

VERSIONE_FORMATO = 1

# Ordine valido per gli INSERT (rispetta le foreign key: ogni tabella
# referenzia solo tabelle che la precedono). Il DELETE in fase di import usa
# l'ordine inverso, cosi' cancella prima le tabelle "figlie".
TABELLE: tuple[str, ...] = (
    "giocatori",
    "utenti",
    "partite",
    "partecipazioni_partita",
    "variazioni_rk",
    "ranking_leader_log",
)


def export_data(conn) -> dict[str, Any]:
    tabelle = {}
    for nome_tabella in TABELLE:
        cur = conn.execute(f"SELECT * FROM {nome_tabella}")
        tabelle[nome_tabella] = db.rows_as_dicts(cur)
    return {"versione": VERSIONE_FORMATO, "tabelle": tabelle}


def import_data(conn, dump: dict[str, Any]) -> None:
    if dump.get("versione") != VERSIONE_FORMATO:
        raise ValueError(
            f"Formato di backup non riconosciuto (versione {dump.get('versione')!r}, "
            f"attesa {VERSIONE_FORMATO})"
        )
    tabelle = dump.get("tabelle", {})

    try:
        for nome_tabella in reversed(TABELLE):
            conn.execute(f"DELETE FROM {nome_tabella}")

        for nome_tabella in TABELLE:
            for riga in tabelle.get(nome_tabella, []):
                colonne = ", ".join(riga.keys())
                segnaposto = ", ".join("?" for _ in riga)
                conn.execute(
                    f"INSERT INTO {nome_tabella} ({colonne}) VALUES ({segnaposto})",
                    tuple(riga.values()),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

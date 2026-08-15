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


# Tabelle collegate a partite/sessioni: vengono svuotate da reset_completo,
# nell'ordine che rispetta le foreign key (prima le "figlie").
TABELLE_STORICO: tuple[str, ...] = (
    "variazioni_rk",
    "partecipazioni_partita",
    "partite",
    "sessione_partecipanti",
    "sessioni_gioco",
    "ranking_leader_log",
)


def reset_completo(conn) -> None:
    """Cancella tutto lo storico (partite, partecipazioni, variazioni Rk,
    sessioni di gioco) e riporta ogni giocatore ai valori di partenza. Non
    tocca giocatori/utenti come account: restano gli stessi nomi e le stesse
    credenziali, solo le statistiche ripartono da zero. Operazione
    irreversibile (a meno di ripristinare un backup preso prima)."""
    try:
        for nome_tabella in TABELLE_STORICO:
            conn.execute(f"DELETE FROM {nome_tabella}")
        conn.execute(
            """UPDATE giocatori SET
                rk_attuale = 1000,
                partite_giocate = 0,
                vittorie = 0,
                sconfitte = 0,
                fascia_attuale = 'H',
                qualificato = 0,
                rk_record = 1000,
                streak_vittorie_corrente = 0,
                streak_vittorie_record = 0"""
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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

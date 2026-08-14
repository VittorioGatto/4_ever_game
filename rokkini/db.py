"""Connessione al database (SQLite locale o Turso via libSQL) e CRUD di base."""

from pathlib import Path
from typing import Any

import libsql
import streamlit as st

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
LOCAL_DB_PATH = Path(__file__).parent.parent / "data" / "local.db"


def connect(database_url: str | None = None, auth_token: str | None = None):
    """Apre una connessione libsql. Senza database_url si connette al file locale
    data/local.db (stesso motore SQL usato in sviluppo e in produzione)."""
    if database_url:
        conn = libsql.connect(database=database_url, auth_token=auth_token)
    else:
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = libsql.connect(database=str(LOCAL_DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


@st.cache_resource
def get_connection():
    """Connessione cacheata per l'app Streamlit: usa Turso se configurato nei
    secrets, altrimenti il file locale (nessun secrets.toml in sviluppo)."""
    try:
        turso_cfg = st.secrets.get("turso")
    except st.errors.StreamlitSecretNotFoundError:
        turso_cfg = None
    if turso_cfg:
        return connect(turso_cfg["database_url"], turso_cfg["auth_token"])
    return connect()


def rows_as_dicts(cursor) -> list[dict[str, Any]]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def row_as_dict(cursor, row) -> dict[str, Any] | None:
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row, strict=True))


# --- giocatori ------------------------------------------------------------


def insert_giocatore(conn, nome: str) -> int:
    cur = conn.execute(
        "INSERT INTO giocatori (nome) VALUES (?)",
        (nome,),
    )
    conn.commit()
    return cur.lastrowid


def fetch_giocatori(conn) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM giocatori ORDER BY nome")
    return rows_as_dicts(cur)


def fetch_giocatore(conn, giocatore_id: int) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM giocatori WHERE id = ?", (giocatore_id,))
    return row_as_dict(cur, cur.fetchone())


def update_giocatore_stato(conn, giocatore_id: int, **campi: Any) -> None:
    colonne = ", ".join(f"{campo} = ?" for campo in campi)
    conn.execute(
        f"UPDATE giocatori SET {colonne} WHERE id = ?",
        (*campi.values(), giocatore_id),
    )


def update_giocatore_nome(conn, giocatore_id: int, nome: str) -> None:
    conn.execute("UPDATE giocatori SET nome = ? WHERE id = ?", (nome, giocatore_id))
    conn.commit()


def set_giocatore_sospeso(conn, giocatore_id: int, sospeso: bool) -> None:
    conn.execute(
        "UPDATE giocatori SET sospeso = ? WHERE id = ?", (int(sospeso), giocatore_id)
    )
    conn.commit()


# --- utenti -----------------------------------------------------------------


def fetch_utenti_attivi(conn) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM utenti WHERE attivo = 1")
    return rows_as_dicts(cur)


def fetch_utente_by_username(conn, username: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM utenti WHERE username = ?", (username,))
    return row_as_dict(cur, cur.fetchone())


def insert_utente(
    conn,
    username: str,
    nome_visualizzato: str,
    password_hash: str,
    ruolo: str = "super_admin",
    email: str | None = None,
    giocatore_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO utenti (username, nome_visualizzato, email, password_hash, ruolo, giocatore_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (username, nome_visualizzato, email, password_hash, ruolo, giocatore_id),
    )
    conn.commit()
    return cur.lastrowid


def set_utente_attivo(conn, utente_id: int, attivo: bool) -> None:
    conn.execute("UPDATE utenti SET attivo = ? WHERE id = ?", (int(attivo), utente_id))
    conn.commit()


# --- partite / partecipazioni / variazioni ----------------------------------


def insert_partita(
    conn,
    data_partita: str,
    modalita: str,
    risultato_set: str,
    squadra_vincente: str,
    registered_by: int,
    replaces_match_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO partite
               (data_partita, modalita, risultato_set, squadra_vincente, registered_by, replaces_match_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data_partita, modalita, risultato_set, squadra_vincente, registered_by, replaces_match_id),
    )
    return cur.lastrowid


def insert_partecipazione(conn, partita_id: int, giocatore_id: int, squadra: str) -> None:
    conn.execute(
        "INSERT INTO partecipazioni_partita (partita_id, giocatore_id, squadra) VALUES (?, ?, ?)",
        (partita_id, giocatore_id, squadra),
    )


def fetch_partecipazioni(conn, partita_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM partecipazioni_partita WHERE partita_id = ? ORDER BY squadra, id",
        (partita_id,),
    )
    return rows_as_dicts(cur)


def fetch_partite_non_annullate(conn) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM partite WHERE voided = 0 ORDER BY data_partita ASC, created_at ASC, id ASC"
    )
    return rows_as_dicts(cur)


def fetch_partite_tutte(conn) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM partite ORDER BY data_partita DESC, created_at DESC, id DESC"
    )
    return rows_as_dicts(cur)


def fetch_partita(conn, partita_id: int) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM partite WHERE id = ?", (partita_id,))
    return row_as_dict(cur, cur.fetchone())


def void_partita_row(conn, partita_id: int, voided_by: int, reason: str) -> None:
    conn.execute(
        """UPDATE partite SET voided = 1, voided_at = datetime('now'), voided_by = ?, voided_reason = ?
           WHERE id = ?""",
        (voided_by, reason, partita_id),
    )


def delete_variazioni(conn, partita_id: int) -> None:
    conn.execute("DELETE FROM variazioni_rk WHERE partita_id = ?", (partita_id,))


def insert_variazione(
    conn,
    partita_id: int,
    giocatore_id: int,
    squadra: str,
    esito: str,
    rk_prima: int,
    k_usato: int,
    probabilita_teorica: float,
    correttivo_usato: float,
    delta: int,
    rk_dopo: int,
) -> None:
    conn.execute(
        """INSERT INTO variazioni_rk
               (partita_id, giocatore_id, squadra, esito, rk_prima, k_usato,
                probabilita_teorica, correttivo_usato, delta, rk_dopo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            partita_id,
            giocatore_id,
            squadra,
            esito,
            rk_prima,
            k_usato,
            probabilita_teorica,
            correttivo_usato,
            delta,
            rk_dopo,
        ),
    )


def fetch_variazioni_per_giocatore(conn, giocatore_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        """SELECT v.*, p.data_partita, p.modalita
           FROM variazioni_rk v
           JOIN partite p ON p.id = v.partita_id
           WHERE v.giocatore_id = ? AND p.voided = 0
           ORDER BY p.data_partita ASC, p.created_at ASC, p.id ASC""",
        (giocatore_id,),
    )
    return rows_as_dicts(cur)


def fetch_variazioni_per_partita(conn, partita_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM variazioni_rk WHERE partita_id = ? ORDER BY squadra, id", (partita_id,)
    )
    return rows_as_dicts(cur)


# --- ranking_leader_log -------------------------------------------------------


def insert_leader_log(conn, giocatore_id: int, started_at: str) -> None:
    conn.execute(
        "INSERT INTO ranking_leader_log (giocatore_id, started_at) VALUES (?, ?)",
        (giocatore_id, started_at),
    )


def close_open_leader_logs(conn, ended_at: str) -> None:
    conn.execute(
        "UPDATE ranking_leader_log SET ended_at = ? WHERE ended_at IS NULL", (ended_at,)
    )


def fetch_open_leader(conn) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM ranking_leader_log WHERE ended_at IS NULL")
    return row_as_dict(cur, cur.fetchone())


def fetch_giorni_al_numero_1(conn) -> list[dict[str, Any]]:
    cur = conn.execute(
        """SELECT giocatore_id,
                  SUM(julianday(COALESCE(ended_at, date('now'))) - julianday(started_at)) AS giorni
           FROM ranking_leader_log
           GROUP BY giocatore_id
           ORDER BY giorni DESC"""
    )
    return rows_as_dicts(cur)


def delete_tutte_variazioni_e_leader_log(conn) -> None:
    """Usato solo da recompute_all: azzera le tabelle derivate prima del replay."""
    conn.execute("DELETE FROM variazioni_rk")
    conn.execute("DELETE FROM ranking_leader_log")

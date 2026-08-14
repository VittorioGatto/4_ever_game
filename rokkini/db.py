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


def _colonna_esiste(conn, tabella: str, colonna: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({tabella})")
    return any(row[1] == colonna for row in cur.fetchall())


def apply_schema(conn) -> None:
    """Crea le tabelle mancanti (CREATE TABLE IF NOT EXISTS, sicuro da
    rieseguire) e applica le poche modifiche additive a tabelle preesistenti
    (ALTER TABLE ADD COLUMN, guardato con un controllo di esistenza: SQLite
    non supporta ADD COLUMN IF NOT EXISTS)."""
    conn.executescript(SCHEMA_PATH.read_text())
    if not _colonna_esiste(conn, "partite", "sessione_id"):
        conn.execute("ALTER TABLE partite ADD COLUMN sessione_id INTEGER REFERENCES sessioni_gioco (id)")
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


def delete_giocatore(conn, giocatore_id: int) -> None:
    """Elimina un giocatore solo se non ha mai giocato: con delle partite
    registrate, eliminarlo lascerebbe partecipazioni_partita/variazioni_rk
    orfane e romperebbe rating_engine.recompute_all. Un giocatore con
    storico va sospeso (set_giocatore_sospeso), non eliminato."""
    giocatore = fetch_giocatore(conn, giocatore_id)
    if giocatore is None:
        return
    if giocatore["partite_giocate"] > 0:
        raise ValueError("Non si può eliminare un giocatore che ha già partite registrate.")
    conn.execute("DELETE FROM giocatori WHERE id = ?", (giocatore_id,))
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
    sessione_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO partite
               (data_partita, modalita, risultato_set, squadra_vincente, registered_by,
                replaces_match_id, sessione_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data_partita,
            modalita,
            risultato_set,
            squadra_vincente,
            registered_by,
            replaces_match_id,
            sessione_id,
        ),
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


# --- sessioni di gioco --------------------------------------------------------


def insert_sessione(conn, iniziata_da: int) -> int:
    cur = conn.execute("INSERT INTO sessioni_gioco (iniziata_da) VALUES (?)", (iniziata_da,))
    conn.commit()
    return cur.lastrowid


def termina_sessione(conn, sessione_id: int) -> None:
    conn.execute(
        "UPDATE sessioni_gioco SET terminata_at = datetime('now') WHERE id = ?", (sessione_id,)
    )
    conn.commit()


def fetch_sessione_attiva(conn) -> dict[str, Any] | None:
    cur = conn.execute(
        "SELECT * FROM sessioni_gioco WHERE terminata_at IS NULL ORDER BY id DESC LIMIT 1"
    )
    return row_as_dict(cur, cur.fetchone())


def fetch_sessione(conn, sessione_id: int) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM sessioni_gioco WHERE id = ?", (sessione_id,))
    return row_as_dict(cur, cur.fetchone())


def fetch_partecipanti_sessione(conn, sessione_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        """SELECT g.* FROM sessione_partecipanti sp
           JOIN giocatori g ON g.id = sp.giocatore_id
           WHERE sp.sessione_id = ? ORDER BY g.nome""",
        (sessione_id,),
    )
    return rows_as_dicts(cur)


def set_partecipanti_sessione(conn, sessione_id: int, giocatore_ids: list[int]) -> None:
    """Riconcilia la lista dei partecipanti con quella data: aggiunge chi
    manca, toglie chi non c'e' piu'. Non tocca le partite gia' registrate."""
    attuali = {
        row["giocatore_id"]
        for row in rows_as_dicts(
            conn.execute(
                "SELECT giocatore_id FROM sessione_partecipanti WHERE sessione_id = ?",
                (sessione_id,),
            )
        )
    }
    nuovi = set(giocatore_ids)
    for giocatore_id in nuovi - attuali:
        conn.execute(
            "INSERT INTO sessione_partecipanti (sessione_id, giocatore_id) VALUES (?, ?)",
            (sessione_id, giocatore_id),
        )
    for giocatore_id in attuali - nuovi:
        conn.execute(
            "DELETE FROM sessione_partecipanti WHERE sessione_id = ? AND giocatore_id = ?",
            (sessione_id, giocatore_id),
        )
    conn.commit()


def fetch_partite_di_sessione(conn, sessione_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        """SELECT * FROM partite WHERE sessione_id = ? AND voided = 0
           ORDER BY data_partita ASC, created_at ASC, id ASC""",
        (sessione_id,),
    )
    return rows_as_dicts(cur)

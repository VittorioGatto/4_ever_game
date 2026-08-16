"""Connessione al database (SQLite locale o Turso via libSQL) e CRUD di base."""

import json
from pathlib import Path
from typing import Any

import libsql
import streamlit as st

from rokkini import constants

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
    if not _colonna_esiste(conn, "sessioni_gioco", "programma_torneo"):
        conn.execute("ALTER TABLE sessioni_gioco ADD COLUMN programma_torneo TEXT")
    conn.execute(
        """INSERT OR IGNORE INTO parametri_calcolo
               (id, rk_iniziale, partite_qualificazione, fasce_json, k_factor_soglie_json,
                correttivo_massimo, correttivo_saturazione_sfavorito, correttivo_saturazione_favorito)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
        (
            constants.RK_INIZIALE,
            constants.PARTITE_QUALIFICAZIONE,
            json.dumps(constants.FASCE),
            json.dumps(constants.K_FACTOR_SOGLIE),
            constants.CORRETTIVO_MASSIMO,
            constants.CORRETTIVO_SATURAZIONE_SFAVORITO,
            constants.CORRETTIVO_SATURAZIONE_FAVORITO,
        ),
    )
    conn.commit()


@st.cache_resource
def _connessione_cacheata():
    """Usa Turso se configurato nei secrets, altrimenti il file locale
    (nessun secrets.toml in sviluppo)."""
    try:
        turso_cfg = st.secrets.get("turso")
    except st.errors.StreamlitSecretNotFoundError:
        turso_cfg = None
    if turso_cfg:
        return connect(turso_cfg["database_url"], turso_cfg["auth_token"])
    return connect()


def get_connection():
    """Connessione cacheata per l'app Streamlit, con un controllo di salute
    a ogni run dello script. Turso (protocollo Hrana) chiude lo stream della
    connessione lato server dopo un periodo di inattivita': una connessione
    cacheata riutilizzata dopo quell'idle time fallisce ogni query con
    "stream not found", e con @st.cache_resource questo blocca l'intera app
    per tutti gli utenti finche' il processo non viene riavviato. Per questo
    la connessione viene verificata con una query innocua prima di essere
    restituita: se lo stream e' morto, la cache viene scartata e se ne apre
    una nuova (nuovo stream Hrana)."""
    conn = _connessione_cacheata()
    try:
        conn.execute("SELECT 1")
    except Exception:
        _connessione_cacheata.clear()
        conn = _connessione_cacheata()
    return conn


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


# Dimensione massima di un blocco per gli INSERT multi-riga qui sotto: con
# Turso ogni query e' un round trip di rete, quindi inserire una riga alla
# volta (come faceva prima questo modulo) e' lento quando le righe sono
# centinaia — es. recompute_all su uno storico lungo. Il limite e' per
# restare sotto il numero massimo di parametri bind che SQLite accetta in
# un'unica query, non per prestazioni.
_DIMENSIONE_BLOCCO_INSERT = 200


def insert_partecipazioni_bulk(conn, righe: list[tuple[int, int, str]]) -> None:
    """righe: (partita_id, giocatore_id, squadra). Usato da register_match/
    edit_match per inserire tutti i partecipanti di una partita in una sola
    query invece di una per giocatore."""
    for i in range(0, len(righe), _DIMENSIONE_BLOCCO_INSERT):
        blocco = righe[i : i + _DIMENSIONE_BLOCCO_INSERT]
        segnaposto = ", ".join(["(?, ?, ?)"] * len(blocco))
        valori = [v for riga in blocco for v in riga]
        conn.execute(
            f"INSERT INTO partecipazioni_partita (partita_id, giocatore_id, squadra) VALUES {segnaposto}",
            valori,
        )


def fetch_partecipazioni(conn, partita_id: int) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT * FROM partecipazioni_partita WHERE partita_id = ? ORDER BY squadra, id",
        (partita_id,),
    )
    return rows_as_dicts(cur)


def fetch_tutte_partecipazioni_non_annullate(conn) -> dict[int, list[dict[str, Any]]]:
    """Le partecipazioni di tutte le partite non annullate, raggruppate per
    partita_id: usato da recompute_all per evitare una query SELECT per
    ogni partita dello storico (con Turso, centinaia di partite = centinaia
    di round trip di rete evitabili con un'unica query)."""
    cur = conn.execute(
        """SELECT pp.* FROM partecipazioni_partita pp
           JOIN partite p ON p.id = pp.partita_id
           WHERE p.voided = 0
           ORDER BY pp.partita_id, pp.squadra, pp.id"""
    )
    raggruppate: dict[int, list[dict[str, Any]]] = {}
    for riga in rows_as_dicts(cur):
        raggruppate.setdefault(riga["partita_id"], []).append(riga)
    return raggruppate


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


def insert_variazioni_bulk(conn, righe: list[tuple]) -> None:
    """righe: (partita_id, giocatore_id, squadra, esito, rk_prima, k_usato,
    probabilita_teorica, correttivo_usato, delta, rk_dopo). Usato da
    recompute_all, che su uno storico lungo puo' generare centinaia di
    variazioni: una query per riga significherebbe altrettanti round trip
    di rete verso Turso."""
    for i in range(0, len(righe), _DIMENSIONE_BLOCCO_INSERT):
        blocco = righe[i : i + _DIMENSIONE_BLOCCO_INSERT]
        segnaposto = ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(blocco))
        valori = [v for riga in blocco for v in riga]
        conn.execute(
            f"""INSERT INTO variazioni_rk
                    (partita_id, giocatore_id, squadra, esito, rk_prima, k_usato,
                     probabilita_teorica, correttivo_usato, delta, rk_dopo)
                VALUES {segnaposto}""",
            valori,
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


def fetch_tutte_variazioni(conn) -> list[dict[str, Any]]:
    """Tutte le variazioni Rk con la data della partita: usata per i record
    "stupidi" (rimonte, tonfi, serie nere) che guardano l'intero storico
    invece che un singolo giocatore. variazioni_rk esiste solo per partite
    non annullate (recompute_all la ricostruisce solo dal replay dello
    storico non annullato), quindi non serve filtrare qui."""
    cur = conn.execute(
        """SELECT v.*, p.data_partita FROM variazioni_rk v
           JOIN partite p ON p.id = v.partita_id
           ORDER BY p.data_partita ASC, p.created_at ASC, p.id ASC"""
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


def set_programma_torneo(conn, sessione_id: int, programma: dict | None) -> None:
    """Salva il piano del torneo (squadre/fixture o obiettivo del girone a
    rotazione) cosi' che sia visibile anche da chi guarda 'Sessioni attive'
    senza essere loggato: a differenza del resto dello stato della pagina
    Sessione di gioco (che vive solo in st.session_state, nel browser di chi
    gestisce il torneo), questo deve essere leggibile da qualunque
    dispositivo. `programma=None` lo cancella (es. quando si rigenerano le
    squadre da capo)."""
    conn.execute(
        "UPDATE sessioni_gioco SET programma_torneo = ? WHERE id = ?",
        (json.dumps(programma) if programma is not None else None, sessione_id),
    )
    conn.commit()


def fetch_programma_torneo(conn, sessione_id: int) -> dict | None:
    cur = conn.execute(
        "SELECT programma_torneo FROM sessioni_gioco WHERE id = ?", (sessione_id,)
    )
    row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    return json.loads(row[0])


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

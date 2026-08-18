import libsql

from rokkini import db, rating_engine


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_nessuna_sessione_attiva_su_db_vuoto(conn):
    assert db.fetch_sessione_attiva(conn) is None


def test_ciclo_di_vita_sessione(conn, admin_id):
    sessione_id = db.insert_sessione(conn, admin_id)
    attiva = db.fetch_sessione_attiva(conn)
    assert attiva is not None
    assert attiva["id"] == sessione_id
    assert attiva["terminata_at"] is None

    db.termina_sessione(conn, sessione_id)
    assert db.fetch_sessione_attiva(conn) is None
    chiusa = db.fetch_sessione(conn, sessione_id)
    assert chiusa["terminata_at"] is not None


def test_programma_torneo_round_trip_preserva_override_squadre_manuali(conn, admin_id):
    """La UI (app_pages/9_sessione_di_gioco.py) persiste le squadre modificate
    a mano per la fixture in corso dentro override_corrente, cosi' un cambio
    di pagina o un redeploy (che azzerano st.session_state) le ripristina
    invece di tornare a quelle generate automaticamente. Qui si verifica solo
    il round trip JSON del campo, non la UI."""
    sessione_id = db.insert_sessione(conn, admin_id)
    programma = {
        "tipo": "fisso",
        "dimensione": 3,
        "squadre": [[1, 2, 3], [4, 5, 6]],
        "fixture": [[0, 1]],
        "giocate": [],
        "override_corrente": {"idx": 0, "squadra_a": [1, 2, 7], "squadra_b": [4, 5, 6]},
    }
    db.set_programma_torneo(conn, sessione_id, programma)

    riletto = db.fetch_programma_torneo(conn, sessione_id)
    assert riletto["override_corrente"] == {"idx": 0, "squadra_a": [1, 2, 7], "squadra_b": [4, 5, 6]}


def test_programma_torneo_round_trip_preserva_scelta_e_squadre_rotante(conn, admin_id):
    """Stesso discorso della funzione precedente, per il girone a rotazione:
    l'admin puo' scegliere quale delle partite proposte giocare (non solo
    la prima), quindi va persistita anche quale ha scelto (scelta_idx) oltre
    alle sue squadre, eventualmente modificate a mano."""
    sessione_id = db.insert_sessione(conn, admin_id)
    programma = {
        "tipo": "rotante",
        "dimensione": 3,
        "conteggio": {"1": 0, "2": 0},
        "target": 4,
        "completate": 1,
        "partite_previste": [[[1, 2, 9], [4, 5, 6]], [[7, 8, 1], [2, 3, 4]]],
        "scelta_idx": 1,
        "squadra_a_corrente": [7, 8, 1],
        "squadra_b_corrente": [2, 3, 9],
    }
    db.set_programma_torneo(conn, sessione_id, programma)

    riletto = db.fetch_programma_torneo(conn, sessione_id)
    assert riletto["scelta_idx"] == 1
    assert riletto["squadra_a_corrente"] == [7, 8, 1]
    assert riletto["squadra_b_corrente"] == [2, 3, 9]


def test_sessioni_leader_log_round_trip_dedup(conn, admin_id):
    p = crea_giocatori(conn, 3)
    s1 = db.insert_sessione(conn, admin_id)
    s2 = db.insert_sessione(conn, admin_id)

    db.insert_sessioni_leader_bulk(conn, {(s1, p[0]), (s2, p[0])})
    # re-inserire la stessa coppia (es. un secondo recompute_all sulla stessa
    # sessione, come capita a ogni nuova partita registrata) non deve
    # duplicare la riga: UNIQUE(sessione_id, giocatore_id) + INSERT OR IGNORE
    db.insert_sessioni_leader_bulk(conn, {(s1, p[0])})
    conn.commit()

    risultato = db.fetch_sessioni_al_numero_1(conn)
    assert len(risultato) == 1
    assert risultato[0]["giocatore_id"] == p[0]
    assert risultato[0]["sessioni"] == 2


def test_set_partecipanti_sessione_aggiunge_e_rimuove(conn, admin_id):
    p = crea_giocatori(conn, 8)
    sessione_id = db.insert_sessione(conn, admin_id)

    db.set_partecipanti_sessione(conn, sessione_id, p[0:6])
    presenti = {g["id"] for g in db.fetch_partecipanti_sessione(conn, sessione_id)}
    assert presenti == set(p[0:6])

    # p[0] se ne va, p[6] e p[7] arrivano
    db.set_partecipanti_sessione(conn, sessione_id, [*p[1:6], p[6], p[7]])
    presenti = {g["id"] for g in db.fetch_partecipanti_sessione(conn, sessione_id)}
    assert presenti == set(p[1:8])
    assert p[0] not in presenti


def test_register_match_collega_la_partita_alla_sessione(conn, admin_id):
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    db.set_partecipanti_sessione(conn, sessione_id, p)

    partita_id = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    partita = db.fetch_partita(conn, partita_id)
    assert partita["sessione_id"] == sessione_id

    partite_sessione = db.fetch_partite_di_sessione(conn, sessione_id)
    assert len(partite_sessione) == 1
    assert partite_sessione[0]["id"] == partita_id


def test_register_match_senza_sessione_ha_sessione_id_nullo(conn, admin_id):
    p = crea_giocatori(conn, 6)
    partita_id = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    assert db.fetch_partita(conn, partita_id)["sessione_id"] is None


def test_edit_match_mantiene_la_sessione_originale(conn, admin_id):
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    partita_id = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    nuova_id = rating_engine.edit_match(
        conn, partita_id, "3v3", "2-1", "B", p[0:3], p[3:6], admin_id
    )
    assert db.fetch_partita(conn, nuova_id)["sessione_id"] == sessione_id


def test_migrazione_aggiunge_colonna_sessione_id_a_db_preesistente(tmp_path):
    """Simula un database creato prima dell'introduzione delle sessioni di
    gioco (tabella partite senza la colonna sessione_id) e verifica che
    apply_schema la aggiunga senza errori e senza perdere dati."""
    db_file = tmp_path / "vecchio.db"
    connessione = libsql.connect(database=str(db_file))
    connessione.execute("PRAGMA foreign_keys = ON")
    connessione.execute("""
        CREATE TABLE utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            nome_visualizzato TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            ruolo TEXT NOT NULL,
            giocatore_id INTEGER,
            attivo INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    connessione.execute("""
        CREATE TABLE partite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_partita TEXT NOT NULL,
            modalita TEXT NOT NULL,
            risultato_set TEXT NOT NULL,
            squadra_vincente TEXT NOT NULL,
            voided INTEGER NOT NULL DEFAULT 0,
            voided_at TEXT,
            voided_by INTEGER,
            voided_reason TEXT,
            replaces_match_id INTEGER,
            registered_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    utente_id = connessione.execute(
        "INSERT INTO utenti (username, nome_visualizzato, password_hash, ruolo) VALUES (?, ?, ?, ?)",
        ("x", "X", "hash", "super_admin"),
    ).lastrowid
    connessione.execute(
        "INSERT INTO partite (data_partita, modalita, risultato_set, squadra_vincente, registered_by) "
        "VALUES ('2026-01-01', '3v3', '2-0', 'A', ?)",
        (utente_id,),
    )
    connessione.commit()
    assert not db._colonna_esiste(connessione, "partite", "sessione_id")

    db.apply_schema(connessione)

    assert db._colonna_esiste(connessione, "partite", "sessione_id")
    partite = db.fetch_partite_tutte(connessione)
    assert len(partite) == 1
    assert partite[0]["sessione_id"] is None

    # rieseguirla non deve fallire (idempotenza)
    db.apply_schema(connessione)
    connessione.close()

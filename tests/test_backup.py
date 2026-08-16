import libsql
import pytest

from rokkini import backup, db, rating_engine


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def _stato_giocatori(conn) -> list[dict]:
    return [
        {k: v for k, v in g.items() if k != "created_at"} for g in db.fetch_giocatori(conn)
    ]


def test_export_contiene_tutte_le_tabelle(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    dump = backup.export_data(conn)
    assert dump["versione"] == 1
    assert set(dump["tabelle"].keys()) == set(backup.TABELLE)
    assert len(dump["tabelle"]["giocatori"]) == 6
    assert len(dump["tabelle"]["utenti"]) == 1
    assert len(dump["tabelle"]["partite"]) == 1
    assert len(dump["tabelle"]["partecipazioni_partita"]) == 6
    assert len(dump["tabelle"]["variazioni_rk"]) == 6


def test_import_rifiuta_versione_sconosciuta(conn):
    with pytest.raises(ValueError, match="non riconosciuto"):
        backup.import_data(conn, {"versione": 999, "tabelle": {}})


def test_round_trip_export_import_su_db_pulito(conn, admin_id, tmp_path):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-02", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)

    dump = backup.export_data(conn)
    stato_originale = _stato_giocatori(conn)

    nuovo_db = tmp_path / "restore.db"
    nuova_conn = libsql.connect(database=str(nuovo_db))
    nuova_conn.execute("PRAGMA foreign_keys = ON")
    db.apply_schema(nuova_conn)

    backup.import_data(nuova_conn, dump)

    stato_ripristinato = _stato_giocatori(nuova_conn)
    assert stato_ripristinato == stato_originale

    partite_originali = db.fetch_partite_tutte(conn)
    partite_ripristinate = db.fetch_partite_tutte(nuova_conn)
    assert len(partite_ripristinate) == len(partite_originali)

    nuova_conn.close()


def test_round_trip_con_sessione_di_gioco_su_db_pulito(conn, admin_id, tmp_path):
    """Una partita con sessione_id valorizzato deve poter essere esportata e
    reimportata su un DB diverso da quello di origine (lo scopo stesso del
    backup): senza sessioni_gioco/sessione_partecipanti nell'elenco delle
    tabelle esportate, l'INSERT in partite fallisce con FOREIGN KEY
    constraint failed perche' la sessione referenziata non esiste sul DB di
    destinazione."""
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    db.set_partecipanti_sessione(conn, sessione_id, p)
    rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )

    dump = backup.export_data(conn)
    assert dump["tabelle"]["sessioni_gioco"]
    assert dump["tabelle"]["sessione_partecipanti"]

    nuovo_db = tmp_path / "restore_sessione.db"
    nuova_conn = libsql.connect(database=str(nuovo_db))
    nuova_conn.execute("PRAGMA foreign_keys = ON")
    db.apply_schema(nuova_conn)

    backup.import_data(nuova_conn, dump)  # non deve sollevare FOREIGN KEY constraint failed

    partite_ripristinate = db.fetch_partite_tutte(nuova_conn)
    assert len(partite_ripristinate) == 1
    assert partite_ripristinate[0]["sessione_id"] == sessione_id
    assert len(db.fetch_partecipanti_sessione(nuova_conn, sessione_id)) == 6

    nuova_conn.close()


def test_import_sostituisce_non_unisce(conn, admin_id):
    p = crea_giocatori(conn, 6)
    dump_vuoto_di_partite = backup.export_data(conn)  # solo 6 giocatori, nessuna partita

    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    assert len(db.fetch_partite_tutte(conn)) == 1

    backup.import_data(conn, dump_vuoto_di_partite)

    assert len(db.fetch_partite_tutte(conn)) == 0
    assert len(db.fetch_giocatori(conn)) == 6


def test_reset_completo_azzera_partite_e_statistiche(conn, admin_id):
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    db.set_partecipanti_sessione(conn, sessione_id, p)
    rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    rating_engine.register_match(conn, "2026-01-02", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)

    assert len(db.fetch_partite_tutte(conn)) == 2
    giocatore_dopo_partite = db.fetch_giocatore(conn, p[0])
    assert giocatore_dopo_partite["rk_attuale"] != 1000 or giocatore_dopo_partite["partite_giocate"] != 0

    backup.reset_completo(conn)

    assert db.fetch_partite_tutte(conn) == []
    assert db.fetch_sessione_attiva(conn) is None
    giocatori_dopo_reset = db.fetch_giocatori(conn)
    assert len(giocatori_dopo_reset) == 6  # i giocatori come account restano
    for g in giocatori_dopo_reset:
        assert g["rk_attuale"] == 1000
        assert g["partite_giocate"] == 0
        assert g["vittorie"] == 0
        assert g["sconfitte"] == 0
        assert g["rk_record"] == 1000
        assert g["streak_vittorie_corrente"] == 0
        assert g["streak_vittorie_record"] == 0


def test_export_csv_contiene_le_partite_vinte_e_i_rk(conn, admin_id):
    p = crea_giocatori(conn, 6, "J")
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    righe_giocatori = backup.export_giocatori_csv(conn)
    righe_partite = backup.export_partite_csv(conn)

    assert len(righe_giocatori) == 6
    assert all(r["data_esportazione"] for r in righe_giocatori)
    assert len(righe_partite) == 1
    partita = righe_partite[0]
    assert partita["squadra_vincente"] == "A"
    assert set(partita["squadra_a"].split(";")) == {"J1", "J2", "J3"}
    assert set(partita["squadra_b"].split(";")) == {"J4", "J5", "J6"}
    assert partita["data_esportazione"]


def test_export_csv_esclude_partite_annullate(conn, admin_id):
    p = crea_giocatori(conn, 6, "K")
    partita_id = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    rating_engine.void_match(conn, partita_id, admin_id, "test")

    assert backup.export_partite_csv(conn) == []


def test_round_trip_csv_ripristina_partite_e_rk(conn, admin_id):
    p = crea_giocatori(conn, 6, "L")
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-02", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)

    righe_giocatori = backup.export_giocatori_csv(conn)
    righe_partite = backup.export_partite_csv(conn)
    rk_atteso = {r["nome"]: r["rk_attuale"] for r in righe_giocatori}

    backup.import_csv(conn, righe_giocatori, righe_partite, admin_id)

    giocatori_dopo = {g["nome"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
    assert giocatori_dopo == rk_atteso
    assert len(db.fetch_partite_non_annullate(conn)) == 2


def test_import_csv_congela_rk_anche_se_la_logica_cambia(conn, admin_id, monkeypatch):
    """Se il K-factor cambia dopo l'esportazione, il replay delle partite
    durante il ripristino produrrebbe Rk diversi da quelli esportati: il Rk
    "ufficiale" deve restare quello congelato nel file giocatori."""
    p = crea_giocatori(conn, 6, "M")
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    righe_giocatori = backup.export_giocatori_csv(conn)
    righe_partite = backup.export_partite_csv(conn)
    rk_congelato = {r["nome"]: int(r["rk_attuale"]) for r in righe_giocatori}

    monkeypatch.setattr("rokkini.elo.K_FACTOR_SOGLIE", [(1, 999)])

    backup.import_csv(conn, righe_giocatori, righe_partite, admin_id)

    giocatori_dopo = {g["nome"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
    assert giocatori_dopo == rk_congelato


def test_import_csv_crea_giocatori_mancanti(conn, admin_id):
    p = crea_giocatori(conn, 6, "N")
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    righe_giocatori = backup.export_giocatori_csv(conn)
    righe_partite = backup.export_partite_csv(conn)

    nuova_conn = conn
    for nome_tabella in reversed(backup.TABELLE):
        if nome_tabella != "utenti":
            nuova_conn.execute(f"DELETE FROM {nome_tabella}")
    nuova_conn.commit()

    backup.import_csv(nuova_conn, righe_giocatori, righe_partite, admin_id)

    assert len(db.fetch_giocatori(nuova_conn)) == 6
    assert len(db.fetch_partite_non_annullate(nuova_conn)) == 1


def test_import_fallito_fa_rollback(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    stato_prima = _stato_giocatori(conn)

    dump_corrotto = backup.export_data(conn)
    # riga malformata: colonna inesistente, fa fallire l'INSERT
    dump_corrotto["tabelle"]["giocatori"][0]["colonna_che_non_esiste"] = "x"

    with pytest.raises(Exception):  # noqa: B017 - qualunque errore SQL della colonna inventata
        backup.import_data(conn, dump_corrotto)

    assert _stato_giocatori(conn) == stato_prima

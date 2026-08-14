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


def test_import_sostituisce_non_unisce(conn, admin_id):
    p = crea_giocatori(conn, 6)
    dump_vuoto_di_partite = backup.export_data(conn)  # solo 6 giocatori, nessuna partita

    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    assert len(db.fetch_partite_tutte(conn)) == 1

    backup.import_data(conn, dump_vuoto_di_partite)

    assert len(db.fetch_partite_tutte(conn)) == 0
    assert len(db.fetch_giocatori(conn)) == 6


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

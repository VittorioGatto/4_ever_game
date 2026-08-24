from dataclasses import replace

import pytest

from rokkini import db, parametri, rating_engine


def test_insert_giocatore_usa_rk_iniziale_attivo_non_il_default_dello_schema(conn):
    """schema.sql ha rk_attuale/fascia_attuale DEFAULT 1000/'H' fissi: senza
    passarli esplicitamente, un giocatore creato dopo che rk_iniziale e'
    stato spostato (es. dalla pagina Simulazione) nascerebbe con lo Rk
    sbagliato — esattamente il bug segnalato in produzione."""
    parametri.salva_parametri_attivi(conn, replace(parametri.DEFAULT, rk_iniziale=1250))

    giocatore_id = db.insert_giocatore(conn, "NuovoGiocatore")

    giocatore = db.fetch_giocatore(conn, giocatore_id)
    assert giocatore["rk_attuale"] == 1250
    assert giocatore["rk_record"] == 1250
    assert giocatore["fascia_attuale"] == "C"


def test_delete_giocatore_senza_partite(conn):
    giocatore_id = db.insert_giocatore(conn, "Test")
    db.delete_giocatore(conn, giocatore_id)
    assert db.fetch_giocatore(conn, giocatore_id) is None


def test_delete_giocatore_con_partite_solleva_errore(conn, admin_id):
    p = [db.insert_giocatore(conn, f"P{i}") for i in range(1, 7)]
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    with pytest.raises(ValueError, match="partite registrate"):
        db.delete_giocatore(conn, p[0])
    assert db.fetch_giocatore(conn, p[0]) is not None


def test_delete_giocatore_inesistente_non_fa_nulla(conn):
    db.delete_giocatore(conn, 999999)  # nessuna eccezione


def test_delete_giocatore_collegato_a_utente_fallisce(conn):
    giocatore_id = db.insert_giocatore(conn, "Collegato")
    db.insert_utente(
        conn,
        username="collegato",
        nome_visualizzato="Collegato",
        password_hash="x",
        giocatore_id=giocatore_id,
    )
    with pytest.raises(Exception):  # noqa: B017 - vincolo FK, il messaggio dipende dal driver
        db.delete_giocatore(conn, giocatore_id)

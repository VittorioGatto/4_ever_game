from dataclasses import replace

from rokkini import db, parametri, rating_engine


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_apply_schema_semina_parametri_di_default(conn):
    attivi = parametri.fetch_parametri_attivi(conn)
    assert attivi == parametri.DEFAULT


def test_salva_parametri_attivi_persiste(conn):
    nuovi = replace(parametri.DEFAULT, rk_iniziale=1500, partite_qualificazione=3)
    parametri.salva_parametri_attivi(conn, nuovi)

    riletti = parametri.fetch_parametri_attivi(conn)
    assert riletti.rk_iniziale == 1500
    assert riletti.partite_qualificazione == 3
    # il resto non tocca
    assert riletti.k_factor_soglie == parametri.DEFAULT.k_factor_soglie


def test_register_match_usa_i_parametri_attivi(conn, admin_id):
    """Cambiare i parametri attivi PRIMA di registrare una partita deve
    riflettersi sul calcolo, senza bisogno di passare nulla esplicitamente a
    register_match: recompute_all pesca da solo i parametri dal DB."""
    parametri.salva_parametri_attivi(conn, replace(parametri.DEFAULT, rk_iniziale=2000))

    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    vincitore = db.fetch_giocatore(conn, p[0])
    assert vincitore["rk_attuale"] > 2000  # partito da 2000, non dal vecchio default


def test_simula_classifica_non_scrive_sul_db(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    stato_prima = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}

    parametri_ipotetici = replace(parametri.DEFAULT, rk_iniziale=5000)
    risultato = rating_engine.simula_classifica(conn, parametri_ipotetici)

    stato_dopo = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
    assert stato_prima == stato_dopo  # il DB non e' stato toccato

    # ma il risultato simulato riflette il Rk iniziale ipotetico
    assert all(r["rk_simulato"] > 5000 - 100 for r in risultato)
    assert {r["nome"] for r in risultato} == {g["nome"] for g in db.fetch_giocatori(conn)}


def test_simula_classifica_ordina_per_rk_decrescente(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    risultato = rating_engine.simula_classifica(conn, parametri.DEFAULT)
    valori = [r["rk_simulato"] for r in risultato]
    assert valori == sorted(valori, reverse=True)


def test_applicare_parametri_diversi_cambia_il_risultato_del_ricalcolo(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rk_con_default = db.fetch_giocatore(conn, p[0])["rk_attuale"]

    nuovi_parametri = replace(parametri.DEFAULT, rk_iniziale=parametri.DEFAULT.rk_iniziale + 500)
    parametri.salva_parametri_attivi(conn, nuovi_parametri)
    rating_engine.recompute_all(conn)
    conn.commit()

    rk_con_nuovi_parametri = db.fetch_giocatore(conn, p[0])["rk_attuale"]
    assert rk_con_nuovi_parametri == rk_con_default + 500

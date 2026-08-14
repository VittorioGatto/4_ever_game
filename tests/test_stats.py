from rokkini import db, rating_engine, stats


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_ranking_esclude_non_qualificati(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    ranking = stats.fetch_ranking(conn)
    qualificazione = stats.fetch_in_qualificazione(conn)
    assert ranking.height == 0  # nessuno ha ancora 8 partite
    assert qualificazione.height == 6


def test_ranking_ordinato_per_rk_dopo_qualificazione(conn, admin_id):
    p = crea_giocatori(conn, 6)
    for i in range(8):
        rating_engine.register_match(
            conn, f"2026-01-{i + 1:02d}", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
        )
    ranking = stats.fetch_ranking(conn)
    assert ranking.height == 6
    assert list(ranking["posizione"]) == list(range(1, 7))
    rk_valori = list(ranking["rk_attuale"])
    assert rk_valori == sorted(rk_valori, reverse=True)


def test_player_profile_storico_rk_include_punto_iniziale(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    profilo = stats.fetch_player_profile(conn, p[0])
    assert profilo is not None
    assert profilo["storico_rk"]["rk"][0] == 1000
    assert profilo["storico_rk"].height == 2  # punto iniziale + una partita


def test_match_history_contiene_rosters_e_delta(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    cronologia = stats.fetch_match_history(conn)
    assert len(cronologia) == 1
    assert len(cronologia[0]["squadra_a"]) == 3
    assert len(cronologia[0]["squadra_b"]) == 3
    assert all(giocatore["delta"] > 0 for giocatore in cronologia[0]["squadra_a"])


def test_records_rk_piu_alto(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    record = stats.fetch_records(conn)
    assert record["rk_piu_alto"]["valore"] == 1020


def test_classifica_sessione_somma_i_delta_e_ordina(conn, admin_id):
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    classifica = stats.fetch_classifica_sessione(conn, sessione_id)
    nomi_per_id = {g["id"]: g["nome"] for g in db.fetch_giocatori(conn)}

    # p[0..2] hanno vinto entrambe: rk_sessione positivo e maggiore di chi ha perso
    per_nome = {r["nome"]: r for r in classifica}
    for gid in p[0:3]:
        assert per_nome[nomi_per_id[gid]]["rk_sessione"] > 0
    for gid in p[3:6]:
        assert per_nome[nomi_per_id[gid]]["rk_sessione"] < 0

    valori = [r["rk_sessione"] for r in classifica]
    assert valori == sorted(valori, reverse=True)

    # rk_totale deve coincidere con l'rk_attuale corrente del giocatore
    giocatori_per_id = {g["id"]: g for g in db.fetch_giocatori(conn)}
    for gid in p:
        assert per_nome[nomi_per_id[gid]]["rk_totale"] == giocatori_per_id[gid]["rk_attuale"]


def test_classifica_sessione_esclude_partite_annullate_e_altre_sessioni(conn, admin_id):
    p = crea_giocatori(conn, 6)
    sessione_id = db.insert_sessione(conn, admin_id)
    partita_id = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id, sessione_id=sessione_id
    )
    # partita fuori sessione: non deve contare
    rating_engine.register_match(conn, "2026-01-02", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    assert stats.fetch_classifica_sessione(conn, sessione_id) != []

    rating_engine.void_match(conn, partita_id, admin_id, "test")
    assert stats.fetch_classifica_sessione(conn, sessione_id) == []

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

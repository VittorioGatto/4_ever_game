from rokkini import db, rating_engine, stats
from rokkini.constants import PARTITE_QUALIFICAZIONE


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_ranking_esclude_non_qualificati(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    ranking = stats.fetch_ranking(conn)
    qualificazione = stats.fetch_in_qualificazione(conn)
    assert ranking.height == 0  # nessuno ha ancora le partite di qualificazione
    assert qualificazione.height == 6


def test_ranking_ordinato_per_rk_dopo_qualificazione(conn, admin_id):
    p = crea_giocatori(conn, 6)
    for i in range(PARTITE_QUALIFICAZIONE):
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


def test_match_history_per_giorno_raggruppa_e_ordina(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-02", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    giorni = stats.fetch_match_history_per_giorno(conn)
    assert [g["data"] for g in giorni] == ["2026-01-02", "2026-01-01"]  # piu' recente prima
    assert len(giorni[0]["partite"]) == 1
    assert len(giorni[1]["partite"]) == 2

    # giorno 1: una vittoria e una sconfitta per p[0:3] -> deltas che si
    # compensano parzialmente, la classifica del giorno riflette la somma
    nomi_classifica = [r["nome"] for r in giorni[1]["classifica"]]
    assert set(nomi_classifica) == {
        g["nome"] for g in db.fetch_giocatori(conn) if g["id"] in p
    }
    valori = [r["rk_giorno"] for r in giorni[1]["classifica"]]
    assert valori == sorted(valori, reverse=True)


def test_records_rk_piu_alto(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    record = stats.fetch_records(conn)
    assert record["rk_piu_alto"]["valore"] == 1025


def test_record_stupidi_su_db_vuoto_non_esplode(conn):
    record = stats.fetch_record_stupidi(conn)
    assert record == {
        "rimonta_clamorosa": None,
        "sorpresa_piu_grande": None,
        "tonfo_doloroso": None,
        "serie_sconfitte": None,
        "giornata_intensa": None,
    }


def test_record_stupidi_rimonta_e_tonfo_sono_lo_stesso_delta_di_specchio(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    record = stats.fetch_record_stupidi(conn)
    # in una partita 3v3 tutti i vincitori/perdenti hanno lo stesso Rk di
    # partenza (1000), quindi lo stesso delta: qui basta verificare segno e
    # coerenza reciproca (il tonfo e' il negativo esatto della rimonta).
    assert record["rimonta_clamorosa"]["valore"] > 0
    assert record["tonfo_doloroso"]["valore"] == -record["rimonta_clamorosa"]["valore"]


def test_record_stupidi_serie_sconfitte_conta_solo_consecutive(conn, admin_id):
    p = crea_giocatori(conn, 6)
    # P1 (in squadra A) perde, vince, perde, perde: la serie piu' lunga e' 2
    rating_engine.register_match(conn, "2026-01-01", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-02", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-03", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-04", "3v3", "1-2", "B", p[0:3], p[3:6], admin_id)

    record = stats.fetch_record_stupidi(conn)
    assert record["serie_sconfitte"]["valore"] == 2


def test_record_stupidi_giornata_intensa_conta_partite_nello_stesso_giorno(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)
    rating_engine.register_match(conn, "2026-01-02", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id)

    record = stats.fetch_record_stupidi(conn)
    assert record["giornata_intensa"]["valore"] == 2


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

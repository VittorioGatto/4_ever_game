from rokkini import db, rating_engine
from rokkini.constants import PARTITE_QUALIFICAZIONE


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_registrazione_sequenziale_aggiorna_rk_e_partite(conn, admin_id):
    p = crea_giocatori(conn, 6)
    rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    giocatori = {g["id"]: g for g in db.fetch_giocatori(conn)}
    for gid in p[0:3]:
        assert giocatori[gid]["rk_attuale"] == 1025  # squadre pari, K=50, P=0.5 -> +25
        assert giocatori[gid]["vittorie"] == 1
        assert giocatori[gid]["partite_giocate"] == 1
    for gid in p[3:6]:
        assert giocatori[gid]["rk_attuale"] == 975
        assert giocatori[gid]["sconfitte"] == 1

    # seconda partita: rk_prima memorizzato deve combaciare col rk_attuale post-prima-partita
    seconda_partita_id = rating_engine.register_match(
        conn, "2026-01-02", "3v3", "2-0", "B", p[0:3], p[3:6], admin_id
    )
    variazioni = db.fetch_variazioni_per_partita(conn, seconda_partita_id)
    for v in variazioni:
        if v["giocatore_id"] in p[0:3]:
            assert v["rk_prima"] == 1025
        else:
            assert v["rk_prima"] == 975


def test_void_match_ricalcola_come_se_non_fosse_mai_avvenuta(conn, admin_id):
    p = crea_giocatori(conn, 6)
    m1 = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    rating_engine.register_match(
        conn, "2026-01-02", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    rk_prima_del_void = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
    assert rk_prima_del_void[p[0]] != 1000  # ha gia' giocato

    rating_engine.void_match(conn, m1, admin_id, "risultato errato")

    assert db.fetch_variazioni_per_partita(conn, m1) == []
    giocatori = {g["id"]: g for g in db.fetch_giocatori(conn)}
    for gid in p[0:3]:
        assert giocatori[gid]["partite_giocate"] == 1  # solo la seconda partita conta ancora
        assert giocatori[gid]["rk_attuale"] == 1025  # ricalcolato come fosse la prima e unica


def test_edit_match_sostituisce_la_partita_mantenendo_la_data(conn, admin_id):
    p = crea_giocatori(conn, 6)
    m1 = rating_engine.register_match(
        conn, "2026-01-01", "3v3", "2-0", "A", p[0:3], p[3:6], admin_id
    )
    nuova_id = rating_engine.edit_match(
        conn, m1, "3v3", "2-1", "B", p[0:3], p[3:6], admin_id
    )

    originale = db.fetch_partita(conn, m1)
    assert originale["voided"] == 1
    assert originale["voided_reason"] == "corretta"
    nuova = db.fetch_partita(conn, nuova_id)
    assert nuova["replaces_match_id"] == m1
    assert nuova["data_partita"] == "2026-01-01"
    assert nuova["squadra_vincente"] == "B"

    giocatori = {g["id"]: g for g in db.fetch_giocatori(conn)}
    for gid in p[0:3]:
        assert giocatori[gid]["rk_attuale"] == 975  # ora hanno perso, non vinto
    for gid in p[3:6]:
        assert giocatori[gid]["rk_attuale"] == 1025


def test_qualificazione_dopo_partite_di_qualificazione(conn, admin_id):
    protagonista = crea_giocatori(conn, 1)[0]
    for i in range(PARTITE_QUALIFICAZIONE):
        compagni = crea_giocatori(conn, 2, prefisso=f"C{i}_")
        avversari = crea_giocatori(conn, 3, prefisso=f"D{i}_")
        rating_engine.register_match(
            conn,
            f"2026-02-{i + 1:02d}",
            "3v3",
            "2-0",
            "A",
            [protagonista, *compagni],
            avversari,
            admin_id,
        )
        protagonista_row = db.fetch_giocatore(conn, protagonista)
        if protagonista_row["partite_giocate"] < PARTITE_QUALIFICAZIONE:
            assert protagonista_row["qualificato"] == 0
        else:
            assert protagonista_row["qualificato"] == 1
    assert db.fetch_giocatore(conn, protagonista)["partite_giocate"] == PARTITE_QUALIFICAZIONE


def test_k_factor_cambia_a_soglie_partite(conn, admin_id):
    protagonista = crea_giocatori(conn, 1)[0]
    k_attesi = []
    for i in range(15):  # 15 partite: la quindicesima deve usare K=32 (scaglione 15-25)
        compagni = crea_giocatori(conn, 2, prefisso=f"C{i}_")
        avversari = crea_giocatori(conn, 3, prefisso=f"D{i}_")
        m_id = rating_engine.register_match(
            conn,
            f"2026-03-{i + 1:02d}",
            "3v3",
            "2-0",
            "A",
            [protagonista, *compagni],
            avversari,
            admin_id,
        )
        variazioni = db.fetch_variazioni_per_partita(conn, m_id)
        k_usato = next(v["k_usato"] for v in variazioni if v["giocatore_id"] == protagonista)
        k_attesi.append(k_usato)
    assert k_attesi[0:5] == [50] * 5
    assert k_attesi[5:14] == [40] * 9
    assert k_attesi[14] == 32


def test_void_produce_effetto_a_catena_oltre_i_giocatori_originali(conn, admin_id):
    """Annullare una partita puo' cambiare l'esito di partite successive anche
    per giocatori che non hanno mai giocato insieme o contro i partecipanti
    della partita annullata, se sono collegati indirettamente tramite un
    giocatore che ha giocato in entrambe le partite."""
    p4 = crea_giocatori(conn, 1, prefisso="P4_")[0]
    p7, p8 = crea_giocatori(conn, 2, prefisso="P7P8_")
    p9, p10, p11 = crea_giocatori(conn, 3, prefisso="P9P10P11_")

    # p4 perde molte partite di fila contro avversari sempre nuovi,
    # accumulando un deficit di Rk consistente
    matches_precedenti = []
    for i in range(10):
        compagni = crea_giocatori(conn, 2, prefisso=f"PRE{i}_")
        avversari = crea_giocatori(conn, 3, prefisso=f"OPP{i}_")
        m_id = rating_engine.register_match(
            conn, f"2026-01-{i + 1:02d}", "3v3", "2-0", "B", [*compagni, p4], avversari, admin_id
        )
        matches_precedenti.append(m_id)

    # match successivo: p4 gioca con p7,p8 contro p9,p10,p11 (mai visti prima)
    m2 = rating_engine.register_match(
        conn, "2026-02-01", "3v3", "2-0", "A", [p4, p7, p8], [p9, p10, p11], admin_id
    )
    variazioni_prima = {
        v["giocatore_id"]: v["rk_dopo"] for v in db.fetch_variazioni_per_partita(conn, m2)
    }

    rating_engine.void_match(conn, matches_precedenti[0], admin_id, "test cascata")

    variazioni_dopo = {
        v["giocatore_id"]: v["rk_dopo"] for v in db.fetch_variazioni_per_partita(conn, m2)
    }

    # p4 ha ora un deficit di Rk minore (una sconfitta in meno prima del match
    # successivo): la media della sua squadra cambia, quindi cambiano anche i
    # delta di p7/p8 (compagni) e p9/p10/p11 (avversari), pur non avendo mai
    # incontrato nessuno delle partite annullate.
    for giocatore_id in (p7, p8, p9, p10, p11):
        assert variazioni_prima[giocatore_id] != variazioni_dopo[giocatore_id]

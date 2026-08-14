import pytest

from rokkini.matchmaking import (
    GiocatorePerMatchmaking,
    genera_combinazioni_bilanciate,
    genera_fixture_girone,
    genera_squadre_multiple,
)


def _giocatori(rk_values: list[int]) -> list[GiocatorePerMatchmaking]:
    return [GiocatorePerMatchmaking(player_id=i, rk_attuale=rk) for i, rk in enumerate(rk_values)]


def test_richiede_esattamente_il_doppio_della_dimensione():
    with pytest.raises(ValueError, match="6 giocatori"):
        genera_combinazioni_bilanciate(_giocatori([1000] * 5), dimensione=3)


def test_squadre_pari_hanno_differenza_zero():
    giocatori = _giocatori([1000, 1000, 1000, 1000, 1000, 1000])
    proposte = genera_combinazioni_bilanciate(giocatori, dimensione=3, n_proposte=1)
    assert proposte[0].differenza == pytest.approx(0.0)


def test_migliori_proposte_minimizzano_la_differenza():
    """6 giocatori con Rk 1000..1500: la matematica intera dice che esistono
    esattamente 3 split che raggiungono la differenza minima possibile
    (100/3, dato che nessun sottoinsieme di 3 valori somma esattamente a
    meta' del totale), verificato a mano enumerando le 20 terne."""
    giocatori = _giocatori([1000, 1100, 1200, 1300, 1400, 1500])
    proposte = genera_combinazioni_bilanciate(giocatori, dimensione=3, n_proposte=3)
    assert len(proposte) == 3
    for p in proposte:
        assert p.differenza == pytest.approx(100 / 3)

    # una quarta proposta, se richiesta, deve avere una differenza maggiore
    quarta = genera_combinazioni_bilanciate(giocatori, dimensione=3, n_proposte=4)[3]
    assert quarta.differenza > proposte[0].differenza


def test_nessuno_split_duplicato_o_speculare():
    giocatori = _giocatori([1000, 1050, 1100, 1150, 1200, 1250])
    tutte = genera_combinazioni_bilanciate(giocatori, dimensione=3, n_proposte=100)
    # C(6,3)/2 = 10 partizioni uniche (fissando un giocatore sempre in squadra A)
    assert len(tutte) == 10
    squadre_a_come_insiemi = {frozenset(p.squadra_a) for p in tutte}
    assert len(squadre_a_come_insiemi) == 10  # nessun duplicato


def test_4v4_conta_le_partizioni_uniche():
    giocatori = _giocatori([1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350])
    tutte = genera_combinazioni_bilanciate(giocatori, dimensione=4, n_proposte=1000)
    assert len(tutte) == 35  # C(8,4)/2


def test_squadra_a_e_b_non_si_sovrappongono_e_coprono_tutti():
    giocatori = _giocatori([1000, 1100, 1200, 1300, 1400, 1500])
    for p in genera_combinazioni_bilanciate(giocatori, dimensione=3, n_proposte=10):
        assert set(p.squadra_a) & set(p.squadra_b) == set()
        assert set(p.squadra_a) | set(p.squadra_b) == {g.player_id for g in giocatori}


# --- genera_squadre_multiple -------------------------------------------------


def test_squadre_multiple_richiede_almeno_due_squadre():
    with pytest.raises(ValueError, match="6 giocatori"):
        genera_squadre_multiple(_giocatori([1000] * 5), dimensione=3)


def test_squadre_multiple_dimensioni_e_copertura():
    giocatori = _giocatori([100, 90, 80, 70, 60, 50, 40, 30, 20])  # 9 -> 3 squadre da 3
    squadre = genera_squadre_multiple(giocatori, dimensione=3)
    assert len(squadre) == 3
    assert all(len(s) == 3 for s in squadre)
    tutti_gli_id = {gid for squadra in squadre for gid in squadra}
    assert tutti_gli_id == {g.player_id for g in giocatori}  # nessuno escluso, 9 e' multiplo di 3


def test_squadre_multiple_draft_a_serpentina_bilancia():
    """Rk decrescenti [100..20]: verificato a mano che il draft a serpentina
    (giro 0: 0,1,2 — giro 1: 2,1,0 — giro 2: 0,1,2) produce squadre con somme
    190/180/170, molto piu' vicine tra loro del min/max dei valori (20-100)."""
    giocatori = _giocatori([100, 90, 80, 70, 60, 50, 40, 30, 20])
    squadre = genera_squadre_multiple(giocatori, dimensione=3)
    rk_per_id = {g.player_id: g.rk_attuale for g in giocatori}
    somme = [sum(rk_per_id[gid] for gid in squadra) for squadra in squadre]
    assert somme == [190, 180, 170]


def test_squadre_multiple_esclude_eccesso():
    giocatori = _giocatori([100, 90, 80, 70, 60, 50, 40])  # 7 giocatori, dimensione 3 -> 2 squadre, 1 escluso
    squadre = genera_squadre_multiple(giocatori, dimensione=3)
    assert len(squadre) == 2
    assert sum(len(s) for s in squadre) == 6
    incluso = {gid for squadra in squadre for gid in squadra}
    escluso = {g.player_id for g in giocatori} - incluso
    assert len(escluso) == 1
    # il piu' debole (rk piu' basso, ultimo nella lista) e' quello escluso
    assert giocatori[-1].player_id in escluso


# --- genera_fixture_girone ----------------------------------------------------


def test_fixture_girone_numero_di_partite():
    assert len(genera_fixture_girone(4)) == 6  # C(4,2)
    assert len(genera_fixture_girone(3)) == 3  # C(3,2)


def test_fixture_girone_ogni_squadra_gioca_contro_tutte_le_altre():
    fixture = genera_fixture_girone(5)
    conteggio = dict.fromkeys(range(5), 0)
    for a, b in fixture:
        conteggio[a] += 1
        conteggio[b] += 1
    assert all(v == 4 for v in conteggio.values())  # n_squadre - 1
    assert len(set(fixture)) == len(fixture)  # nessuna coppia duplicata

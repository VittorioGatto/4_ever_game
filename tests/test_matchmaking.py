import pytest

from rokkini.matchmaking import GiocatorePerMatchmaking, genera_combinazioni_bilanciate


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

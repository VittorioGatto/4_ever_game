import pytest

from rokkini.elo import (
    PlayerPreMatch,
    compute_match_deltas,
    individual_correction,
    k_factor,
    round_half_away_from_zero,
    team_average,
    tier_for_rk,
    win_probability,
)


def test_k_factor_soglie():
    assert k_factor(0) == 50  # prima partita
    assert k_factor(4) == 50  # quinta partita
    assert k_factor(5) == 40  # sesta partita
    assert k_factor(13) == 40  # quattordicesima
    assert k_factor(14) == 32  # quindicesima
    assert k_factor(24) == 32  # venticinquesima
    assert k_factor(25) == 24  # ventiseiesima
    assert k_factor(39) == 24  # quarantesima
    assert k_factor(40) == 16  # quarantunesima
    assert k_factor(1000) == 16


def test_tier_for_rk():
    assert tier_for_rk(0) == "H"
    assert tier_for_rk(1199) == "H"
    assert tier_for_rk(1200) == "C"
    assert tier_for_rk(1499) == "C"
    assert tier_for_rk(1500) == "B"
    assert tier_for_rk(1799) == "B"
    assert tier_for_rk(1800) == "A"
    assert tier_for_rk(2500) == "A"


def test_round_half_away_from_zero():
    assert round_half_away_from_zero(15.36) == 15
    assert round_half_away_from_zero(18.72) == 19
    assert round_half_away_from_zero(-7.41) == -7
    assert round_half_away_from_zero(0.5) == 1
    assert round_half_away_from_zero(-0.5) == -1
    assert round_half_away_from_zero(2.5) == 3  # divergerebbe da banker's rounding (round(2.5)==2)


def test_win_probability_complementary():
    p_a = win_probability(1600, 1400)
    p_b = win_probability(1400, 1600)
    assert p_a > 0.5
    assert p_a + p_b == pytest.approx(1.0)


def test_individual_correction_clamped():
    assert individual_correction(1400, 1600) == pytest.approx(-0.20)
    assert individual_correction(1400, 1400) == pytest.approx(0.0)
    assert individual_correction(1400, 1200) == pytest.approx(0.20)
    # differenza enorme: il correttivo resta comunque clampato a +-0.20
    assert individual_correction(1000, 3000) == pytest.approx(-0.20)
    assert individual_correction(3000, 1000) == pytest.approx(0.20)


def test_regolamento_esempio_10_3():
    """Esempio del regolamento (sezione 10.3): squadra 1600/1400/1200 Rk,
    media 1400, vittoria con variazione base di circa +15 Rk per tutti
    (stesso K per i tre giocatori in questo esempio)."""
    team_avg = 1400
    delta_base = 15
    rk_values_and_expected = [(1600, 12), (1400, 15), (1200, 18)]
    for rk, expected_delta in rk_values_and_expected:
        c = individual_correction(team_avg, rk)
        delta_finale = round_half_away_from_zero(delta_base * (1 + c))
        assert delta_finale == expected_delta


def test_compute_match_deltas_winner_gains_loser_loses():
    team_a = [
        PlayerPreMatch(player_id=1, rk_before=1500, matches_played_before=10),
        PlayerPreMatch(player_id=2, rk_before=1450, matches_played_before=10),
        PlayerPreMatch(player_id=3, rk_before=1550, matches_played_before=10),
    ]
    team_b = [
        PlayerPreMatch(player_id=4, rk_before=1300, matches_played_before=10),
        PlayerPreMatch(player_id=5, rk_before=1250, matches_played_before=10),
        PlayerPreMatch(player_id=6, rk_before=1350, matches_played_before=10),
    ]
    deltas_a, deltas_b = compute_match_deltas(team_a, team_b, winner="A")

    assert all(d.esito == "vittoria" for d in deltas_a)
    assert all(d.esito == "sconfitta" for d in deltas_b)
    assert all(d.delta > 0 for d in deltas_a)
    assert all(d.delta < 0 for d in deltas_b)
    assert all(d.rk_dopo == d.rk_prima + d.delta for d in deltas_a + deltas_b)

    # la squadra favorita (A) vince: guadagno minore di quanto guadagnerebbe
    # una sfavorita che vince, perché P_a > 0.5
    for d in deltas_a:
        assert d.probabilita_teorica > 0.5


def test_compute_match_deltas_underdog_win_gains_more():
    favourite = [PlayerPreMatch(player_id=1, rk_before=1800, matches_played_before=10)]
    underdog = [PlayerPreMatch(player_id=2, rk_before=1200, matches_played_before=10)]
    # squadre da 1 giocatore solo per isolare l'effetto della probabilità,
    # senza correttivo individuale (team_avg == player_rk => C=0)
    _, deltas_underdog_win = compute_match_deltas(favourite, underdog, winner="B")
    assert deltas_underdog_win[0].delta > 16  # supera il guadagno "alla pari" (K=32 qui: 16)


def test_individual_correction_favours_weaker_teammate_on_loss():
    team_avg = 1400
    stronger_c = individual_correction(team_avg, 1600)
    weaker_c = individual_correction(team_avg, 1200)
    delta_base = -15
    stronger_loss = round_half_away_from_zero(delta_base * (1 - stronger_c))
    weaker_loss = round_half_away_from_zero(delta_base * (1 - weaker_c))
    # il piu' forte della squadra perde di piu' (valore piu' negativo)
    assert stronger_loss < weaker_loss


def test_team_average():
    players = [
        PlayerPreMatch(player_id=1, rk_before=1000, matches_played_before=0),
        PlayerPreMatch(player_id=2, rk_before=1200, matches_played_before=0),
        PlayerPreMatch(player_id=3, rk_before=1400, matches_played_before=0),
    ]
    assert team_average(players) == pytest.approx(1200.0)

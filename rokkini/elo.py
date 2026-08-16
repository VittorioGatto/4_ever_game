"""Motore di calcolo Rk (Elo). Funzioni pure: nessun I/O, nessuna dipendenza da Streamlit o DB.

Tutte le funzioni che dipendono dai parametri di calcolo (K-factor, fasce,
correttivo) li ricevono esplicitamente invece di leggerli da costanti
globali: cosi' rating_engine.simula_classifica puo' rigiocare lo storico con
parametri ipotetici diversi da quelli attivi, senza mutare stato condiviso
(pericoloso in un'app multi-utente come Streamlit)."""

import math
from dataclasses import dataclass
from typing import Literal

from rokkini.parametri import Parametri

Squadra = Literal["A", "B"]
Esito = Literal["vittoria", "sconfitta"]


@dataclass(frozen=True)
class PlayerPreMatch:
    player_id: int
    rk_before: int
    matches_played_before: int


@dataclass(frozen=True)
class PlayerDelta:
    player_id: int
    squadra: Squadra
    esito: Esito
    rk_prima: int
    k_usato: int
    probabilita_teorica: float
    correttivo_usato: float
    delta: int
    rk_dopo: int


def k_factor(matches_played: int, k_factor_soglie: list[tuple[int, int]]) -> int:
    for soglia, k in k_factor_soglie:
        if matches_played >= soglia:
            return k
    raise ValueError(f"matches_played negativo: {matches_played}")


def tier_for_rk(rk: int, fasce: list[tuple[int, str]]) -> str:
    for soglia, fascia in fasce:
        if rk >= soglia:
            return fascia
    raise AssertionError("le fasce devono coprire tutti i valori di rk")


def team_average(players: list[PlayerPreMatch]) -> float:
    return sum(p.rk_before for p in players) / len(players)


def win_probability(own_avg: float, opponent_avg: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent_avg - own_avg) / 400))


def individual_correction(
    teammates_avg: float,
    player_rk: int,
    correttivo_massimo: float,
    saturazione_sfavorito: int,
    saturazione_favorito: int,
) -> float:
    """C: confronta il Rk del giocatore con la media Rk dei SOLI compagni di
    squadra (se stesso escluso). D>0 (giocatore piu' debole dei compagni,
    "sfavorito") da' un correttivo positivo che satura a correttivo_massimo
    gia' a saturazione_sfavorito Rk di differenza; D<0 ("favorito") da' un
    correttivo negativo che satura solo a saturazione_favorito (tipicamente
    il doppio, quindi la penalita' del favorito cresce piu' lentamente del
    bonus dello sfavorito)."""
    d = teammates_avg - player_rk
    if d > 0:
        return min(d / saturazione_sfavorito * correttivo_massimo, correttivo_massimo)
    return -min(-d / saturazione_favorito * correttivo_massimo, correttivo_massimo)


def round_half_away_from_zero(x: float) -> int:
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def _team_deltas(
    team: list[PlayerPreMatch],
    team_avg: float,
    opponent_avg: float,
    esito: Esito,
    squadra: Squadra,
    parametri: Parametri,
) -> list[PlayerDelta]:
    p = win_probability(team_avg, opponent_avg)
    s = 1.0 if esito == "vittoria" else 0.0
    somma_squadra = sum(pl.rk_before for pl in team)
    deltas = []
    for player in team:
        k = k_factor(player.matches_played_before, parametri.k_factor_soglie)
        delta_base = k * (s - p)
        if len(team) > 1:
            media_compagni = (somma_squadra - player.rk_before) / (len(team) - 1)
            c = individual_correction(
                media_compagni,
                player.rk_before,
                parametri.correttivo_massimo,
                parametri.correttivo_saturazione_sfavorito,
                parametri.correttivo_saturazione_favorito,
            )
        else:
            c = 0.0  # nessun compagno con cui confrontarsi
        delta_finale = delta_base * (1 + c) if esito == "vittoria" else delta_base * (1 - c)
        delta_arrotondato = round_half_away_from_zero(delta_finale)
        deltas.append(
            PlayerDelta(
                player_id=player.player_id,
                squadra=squadra,
                esito=esito,
                rk_prima=player.rk_before,
                k_usato=k,
                probabilita_teorica=p,
                correttivo_usato=c,
                delta=delta_arrotondato,
                rk_dopo=player.rk_before + delta_arrotondato,
            )
        )
    return deltas


def compute_match_deltas(
    team_a: list[PlayerPreMatch],
    team_b: list[PlayerPreMatch],
    winner: Squadra,
    parametri: Parametri,
) -> tuple[list[PlayerDelta], list[PlayerDelta]]:
    """Calcola i delta Rk per entrambe le squadre.

    Unica fonte di verità per il calcolo: usata sia per registrare una
    partita nuova sia dentro rating_engine.recompute_all/simula_classifica,
    così normale registrazione, ricalcolo e simulazione non possono
    divergere.
    """
    avg_a = team_average(team_a)
    avg_b = team_average(team_b)
    esito_a: Esito = "vittoria" if winner == "A" else "sconfitta"
    esito_b: Esito = "vittoria" if winner == "B" else "sconfitta"
    deltas_a = _team_deltas(team_a, avg_a, avg_b, esito_a, "A", parametri)
    deltas_b = _team_deltas(team_b, avg_b, avg_a, esito_b, "B", parametri)
    return deltas_a, deltas_b

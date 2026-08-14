"""Suggerimento di squadre bilanciate per il matchmaking di una sessione di
gioco. Funzioni pure, nessun I/O: stesso stile di rokkini/elo.py."""

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class GiocatorePerMatchmaking:
    player_id: int
    rk_attuale: int


@dataclass(frozen=True)
class PropostaSquadre:
    squadra_a: list[int]
    squadra_b: list[int]
    media_a: float
    media_b: float

    @property
    def differenza(self) -> float:
        return abs(self.media_a - self.media_b)


def genera_combinazioni_bilanciate(
    giocatori: list[GiocatorePerMatchmaking],
    dimensione: int,
    n_proposte: int = 3,
) -> list[PropostaSquadre]:
    """Enumera tutte le divisioni uniche di `giocatori` in due squadre da
    `dimensione` giocatori ciascuna, ordinate per differenza di Rk medio
    crescente, e restituisce le migliori `n_proposte`.

    `giocatori` deve contenere esattamente 2*dimensione elementi. Il primo
    elemento è sempre assegnato alla squadra A: la differenza di Rk medio è
    simmetrica rispetto allo scambio A/B, quindi senza questo vincolo ogni
    split verrebbe contato (e proposto) due volte con le etichette scambiate.

    Enumerazione esaustiva (10 split unici per 3v3, 35 per 4v4): a questa
    scala è istantanea ed è corretta per costruzione, senza bisogno di una
    euristica di ottimizzazione — stessa filosofia di rating_engine.recompute_all.
    """
    attesi = dimensione * 2
    if len(giocatori) != attesi:
        raise ValueError(
            f"Servono esattamente {attesi} giocatori per generare squadre da {dimensione} "
            f"(ricevuti {len(giocatori)})"
        )

    primo, *resto = range(len(giocatori))

    proposte = []
    for combo in combinations(resto, dimensione - 1):
        indici_a = {primo, *combo}
        squadra_a = [giocatori[i] for i in range(len(giocatori)) if i in indici_a]
        squadra_b = [giocatori[i] for i in range(len(giocatori)) if i not in indici_a]
        media_a = sum(g.rk_attuale for g in squadra_a) / dimensione
        media_b = sum(g.rk_attuale for g in squadra_b) / dimensione
        proposte.append(
            PropostaSquadre(
                squadra_a=[g.player_id for g in squadra_a],
                squadra_b=[g.player_id for g in squadra_b],
                media_a=media_a,
                media_b=media_b,
            )
        )

    proposte.sort(key=lambda p: p.differenza)
    return proposte[:n_proposte]

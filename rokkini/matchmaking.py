"""Suggerimento di squadre bilanciate per il matchmaking di una sessione di
gioco. Funzioni pure, nessun I/O: stesso stile di rokkini/elo.py."""

from dataclasses import dataclass
from itertools import combinations
from math import gcd


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


def genera_squadre_multiple(
    giocatori: list[GiocatorePerMatchmaking], dimensione: int
) -> list[list[int]]:
    """Divide i giocatori in squadre da `dimensione` con un draft a
    serpentina: ordina per Rk decrescente e distribuisce un giro alla volta
    nell'ordine 1,2,...,N,N,...,2,1 (alternando direzione). Bilancia bene
    senza l'esplosione combinatoria dell'enumerazione esaustiva usata da
    genera_combinazioni_bilanciate, che non scala oltre 2 squadre.

    Se il numero di giocatori non è multiplo di `dimensione`, i più deboli in
    eccesso restano fuori da questo turno (non entrano in nessuna squadra).
    Richiede almeno 2*dimensione giocatori (altrimenti non si formano nemmeno
    due squadre)."""
    n_squadre = len(giocatori) // dimensione
    if n_squadre < 2:
        raise ValueError(
            f"Servono almeno {dimensione * 2} giocatori per formare 2 squadre da "
            f"{dimensione} (ricevuti {len(giocatori)})"
        )

    ordinati = sorted(giocatori, key=lambda g: g.rk_attuale, reverse=True)
    utilizzati = ordinati[: n_squadre * dimensione]

    squadre: list[list[int]] = [[] for _ in range(n_squadre)]
    ordine = list(range(n_squadre))
    for giro in range(dimensione):
        sequenza = ordine if giro % 2 == 0 else list(reversed(ordine))
        for posizione, squadra_idx in enumerate(sequenza):
            giocatore = utilizzati[giro * n_squadre + posizione]
            squadre[squadra_idx].append(giocatore.player_id)
    return squadre


def genera_fixture_girone(n_squadre: int) -> list[tuple[int, int]]:
    """Tutte le coppie possibili tra `n_squadre` squadre (indicizzate da 0):
    un girone all'italiana a gruppo unico, ogni squadra incontra ogni altra
    esattamente una volta."""
    return list(combinations(range(n_squadre), 2))


def numero_partite_per_girone_equo(n_giocatori: int, dimensione: int) -> int:
    """Quando `n_giocatori` non è multiplo di `dimensione` non si possono
    formare squadre fisse senza escludere qualcuno per l'intero girone: le
    squadre vanno ricomposte partita per partita (vedi
    prossima_partita_girone_rotante). Questa funzione calcola il numero
    minimo di partite necessarie perché ognuno ne giochi esattamente lo
    stesso numero, dato che ogni partita occupa 2*dimensione posti: il
    minimo comune multiplo di n_giocatori e 2*dimensione, diviso per
    2*dimensione — equivalentemente n_giocatori / mcd(n_giocatori, 2*dimensione).
    Se n_giocatori è già multiplo di dimensione, coincide con le partite del
    girone a squadre fisse (es. 9 giocatori, dimensione 3 → 3 partite, come
    genera_fixture_girone(3))."""
    return n_giocatori // gcd(n_giocatori, dimensione * 2)


def prossima_partita_girone_rotante(
    giocatori: list[GiocatorePerMatchmaking],
    dimensione: int,
    conteggio_partite: dict[int, int],
) -> tuple[list[int], list[int]]:
    """Sceglie i 2*dimensione giocatori che hanno giocato meno partite finora
    in questo girone (a parità, nell'ordine di `giocatori`) e li divide nelle
    due squadre più bilanciate possibile. Usata quando il numero di
    giocatori presenti non è multiplo di `dimensione`: dando sempre priorità
    a chi ha giocato meno, dopo numero_partite_per_girone_equo(...) partite
    tutti ne hanno giocate esattamente lo stesso numero."""
    attesi = dimensione * 2
    if len(giocatori) < attesi:
        raise ValueError(
            f"Servono almeno {attesi} giocatori per una partita da {dimensione} "
            f"(ricevuti {len(giocatori)})"
        )
    ordinati = sorted(giocatori, key=lambda g: conteggio_partite.get(g.player_id, 0))
    selezionati = ordinati[:attesi]
    proposta = genera_combinazioni_bilanciate(selezionati, dimensione, n_proposte=1)[0]
    return proposta.squadra_a, proposta.squadra_b


def programma_completo_girone_rotante(
    giocatori: list[GiocatorePerMatchmaking],
    dimensione: int,
    conteggio_iniziale: dict[int, int],
    n_partite: int,
) -> list[tuple[list[int], list[int]]]:
    """Proietta in anticipo le prossime `n_partite` del girone a rotazione,
    applicando ripetutamente prossima_partita_girone_rotante a partire da
    `conteggio_iniziale` e aggiornando via via una copia locale del
    conteggio. E' una previsione, non un impegno: se il pool di presenti
    cambia o una partita viene modificata a mano prima di essere
    confermata, l'esito reale puo' discostarsi da qui in poi — motivo per
    cui non e' persistita come fixture fissa, solo mostrata come proposta."""
    conteggio = dict(conteggio_iniziale)
    programma = []
    for _ in range(n_partite):
        squadra_a, squadra_b = prossima_partita_girone_rotante(giocatori, dimensione, conteggio)
        programma.append((squadra_a, squadra_b))
        for gid in squadra_a + squadra_b:
            conteggio[gid] = conteggio.get(gid, 0) + 1
    return programma

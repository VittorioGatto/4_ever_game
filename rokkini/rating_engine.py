"""Orchestrazione: registrare/annullare/correggere partite e ricalcolare i Rk.

register_match / void_match / edit_match condividono tutti lo stesso
percorso finale (recompute_all) invece di avere una scorciatoia "applica
solo il delta della nuova partita": non esiste quindi una seconda
implementazione del calcolo da tenere sincronizzata con quella usata per il
ricalcolo dopo un annullamento.
"""

from rokkini import db
from rokkini.constants import PARTITE_QUALIFICAZIONE, RK_INIZIALE
from rokkini.elo import PlayerDelta, PlayerPreMatch, compute_match_deltas, tier_for_rk


class GiocatoreState:
    __slots__ = (
        "partite_giocate",
        "qualificato",
        "rk",
        "rk_record",
        "sconfitte",
        "streak_vittorie_corrente",
        "streak_vittorie_record",
        "vittorie",
    )

    def __init__(self) -> None:
        self.rk = RK_INIZIALE
        self.partite_giocate = 0
        self.vittorie = 0
        self.sconfitte = 0
        self.qualificato = False
        self.rk_record = RK_INIZIALE
        self.streak_vittorie_corrente = 0
        self.streak_vittorie_record = 0

    def applica(self, delta: PlayerDelta) -> None:
        self.rk = delta.rk_dopo
        self.partite_giocate += 1
        self.rk_record = max(self.rk_record, self.rk)
        if delta.esito == "vittoria":
            self.vittorie += 1
            self.streak_vittorie_corrente += 1
            self.streak_vittorie_record = max(
                self.streak_vittorie_record, self.streak_vittorie_corrente
            )
        else:
            self.sconfitte += 1
            self.streak_vittorie_corrente = 0
        if self.partite_giocate >= PARTITE_QUALIFICAZIONE:
            self.qualificato = True


def _validate_squadre(modalita: str, squadra_a: list[int], squadra_b: list[int]) -> None:
    dimensione_attesa = 3 if modalita == "3v3" else 4
    if len(squadra_a) != dimensione_attesa or len(squadra_b) != dimensione_attesa:
        raise ValueError(f"La modalita' {modalita} richiede {dimensione_attesa} giocatori a squadra")
    if set(squadra_a) & set(squadra_b):
        raise ValueError("Un giocatore non puo' essere in entrambe le squadre")
    if len(set(squadra_a)) != len(squadra_a) or len(set(squadra_b)) != len(squadra_b):
        raise ValueError("Giocatori duplicati nella stessa squadra")


def register_match(
    conn,
    data_partita: str,
    modalita: str,
    risultato_set: str,
    squadra_vincente: str,
    squadra_a: list[int],
    squadra_b: list[int],
    registered_by: int,
    sessione_id: int | None = None,
) -> int:
    _validate_squadre(modalita, squadra_a, squadra_b)
    try:
        partita_id = db.insert_partita(
            conn,
            data_partita,
            modalita,
            risultato_set,
            squadra_vincente,
            registered_by,
            sessione_id=sessione_id,
        )
        db.insert_partecipazioni_bulk(
            conn,
            [(partita_id, gid, "A") for gid in squadra_a]
            + [(partita_id, gid, "B") for gid in squadra_b],
        )
        recompute_all(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return partita_id


def void_match(conn, partita_id: int, voided_by: int, reason: str) -> None:
    try:
        db.void_partita_row(conn, partita_id, voided_by, reason)
        recompute_all(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def edit_match(
    conn,
    partita_id: int,
    modalita: str,
    risultato_set: str,
    squadra_vincente: str,
    squadra_a: list[int],
    squadra_b: list[int],
    edited_by: int,
) -> int:
    """Annulla la partita originale e ne inserisce una nuova con la stessa
    data (stessa posizione cronologica); replaces_match_id traccia il
    collegamento. Non e' possibile cambiare la data da questa funzione."""
    _validate_squadre(modalita, squadra_a, squadra_b)
    try:
        originale = db.fetch_partita(conn, partita_id)
        if originale is None:
            raise ValueError(f"Partita {partita_id} non trovata")
        db.void_partita_row(conn, partita_id, edited_by, "corretta")
        nuova_id = db.insert_partita(
            conn,
            originale["data_partita"],
            modalita,
            risultato_set,
            squadra_vincente,
            edited_by,
            replaces_match_id=partita_id,
            sessione_id=originale["sessione_id"],
        )
        db.insert_partecipazioni_bulk(
            conn,
            [(nuova_id, gid, "A") for gid in squadra_a] + [(nuova_id, gid, "B") for gid in squadra_b],
        )
        recompute_all(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return nuova_id


def recompute_all(conn) -> None:
    """Ricalcola da zero l'intero storico non annullato, in ordine
    cronologico, e riscrive giocatori/variazioni_rk/ranking_leader_log.

    Approccio a replay completo, non calcolo incrementale del sottografo
    "affetto" da una modifica: alla scala di un gruppo di amici il replay e'
    computazionalmente banale ed e' corretto per costruzione, perche' non
    esiste logica separata su "quali partite sono affette" che possa avere
    bug — l'algoritmo rigioca semplicemente tutta la storia. Le letture e
    scritture verso il DB sono pero' raggruppate in poche query invece di
    una per partita/variazione: con Turso ogni query e' un round trip di
    rete, e uno storico di centinaia di partite renderebbe altrimenti
    questa funzione (richiamata a ogni registrazione/annullamento/
    correzione) lenta in modo percepibile."""
    giocatori = db.fetch_giocatori(conn)
    stato: dict[int, GiocatoreState] = {g["id"]: GiocatoreState() for g in giocatori}
    sospeso_map = {g["id"]: bool(g["sospeso"]) for g in giocatori}

    db.delete_tutte_variazioni_e_leader_log(conn)

    partecipazioni_per_partita = db.fetch_tutte_partecipazioni_non_annullate(conn)
    righe_variazioni: list[tuple] = []

    leader_corrente: int | None = None
    for partita in db.fetch_partite_non_annullate(conn):
        partecipazioni = partecipazioni_per_partita.get(partita["id"], [])
        squadra_a_ids = [p["giocatore_id"] for p in partecipazioni if p["squadra"] == "A"]
        squadra_b_ids = [p["giocatore_id"] for p in partecipazioni if p["squadra"] == "B"]

        team_a = [
            PlayerPreMatch(gid, stato[gid].rk, stato[gid].partite_giocate)
            for gid in squadra_a_ids
        ]
        team_b = [
            PlayerPreMatch(gid, stato[gid].rk, stato[gid].partite_giocate)
            for gid in squadra_b_ids
        ]
        deltas_a, deltas_b = compute_match_deltas(team_a, team_b, partita["squadra_vincente"])

        for delta in deltas_a + deltas_b:
            stato[delta.player_id].applica(delta)
            righe_variazioni.append(
                (
                    partita["id"],
                    delta.player_id,
                    delta.squadra,
                    delta.esito,
                    delta.rk_prima,
                    delta.k_usato,
                    delta.probabilita_teorica,
                    delta.correttivo_usato,
                    delta.delta,
                    delta.rk_dopo,
                )
            )

        leader_corrente = _aggiorna_leader_log(
            conn, stato, sospeso_map, leader_corrente, partita["data_partita"]
        )

    db.insert_variazioni_bulk(conn, righe_variazioni)

    for giocatore_id, s in stato.items():
        db.update_giocatore_stato(
            conn,
            giocatore_id,
            rk_attuale=s.rk,
            partite_giocate=s.partite_giocate,
            vittorie=s.vittorie,
            sconfitte=s.sconfitte,
            qualificato=int(s.qualificato),
            fascia_attuale=tier_for_rk(s.rk),
            rk_record=s.rk_record,
            streak_vittorie_corrente=s.streak_vittorie_corrente,
            streak_vittorie_record=s.streak_vittorie_record,
        )


def _aggiorna_leader_log(
    conn,
    stato: dict[int, GiocatoreState],
    sospeso_map: dict[int, bool],
    leader_corrente: int | None,
    data_partita: str,
) -> int | None:
    candidati = [
        (giocatore_id, s.rk)
        for giocatore_id, s in stato.items()
        if s.qualificato and not sospeso_map.get(giocatore_id, False)
    ]
    if not candidati:
        return leader_corrente
    nuovo_leader = max(candidati, key=lambda item: item[1])[0]
    if nuovo_leader != leader_corrente:
        if leader_corrente is not None:
            db.close_open_leader_logs(conn, data_partita)
        db.insert_leader_log(conn, nuovo_leader, data_partita)
        return nuovo_leader
    return leader_corrente

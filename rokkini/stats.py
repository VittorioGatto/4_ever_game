"""Query di lettura per classifica, profili, storico e record. Restituiscono
polars DataFrame o dict pronti per la UI Streamlit."""

from typing import Any

import polars as pl

from rokkini import db
from rokkini.constants import RK_INIZIALE


def _con_percentuale_vittorie(giocatori: list[dict[str, Any]]) -> list[dict[str, Any]]:
    arricchiti = []
    for g in giocatori:
        percentuale = (g["vittorie"] / g["partite_giocate"] * 100) if g["partite_giocate"] else 0.0
        arricchiti.append({**g, "percentuale_vittorie": round(percentuale, 1)})
    return arricchiti


def fetch_ranking(conn, fascia: str | None = None) -> pl.DataFrame:
    giocatori = [
        g for g in db.fetch_giocatori(conn) if g["qualificato"] and not g["sospeso"]
    ]
    giocatori.sort(key=lambda g: g["rk_attuale"], reverse=True)
    if fascia and fascia != "Tutti":
        giocatori = [g for g in giocatori if g["fascia_attuale"] == fascia]
    arricchiti = _con_percentuale_vittorie(giocatori)
    for posizione, g in enumerate(arricchiti, start=1):
        g["posizione"] = posizione
    if not arricchiti:
        return pl.DataFrame(
            schema={
                "posizione": pl.Int64,
                "nome": pl.Utf8,
                "rk_attuale": pl.Int64,
                "fascia_attuale": pl.Utf8,
                "partite_giocate": pl.Int64,
                "vittorie": pl.Int64,
                "sconfitte": pl.Int64,
                "percentuale_vittorie": pl.Float64,
            }
        )
    colonne = [
        "posizione",
        "nome",
        "rk_attuale",
        "fascia_attuale",
        "partite_giocate",
        "vittorie",
        "sconfitte",
        "percentuale_vittorie",
    ]
    return pl.DataFrame(arricchiti).select(colonne)


def fetch_in_qualificazione(conn) -> pl.DataFrame:
    giocatori = [
        g for g in db.fetch_giocatori(conn) if not g["qualificato"] and not g["sospeso"]
    ]
    giocatori.sort(key=lambda g: g["rk_attuale"], reverse=True)
    arricchiti = _con_percentuale_vittorie(giocatori)
    if not arricchiti:
        return pl.DataFrame(
            schema={
                "nome": pl.Utf8,
                "rk_attuale": pl.Int64,
                "partite_giocate": pl.Int64,
                "vittorie": pl.Int64,
                "sconfitte": pl.Int64,
            }
        )
    colonne = ["nome", "rk_attuale", "partite_giocate", "vittorie", "sconfitte"]
    return pl.DataFrame(arricchiti).select(colonne)


def fetch_player_profile(conn, giocatore_id: int) -> dict[str, Any] | None:
    giocatore = db.fetch_giocatore(conn, giocatore_id)
    if giocatore is None:
        return None
    ranking = fetch_ranking(conn)
    posizione_rows = ranking.filter(pl.col("nome") == giocatore["nome"])
    posizione = int(posizione_rows["posizione"][0]) if posizione_rows.height else None

    variazioni = db.fetch_variazioni_per_giocatore(conn, giocatore_id)
    punti_storico = [{"partita_numero": 0, "rk": RK_INIZIALE}]
    for i, v in enumerate(variazioni, start=1):
        punti_storico.append({"partita_numero": i, "rk": v["rk_dopo"]})
    storico_rk = pl.DataFrame(punti_storico)

    percentuale = (
        (giocatore["vittorie"] / giocatore["partite_giocate"] * 100)
        if giocatore["partite_giocate"]
        else 0.0
    )
    return {
        "giocatore": giocatore,
        "posizione": posizione,
        "percentuale_vittorie": round(percentuale, 1),
        "storico_rk": storico_rk,
    }


def _costruisci_cronologia(conn, partite: list[dict[str, Any]]) -> list[dict[str, Any]]:
    giocatori_per_id = {g["id"]: g["nome"] for g in db.fetch_giocatori(conn)}
    cronologia = []
    for partita in partite:
        variazioni = db.fetch_variazioni_per_partita(conn, partita["id"])
        squadra_a = [
            {"nome": giocatori_per_id.get(v["giocatore_id"], "?"), "delta": v["delta"]}
            for v in variazioni
            if v["squadra"] == "A"
        ]
        squadra_b = [
            {"nome": giocatori_per_id.get(v["giocatore_id"], "?"), "delta": v["delta"]}
            for v in variazioni
            if v["squadra"] == "B"
        ]
        cronologia.append({"partita": partita, "squadra_a": squadra_a, "squadra_b": squadra_b})
    return cronologia


def fetch_match_history(conn) -> list[dict[str, Any]]:
    return _costruisci_cronologia(conn, db.fetch_partite_tutte(conn))


def fetch_match_history_sessione(conn, sessione_id: int) -> list[dict[str, Any]]:
    return _costruisci_cronologia(conn, db.fetch_partite_di_sessione(conn, sessione_id))


def fetch_classifica_sessione(conn, sessione_id: int) -> list[dict[str, Any]]:
    """Somma i delta Rk per giocatore sulle partite non annullate di questa
    sessione, unita al Rk totale attuale di ciascuno. Ordinata per Rk
    guadagnati nella sessione, decrescente."""
    partite = db.fetch_partite_di_sessione(conn, sessione_id)  # gia' esclude le annullate
    giocatori_per_id = {g["id"]: g for g in db.fetch_giocatori(conn)}
    somma_per_giocatore: dict[int, int] = {}
    for partita in partite:
        for v in db.fetch_variazioni_per_partita(conn, partita["id"]):
            somma_per_giocatore[v["giocatore_id"]] = (
                somma_per_giocatore.get(v["giocatore_id"], 0) + v["delta"]
            )
    classifica = [
        {
            "nome": giocatori_per_id[gid]["nome"],
            "rk_sessione": somma,
            "rk_totale": giocatori_per_id[gid]["rk_attuale"],
        }
        for gid, somma in somma_per_giocatore.items()
        if gid in giocatori_per_id
    ]
    classifica.sort(key=lambda r: r["rk_sessione"], reverse=True)
    return classifica


def fetch_records(conn) -> dict[str, Any]:
    giocatori = db.fetch_giocatori(conn)
    giorni_al_numero_1 = {
        r["giocatore_id"]: r["giorni"] for r in db.fetch_giorni_al_numero_1(conn)
    }
    giocatori_per_id = {g["id"]: g for g in giocatori}

    def top(chiave: str) -> dict[str, Any] | None:
        candidati = [g for g in giocatori if g[chiave] > 0] if chiave != "rk_record" else giocatori
        if not candidati:
            return None
        migliore = max(candidati, key=lambda g: g[chiave])
        return {"nome": migliore["nome"], "valore": migliore[chiave]}

    giorni_top = None
    if giorni_al_numero_1:
        giocatore_id_top = max(giorni_al_numero_1, key=lambda gid: giorni_al_numero_1[gid])
        giocatore = giocatori_per_id.get(giocatore_id_top)
        if giocatore:
            giorni_top = {
                "nome": giocatore["nome"],
                "valore": round(giorni_al_numero_1[giocatore_id_top], 1),
            }

    return {
        "rk_piu_alto": top("rk_record"),
        "piu_partite": top("partite_giocate"),
        "piu_vittorie": top("vittorie"),
        "serie_vittorie": top("streak_vittorie_record"),
        "giorni_al_numero_1": giorni_top,
    }

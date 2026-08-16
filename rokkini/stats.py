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


def fetch_match_history_per_giorno(conn) -> list[dict[str, Any]]:
    """Storico raggruppato per giorno (data_partita), i giorni piu' recenti
    prima: per ciascuno, le partite di quel giorno (incluse quelle
    annullate, per trasparenza) e la classifica giornaliera — somma dei
    delta Rk di quel giorno per giocatore, ordinata decrescente. Le
    partite annullate non hanno variazioni_rk (rating_engine.recompute_all
    le esclude dal replay), quindi non contribuiscono alla somma."""
    giorni: dict[str, list[dict[str, Any]]] = {}
    for voce in fetch_match_history(conn):
        giorni.setdefault(voce["partita"]["data_partita"], []).append(voce)

    risultato = []
    for data in sorted(giorni.keys(), reverse=True):
        voci_giorno = giorni[data]
        somma_per_giocatore: dict[str, int] = {}
        for voce in voci_giorno:
            for g in voce["squadra_a"] + voce["squadra_b"]:
                somma_per_giocatore[g["nome"]] = somma_per_giocatore.get(g["nome"], 0) + g["delta"]
        classifica_giorno = sorted(
            (
                {"nome": nome, "rk_giorno": somma}
                for nome, somma in somma_per_giocatore.items()
            ),
            key=lambda r: r["rk_giorno"],
            reverse=True,
        )
        risultato.append({"data": data, "partite": voci_giorno, "classifica": classifica_giorno})
    return risultato


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


def fetch_record_stupidi(conn) -> dict[str, Any]:
    """Record scherzosi, calcolati sull'intero storico delle variazioni Rk
    invece che sulle colonne aggregate di giocatori (che tengono solo il
    meglio, es. la striscia di vittorie: qui serve anche il "peggio", tipo
    la serie di sconfitte piu' lunga)."""
    nome_per_id = {g["id"]: g["nome"] for g in db.fetch_giocatori(conn)}
    variazioni = db.fetch_tutte_variazioni(conn)
    vittorie = [v for v in variazioni if v["esito"] == "vittoria"]
    sconfitte = [v for v in variazioni if v["esito"] == "sconfitta"]

    rimonta = max(vittorie, key=lambda v: v["delta"]) if vittorie else None
    sorpresa = min(vittorie, key=lambda v: v["probabilita_teorica"]) if vittorie else None
    tonfo = min(sconfitte, key=lambda v: v["delta"]) if sconfitte else None

    peggior_striscia: dict[str, Any] | None = None
    for giocatore_id, nome in nome_per_id.items():
        corrente = 0
        massimo = 0
        for v in variazioni:
            if v["giocatore_id"] != giocatore_id:
                continue
            if v["esito"] == "sconfitta":
                corrente += 1
                massimo = max(massimo, corrente)
            else:
                corrente = 0
        if massimo > 0 and (peggior_striscia is None or massimo > peggior_striscia["valore"]):
            peggior_striscia = {"nome": nome, "valore": massimo}

    conteggio_giorno: dict[tuple[int, str], int] = {}
    for v in variazioni:
        chiave = (v["giocatore_id"], v["data_partita"])
        conteggio_giorno[chiave] = conteggio_giorno.get(chiave, 0) + 1
    giornata_intensa = None
    if conteggio_giorno:
        (giocatore_id, _data), n = max(conteggio_giorno.items(), key=lambda kv: kv[1])
        giornata_intensa = {"nome": nome_per_id[giocatore_id], "valore": n}

    return {
        "rimonta_clamorosa": (
            {"nome": nome_per_id[rimonta["giocatore_id"]], "valore": rimonta["delta"]}
            if rimonta
            else None
        ),
        "sorpresa_piu_grande": (
            {
                "nome": nome_per_id[sorpresa["giocatore_id"]],
                "valore": round(sorpresa["probabilita_teorica"] * 100, 1),
            }
            if sorpresa
            else None
        ),
        "tonfo_doloroso": (
            {"nome": nome_per_id[tonfo["giocatore_id"]], "valore": tonfo["delta"]}
            if tonfo
            else None
        ),
        "serie_sconfitte": peggior_striscia,
        "giornata_intensa": giornata_intensa,
    }

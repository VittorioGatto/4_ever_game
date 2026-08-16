"""Esportazione/importazione dei dati (backup e restore).

export_data/import_data: dump JSON completo di tutte le tabelle (incluse le
password bcrypt), per un ripristino byte-per-byte. export_giocatori_csv/
export_partite_csv/import_csv: la coppia di file CSV usata dalla pagina di
backup, pensata per restare valida anche se la logica di calcolo dei punti
cambia (vedi commento piu' sotto). In entrambi i casi l'import sostituisce
lo storico esistente: non e' un merge.
"""

from datetime import datetime
from typing import Any

from rokkini import db, rating_engine

VERSIONE_FORMATO = 1

# Ordine valido per gli INSERT (rispetta le foreign key: ogni tabella
# referenzia solo tabelle che la precedono). Il DELETE in fase di import usa
# l'ordine inverso, cosi' cancella prima le tabelle "figlie". sessioni_gioco
# e sessione_partecipanti devono esserci: partite.sessione_id le referenzia,
# e senza di loro un import (specie su un DB diverso da quello di origine,
# lo scopo stesso del backup) fallisce con FOREIGN KEY constraint failed
# appena una partita importata fa riferimento a una sessione mai ripristinata.
TABELLE: tuple[str, ...] = (
    "giocatori",
    "utenti",
    "sessioni_gioco",
    "partite",
    "sessione_partecipanti",
    "partecipazioni_partita",
    "variazioni_rk",
    "ranking_leader_log",
)


def export_data(conn) -> dict[str, Any]:
    tabelle = {}
    for nome_tabella in TABELLE:
        cur = conn.execute(f"SELECT * FROM {nome_tabella}")
        tabelle[nome_tabella] = db.rows_as_dicts(cur)
    return {"versione": VERSIONE_FORMATO, "tabelle": tabelle}


# --- export/import in 2 file CSV (partite + Rk dei giocatori) ---------------
#
# A differenza di export_data/import_data (dump grezzo di tutte le tabelle,
# pensato per un ripristino byte-per-byte), questa coppia di file e' pensata
# per restare leggibile e utile anche se in futuro cambia la logica di
# calcolo dei punti (K-factor, soglie di qualificazione, ecc.): un file
# contiene lo storico delle partite (chi ha giocato contro chi, chi ha
# vinto), l'altro il Rk "ufficiale" di ogni giocatore nel momento
# dell'esportazione. Al ripristino, i valori del file giocatori sono quelli
# che contano: le partite vengono rigiocate con recompute_all per ricostruire
# uno storico coerente (utile per la pagina Storico), ma se la logica di
# calcolo e' cambiata nel frattempo il replay puo' produrre numeri diversi da
# quelli originali, quindi il Rk "attuale" di ogni giocatore viene
# risovrascritto con lo snapshot congelato del file giocatori.
COLONNE_GIOCATORI_CSV: tuple[str, ...] = (
    "nome",
    "rk_attuale",
    "partite_giocate",
    "vittorie",
    "sconfitte",
    "fascia_attuale",
    "qualificato",
    "rk_record",
    "streak_vittorie_corrente",
    "streak_vittorie_record",
    "data_esportazione",
)

COLONNE_PARTITE_CSV: tuple[str, ...] = (
    "data_partita",
    "modalita",
    "risultato_set",
    "squadra_vincente",
    "squadra_a",
    "squadra_b",
    "data_esportazione",
)

_SEPARATORE_NOMI = ";"


def export_giocatori_csv(conn) -> list[dict[str, Any]]:
    data_esportazione = datetime.now().isoformat(timespec="seconds")
    righe = []
    for g in db.fetch_giocatori(conn):
        righe.append({colonna: g[colonna] for colonna in COLONNE_GIOCATORI_CSV if colonna != "data_esportazione"})
        righe[-1]["data_esportazione"] = data_esportazione
    return righe


def export_partite_csv(conn) -> list[dict[str, Any]]:
    """Solo le partite non annullate: quelle corrette/annullate non vanno
    riproposte in un ripristino."""
    data_esportazione = datetime.now().isoformat(timespec="seconds")
    nome_per_id = {g["id"]: g["nome"] for g in db.fetch_giocatori(conn)}
    partecipazioni_per_partita = db.fetch_tutte_partecipazioni_non_annullate(conn)

    righe = []
    for partita in db.fetch_partite_non_annullate(conn):
        partecipazioni = partecipazioni_per_partita.get(partita["id"], [])
        squadra_a = [nome_per_id[p["giocatore_id"]] for p in partecipazioni if p["squadra"] == "A"]
        squadra_b = [nome_per_id[p["giocatore_id"]] for p in partecipazioni if p["squadra"] == "B"]
        righe.append(
            {
                "data_partita": partita["data_partita"],
                "modalita": partita["modalita"],
                "risultato_set": partita["risultato_set"],
                "squadra_vincente": partita["squadra_vincente"],
                "squadra_a": _SEPARATORE_NOMI.join(squadra_a),
                "squadra_b": _SEPARATORE_NOMI.join(squadra_b),
                "data_esportazione": data_esportazione,
            }
        )
    return righe


def import_csv(conn, righe_giocatori: list[dict[str, Any]], righe_partite: list[dict[str, Any]], registered_by: int) -> None:
    """Ripristina lo stato da una coppia di file esportati con
    export_giocatori_csv/export_partite_csv. Sostituisce interamente lo
    storico partite (stesso comportamento "non e' un merge" di import_data)
    e riporta ogni giocatore al Rk congelato nel file, indipendentemente da
    quello che il replay delle partite ricalcolerebbe con la logica attuale."""
    try:
        for nome_tabella in TABELLE_STORICO:
            conn.execute(f"DELETE FROM {nome_tabella}")
        conn.execute(
            """UPDATE giocatori SET
                rk_attuale = 1000,
                partite_giocate = 0,
                vittorie = 0,
                sconfitte = 0,
                fascia_attuale = 'H',
                qualificato = 0,
                rk_record = 1000,
                streak_vittorie_corrente = 0,
                streak_vittorie_record = 0"""
        )

        id_per_nome = {g["nome"]: g["id"] for g in db.fetch_giocatori(conn)}
        for riga in righe_giocatori:
            nome = riga["nome"]
            if nome not in id_per_nome:
                id_per_nome[nome] = db.insert_giocatore(conn, nome)

        for riga in righe_partite:
            squadra_a_ids = [id_per_nome[nome] for nome in riga["squadra_a"].split(_SEPARATORE_NOMI) if nome]
            squadra_b_ids = [id_per_nome[nome] for nome in riga["squadra_b"].split(_SEPARATORE_NOMI) if nome]
            partita_id = db.insert_partita(
                conn,
                riga["data_partita"],
                riga["modalita"],
                riga["risultato_set"],
                riga["squadra_vincente"],
                registered_by,
            )
            db.insert_partecipazioni_bulk(
                conn,
                [(partita_id, gid, "A") for gid in squadra_a_ids]
                + [(partita_id, gid, "B") for gid in squadra_b_ids],
            )

        rating_engine.recompute_all(conn)

        # Il Rk "ufficiale" resta quello congelato nel file, non quello appena
        # ricalcolato dal replay (vedi commento in testa a questa sezione).
        for riga in righe_giocatori:
            db.update_giocatore_stato(
                conn,
                id_per_nome[riga["nome"]],
                rk_attuale=int(riga["rk_attuale"]),
                partite_giocate=int(riga["partite_giocate"]),
                vittorie=int(riga["vittorie"]),
                sconfitte=int(riga["sconfitte"]),
                fascia_attuale=riga["fascia_attuale"],
                qualificato=int(riga["qualificato"]),
                rk_record=int(riga["rk_record"]),
                streak_vittorie_corrente=int(riga["streak_vittorie_corrente"]),
                streak_vittorie_record=int(riga["streak_vittorie_record"]),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise


# Tabelle collegate a partite/sessioni: vengono svuotate da reset_completo,
# nell'ordine che rispetta le foreign key (prima le "figlie").
TABELLE_STORICO: tuple[str, ...] = (
    "variazioni_rk",
    "partecipazioni_partita",
    "partite",
    "sessione_partecipanti",
    "sessioni_gioco",
    "ranking_leader_log",
)


def reset_completo(conn) -> None:
    """Cancella tutto lo storico (partite, partecipazioni, variazioni Rk,
    sessioni di gioco) e riporta ogni giocatore ai valori di partenza. Non
    tocca giocatori/utenti come account: restano gli stessi nomi e le stesse
    credenziali, solo le statistiche ripartono da zero. Operazione
    irreversibile (a meno di ripristinare un backup preso prima)."""
    try:
        for nome_tabella in TABELLE_STORICO:
            conn.execute(f"DELETE FROM {nome_tabella}")
        conn.execute(
            """UPDATE giocatori SET
                rk_attuale = 1000,
                partite_giocate = 0,
                vittorie = 0,
                sconfitte = 0,
                fascia_attuale = 'H',
                qualificato = 0,
                rk_record = 1000,
                streak_vittorie_corrente = 0,
                streak_vittorie_record = 0"""
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def import_data(conn, dump: dict[str, Any]) -> None:
    if dump.get("versione") != VERSIONE_FORMATO:
        raise ValueError(
            f"Formato di backup non riconosciuto (versione {dump.get('versione')!r}, "
            f"attesa {VERSIONE_FORMATO})"
        )
    tabelle = dump.get("tabelle", {})

    try:
        for nome_tabella in reversed(TABELLE):
            conn.execute(f"DELETE FROM {nome_tabella}")

        for nome_tabella in TABELLE:
            for riga in tabelle.get(nome_tabella, []):
                colonne = ", ".join(riga.keys())
                segnaposto = ", ".join("?" for _ in riga)
                conn.execute(
                    f"INSERT INTO {nome_tabella} ({colonne}) VALUES ({segnaposto})",
                    tuple(riga.values()),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

"""ui_common.py chiama Streamlit (st.subheader, st.table, ecc.) fuori da un
vero `streamlit run`: le chiamate funzionano comunque (con un warning
innocuo "missing ScriptRunContext"), quindi si puo' testare direttamente
senza un harness apposito. Serve soprattutto a coprire gestisci_anteprima_e_
conferma, l'unico punto della UI che chiama compute_match_deltas: un
disallineamento di firma li' (come successo quando compute_match_deltas ha
guadagnato il parametro `parametri`) non veniva intercettato da nessun test,
solo dai log di produzione."""

import streamlit as st

from rokkini import db, ui_common


def crea_giocatori(conn, n: int, prefisso: str = "P") -> list[int]:
    return [db.insert_giocatore(conn, f"{prefisso}{i}") for i in range(1, n + 1)]


def test_gestisci_anteprima_calcola_delta_e_li_salva_in_sessione(conn, admin_id):
    p = crea_giocatori(conn, 6)
    giocatori_per_id = {g["id"]: g for g in db.fetch_giocatori(conn)}
    nomi_per_id = {g["id"]: g["nome"] for g in db.fetch_giocatori(conn)}
    st.session_state.pop("anteprima_partita", None)

    ui_common.gestisci_anteprima_e_conferma(
        conn,
        True,
        nomi_per_id,
        giocatori_per_id,
        "2026-01-01",
        "3v3",
        "2-0",
        p[0:3],
        p[3:6],
    )

    anteprima = st.session_state["anteprima_partita"]
    assert anteprima["squadra_vincente"] == "A"
    assert len(anteprima["deltas_a"]) == 3
    assert len(anteprima["deltas_b"]) == 3
    assert all(d.esito == "vittoria" for d in anteprima["deltas_a"])
    assert all(d.esito == "sconfitta" for d in anteprima["deltas_b"])

    st.session_state.pop("anteprima_partita", None)

from datetime import date

import streamlit as st

from rokkini import auth, db, ui_common
from rokkini.matchmaking import GiocatorePerMatchmaking, genera_combinazioni_bilanciate

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🎮 Sessione di gioco")
st.caption(
    "Seleziona chi c'è oggi: puoi registrare più partite di fila sullo stesso gruppo "
    "senza reinserirlo ogni volta. Se qualcuno se ne va, basta toglierlo dalla lista."
)

giocatori = [g for g in db.fetch_giocatori(conn) if not g["sospeso"]]
if len(giocatori) < 6:
    st.warning("Servono almeno 6 giocatori non sospesi nel sistema per usare questa pagina.")
    st.stop()

nomi_per_id = {g["id"]: g["nome"] for g in giocatori}
giocatori_per_id = {g["id"]: g for g in giocatori}


def _etichetta(giocatore_id: int) -> str:
    return nomi_per_id[giocatore_id]


pool = st.multiselect(
    "Giocatori presenti oggi",
    options=list(nomi_per_id.keys()),
    format_func=_etichetta,
    key="sessione_pool",
)
if len(pool) < 6:
    st.info("Seleziona almeno 6 giocatori presenti per iniziare.")
    st.stop()

st.divider()
modalita = st.radio("Modalità", ["3v3", "4v4"], horizontal=True, key="sessione_modalita")
dimensione = 3 if modalita == "3v3" else 4

chi_gioca = st.multiselect(
    "Chi gioca questa partita (dal gruppo presente)",
    options=pool,
    format_func=_etichetta,
    key="sessione_chi_gioca",
)

# se cambia il gruppo che gioca, le proposte e le squadre gia' scelte non sono
# piu' valide (potrebbero riferirsi a giocatori non piu' selezionati)
if st.session_state.get("sessione_chi_gioca_precedente") != chi_gioca:
    st.session_state.pop("sessione_proposte", None)
    st.session_state.pop("sessione_proposta_applicata", None)
    st.session_state["sessione_squadra_a"] = []
    st.session_state["sessione_squadra_b"] = []
    st.session_state["sessione_chi_gioca_precedente"] = chi_gioca

if len(chi_gioca) != dimensione * 2:
    st.info(f"Seleziona esattamente {dimensione * 2} giocatori per generare le squadre.")
    st.stop()

if st.button("🎲 Suggerisci squadre bilanciate"):
    candidati = [
        GiocatorePerMatchmaking(gid, giocatori_per_id[gid]["rk_attuale"]) for gid in chi_gioca
    ]
    st.session_state["sessione_proposte"] = genera_combinazioni_bilanciate(
        candidati, dimensione, n_proposte=3
    )
    st.session_state.pop("sessione_proposta_applicata", None)

proposte = st.session_state.get("sessione_proposte")
if proposte:
    etichette = [
        f"Proposta {i + 1} — media {p.media_a:.0f} vs {p.media_b:.0f} (Δ{p.differenza:.0f}) · "
        f"A: {', '.join(nomi_per_id[g] for g in p.squadra_a)} · "
        f"B: {', '.join(nomi_per_id[g] for g in p.squadra_b)}"
        for i, p in enumerate(proposte)
    ]
    scelta_idx = st.radio(
        "Proposte bilanciate", range(len(proposte)), format_func=lambda i: etichette[i]
    )
    if st.session_state.get("sessione_proposta_applicata") != scelta_idx:
        st.session_state["sessione_squadra_a"] = proposte[scelta_idx].squadra_a
        st.session_state["sessione_squadra_b"] = proposte[scelta_idx].squadra_b
        st.session_state["sessione_proposta_applicata"] = scelta_idx

st.caption("Puoi modificare le squadre a mano prima di confermare (es. se qualcuno preferisce un'altra formazione).")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Squadra A**")
    squadra_a = st.multiselect(
        "Squadra A",
        options=chi_gioca,
        format_func=_etichetta,
        key="sessione_squadra_a",
        label_visibility="collapsed",
    )
with col_b:
    st.markdown("**Squadra B**")
    squadra_b = st.multiselect(
        "Squadra B",
        options=chi_gioca,
        format_func=_etichetta,
        key="sessione_squadra_b",
        label_visibility="collapsed",
    )

data_partita = st.date_input("Data partita", value=date.today(), key="sessione_data_partita")
risultato_set = st.radio(
    "Risultato set (Squadra A - Squadra B)",
    ["2-0", "2-1", "1-2", "0-2"],
    horizontal=True,
    key="sessione_risultato_set",
)
calcola = st.button("Calcola anteprima", key="sessione_calcola_anteprima")

errori = ui_common.valida_squadre_ui(modalita, squadra_a, squadra_b) if calcola else []
for e in errori:
    st.error(e)

ui_common.gestisci_anteprima_e_conferma(
    conn,
    calcola=calcola and not errori,
    nomi_per_id=nomi_per_id,
    giocatori_per_id=giocatori_per_id,
    data_partita=data_partita.isoformat(),
    modalita=modalita,
    risultato_set=risultato_set,
    squadra_a=squadra_a,
    squadra_b=squadra_b,
    session_key="sessione_anteprima_partita",
)

from datetime import date

import streamlit as st

from rokkini import auth, db, ui_common

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🆕 Nuova partita")

giocatori = [g for g in db.fetch_giocatori(conn) if not g["sospeso"]]
if len(giocatori) < 6:
    st.warning("Servono almeno 6 giocatori non sospesi per registrare una partita 3v3.")
    st.stop()

nomi_per_id = {g["id"]: g["nome"] for g in giocatori}
giocatori_per_id = {g["id"]: g for g in giocatori}


def _etichetta(giocatore_id: int) -> str:
    return nomi_per_id[giocatore_id]


with st.form("nuova_partita_form"):
    data_partita = st.date_input("Data partita", value=date.today())
    modalita = st.radio("Modalità", ["3v3", "4v4"], horizontal=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Squadra A**")
        squadra_a = st.multiselect(
            "Giocatori squadra A",
            options=list(nomi_per_id.keys()),
            format_func=_etichetta,
            key="squadra_a",
            label_visibility="collapsed",
        )
    with col_b:
        st.markdown("**Squadra B**")
        squadra_b = st.multiselect(
            "Giocatori squadra B",
            options=list(nomi_per_id.keys()),
            format_func=_etichetta,
            key="squadra_b",
            label_visibility="collapsed",
        )

    risultato_set = st.radio(
        "Risultato set (Squadra A - Squadra B)", ["2-0", "2-1", "1-2", "0-2"], horizontal=True
    )
    calcola = st.form_submit_button("Calcola anteprima")

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
)

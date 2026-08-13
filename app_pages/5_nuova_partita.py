from datetime import date

import streamlit as st

from rokkini import auth, db, rating_engine
from rokkini.elo import PlayerPreMatch, compute_match_deltas

conn = db.get_connection()
auth.require_role(conn, "admin", "super_admin")

st.title("🆕 Nuova partita")

giocatori = [g for g in db.fetch_giocatori(conn) if not g["sospeso"]]
if len(giocatori) < 6:
    st.warning("Servono almeno 6 giocatori non sospesi per registrare una partita 3v3.")
    st.stop()

nomi_per_id = {g["id"]: g["nome"] for g in giocatori}


def _etichetta(giocatore_id: int) -> str:
    return nomi_per_id[giocatore_id]


with st.form("nuova_partita_form"):
    data_partita = st.date_input("Data partita", value=date.today())
    modalita = st.radio("Modalità", ["3v3", "4v4"], horizontal=True)
    dimensione = 3 if modalita == "3v3" else 4

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

if calcola:
    errori = []
    if len(squadra_a) != dimensione or len(squadra_b) != dimensione:
        errori.append(f"Servono esattamente {dimensione} giocatori per squadra in modalità {modalita}.")
    if set(squadra_a) & set(squadra_b):
        errori.append("Un giocatore non può stare in entrambe le squadre.")
    if len(set(squadra_a)) != len(squadra_a) or len(set(squadra_b)) != len(squadra_b):
        errori.append("Giocatori duplicati nella stessa squadra.")

    if errori:
        for e in errori:
            st.error(e)
    else:
        squadra_vincente = "A" if risultato_set in ("2-0", "2-1") else "B"
        giocatori_per_id = {g["id"]: g for g in giocatori}
        team_a = [
            PlayerPreMatch(
                gid, giocatori_per_id[gid]["rk_attuale"], giocatori_per_id[gid]["partite_giocate"]
            )
            for gid in squadra_a
        ]
        team_b = [
            PlayerPreMatch(
                gid, giocatori_per_id[gid]["rk_attuale"], giocatori_per_id[gid]["partite_giocate"]
            )
            for gid in squadra_b
        ]
        deltas_a, deltas_b = compute_match_deltas(team_a, team_b, squadra_vincente)
        st.session_state["anteprima_partita"] = {
            "data_partita": data_partita.isoformat(),
            "modalita": modalita,
            "risultato_set": risultato_set,
            "squadra_vincente": squadra_vincente,
            "squadra_a": squadra_a,
            "squadra_b": squadra_b,
            "deltas_a": deltas_a,
            "deltas_b": deltas_b,
        }

anteprima = st.session_state.get("anteprima_partita")
if anteprima:
    st.subheader("Anteprima risultato")

    def _tabella(deltas, vincitrice: bool) -> None:
        titolo = "Vittoria" if vincitrice else "Sconfitta"
        st.markdown(f"**{titolo}**")
        st.table(
            {
                "Giocatore": [nomi_per_id[d.player_id] for d in deltas],
                "Prima": [d.rk_prima for d in deltas],
                "Variazione": [f"{'+' if d.delta >= 0 else ''}{d.delta}" for d in deltas],
                "Dopo": [d.rk_dopo for d in deltas],
            }
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Squadra A")
        _tabella(anteprima["deltas_a"], anteprima["squadra_vincente"] == "A")
    with col_b:
        st.markdown("### Squadra B")
        _tabella(anteprima["deltas_b"], anteprima["squadra_vincente"] == "B")

    if st.button("✅ Conferma e registra", type="primary"):
        utente_id = auth.current_user_id(conn)
        rating_engine.register_match(
            conn,
            anteprima["data_partita"],
            anteprima["modalita"],
            anteprima["risultato_set"],
            anteprima["squadra_vincente"],
            anteprima["squadra_a"],
            anteprima["squadra_b"],
            utente_id,
        )
        del st.session_state["anteprima_partita"]
        st.success("Partita registrata.")
        st.rerun()

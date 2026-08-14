import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("🟢 Sessioni attive")

sessione = db.fetch_sessione_attiva(conn)
if sessione is None:
    st.info("Nessuna sessione di gioco in corso al momento.")
    st.stop()

st.success(f"Sessione in corso, iniziata alle {sessione['iniziata_at']}.")

partecipanti = db.fetch_partecipanti_sessione(conn, sessione["id"])
classifica_sessione = {
    r["nome"]: r for r in stats.fetch_classifica_sessione(conn, sessione["id"])
}

st.subheader(f"Classifica della sessione — presenti ({len(partecipanti)})")
righe = [
    {
        "Giocatore": g["nome"],
        "Rk guadagnati oggi": classifica_sessione.get(g["nome"], {}).get("rk_sessione", 0),
        "Rk totale attuale": g["rk_attuale"],
    }
    for g in partecipanti
]
righe.sort(key=lambda r: r["Rk guadagnati oggi"], reverse=True)
st.dataframe(righe, hide_index=True, use_container_width=True)

st.divider()
cronologia = stats.fetch_match_history_sessione(conn, sessione["id"])
if not cronologia:
    st.caption("Nessuna partita ancora giocata in questa sessione.")
    st.stop()

st.subheader(f"Partite giocate ({len(cronologia)})")
for voce in reversed(cronologia):
    p = voce["partita"]
    vincitrice_a = p["squadra_vincente"] == "A"
    with st.expander(f"{p['modalita']} — {p['risultato_set']}"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Squadra A** {'🏆' if vincitrice_a else ''}")
            for g in voce["squadra_a"]:
                st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")
        with col_b:
            st.markdown(f"**Squadra B** {'🏆' if not vincitrice_a else ''}")
            for g in voce["squadra_b"]:
                st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")

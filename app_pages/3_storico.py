import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("📜 Storico partite")

cronologia = stats.fetch_match_history(conn)
if not cronologia:
    st.info("Nessuna partita registrata.")
    st.stop()

for voce in cronologia:
    partita = voce["partita"]
    titolo = f"{partita['data_partita']} — {partita['modalita']} — {partita['risultato_set']}"
    if partita["voided"]:
        titolo += "  ⚠️ ANNULLATA"
    with st.expander(titolo):
        if partita["voided"]:
            st.warning(f"Partita annullata. Motivo: {partita['voided_reason'] or '—'}")
        col_a, col_b = st.columns(2)
        vincitrice_a = partita["squadra_vincente"] == "A"
        with col_a:
            st.markdown(f"**Squadra A** {'🏆' if vincitrice_a else ''}")
            for giocatore in voce["squadra_a"]:
                segno = "+" if giocatore["delta"] >= 0 else ""
                st.write(f"{giocatore['nome']}  {segno}{giocatore['delta']} Rk")
        with col_b:
            st.markdown(f"**Squadra B** {'🏆' if not vincitrice_a else ''}")
            for giocatore in voce["squadra_b"]:
                segno = "+" if giocatore["delta"] >= 0 else ""
                st.write(f"{giocatore['nome']}  {segno}{giocatore['delta']} Rk")

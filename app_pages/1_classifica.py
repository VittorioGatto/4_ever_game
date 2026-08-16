import streamlit as st

from rokkini import db, stats
from rokkini.constants import PARTITE_QUALIFICAZIONE

conn = db.get_connection()

st.title("🏆 Classifica")

fascia = st.radio("Fascia", ["Tutti", "A", "B", "C", "D", "H"], horizontal=True)
ranking = stats.fetch_ranking(conn, fascia=fascia)

if ranking.height == 0:
    st.info(
        f"Nessun giocatore ancora in classifica (serve aver completato le "
        f"{PARTITE_QUALIFICAZIONE} partite di qualificazione)."
    )
else:
    st.dataframe(
        ranking,
        hide_index=True,
        width="stretch",
        column_config={
            "posizione": st.column_config.NumberColumn("#"),
            "nome": st.column_config.TextColumn("Giocatore"),
            "rk_attuale": st.column_config.NumberColumn("Rk"),
            "fascia_attuale": st.column_config.TextColumn("Fascia"),
            "partite_giocate": st.column_config.NumberColumn("Partite"),
            "vittorie": st.column_config.NumberColumn("Vittorie"),
            "sconfitte": st.column_config.NumberColumn("Sconfitte"),
            "percentuale_vittorie": st.column_config.NumberColumn("Vittorie %", format="%.1f%%"),
        },
    )

qualificazione = stats.fetch_in_qualificazione(conn)
if qualificazione.height:
    st.subheader("In qualificazione")
    st.caption(f"Servono almeno {PARTITE_QUALIFICAZIONE} partite ufficiali per entrare in classifica.")
    st.dataframe(
        qualificazione,
        hide_index=True,
        width="stretch",
        column_config={
            "nome": st.column_config.TextColumn("Giocatore"),
            "rk_attuale": st.column_config.NumberColumn("Rk"),
            "partite_giocate": st.column_config.NumberColumn("Partite"),
            "vittorie": st.column_config.NumberColumn("Vittorie"),
            "sconfitte": st.column_config.NumberColumn("Sconfitte"),
        },
    )

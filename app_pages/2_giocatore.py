import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("👤 Scheda giocatore")

giocatori = db.fetch_giocatori(conn)
if not giocatori:
    st.info("Nessun giocatore registrato.")
    st.stop()

nomi = [g["nome"] for g in giocatori]
nome_scelto = st.selectbox("Giocatore", nomi)
giocatore_id = next(g["id"] for g in giocatori if g["nome"] == nome_scelto)

profilo = stats.fetch_player_profile(conn, giocatore_id)
g = profilo["giocatore"]

col1, col2, col3 = st.columns(3)
col1.metric("Rk attuali", g["rk_attuale"])
col2.metric("Fascia", g["fascia_attuale"])
col3.metric("Posizione", f"#{profilo['posizione']}" if profilo["posizione"] else "in qualificazione")

if g["sospeso"]:
    st.warning("Giocatore sospeso.")

st.subheader("Statistiche")
st.table(
    {
        "Partite": [g["partite_giocate"]],
        "Vittorie": [g["vittorie"]],
        "Sconfitte": [g["sconfitte"]],
        "Vittorie %": [f"{profilo['percentuale_vittorie']}%"],
        "Record Rk": [g["rk_record"]],
        "Serie vittorie attuale": [g["streak_vittorie_corrente"]],
        "Serie vittorie record": [g["streak_vittorie_record"]],
    }
)

st.subheader("Andamento Rk")
if profilo["storico_rk"].height > 1:
    st.line_chart(profilo["storico_rk"], x="partita_numero", y="rk")
else:
    st.caption("Nessuna partita ancora giocata.")

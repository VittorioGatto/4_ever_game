import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("📊 Statistiche / Record")

record = stats.fetch_records(conn)


def mostra_record(etichetta: str, chiave: str, formato: str = "{}") -> None:
    dato = record[chiave]
    if dato is None:
        st.metric(etichetta, "—")
    else:
        st.metric(etichetta, f"{dato['nome']} — {formato.format(dato['valore'])}")


col1, col2 = st.columns(2)
with col1:
    mostra_record("Rk più alto di sempre", "rk_piu_alto")
    mostra_record("Più partite", "piu_partite")
    mostra_record("Serie di vittorie", "serie_vittorie")
with col2:
    mostra_record("Più vittorie", "piu_vittorie")
    mostra_record("Più giorni al #1", "giorni_al_numero_1", formato="{:.0f} giorni")

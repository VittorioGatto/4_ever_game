import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("📊 Statistiche / Record")

record = stats.fetch_records(conn)
record_stupidi = stats.fetch_record_stupidi(conn)


def mostra_record(dati: dict, etichetta: str, chiave: str, formato: str = "{}") -> None:
    dato = dati[chiave]
    if dato is None:
        st.metric(etichetta, "—")
    else:
        st.metric(etichetta, f"{dato['nome']} — {formato.format(dato['valore'])}")


col1, col2 = st.columns(2)
with col1:
    mostra_record(record, "Rk più alto di sempre", "rk_piu_alto")
    mostra_record(record, "Più partite", "piu_partite")
    mostra_record(record, "Serie di vittorie", "serie_vittorie")
with col2:
    mostra_record(record, "Più vittorie", "piu_vittorie")
    mostra_record(record, "Più giorni al #1", "giorni_al_numero_1", formato="{:.0f} giorni")

st.divider()
st.subheader("🤡 Statistiche stupide")

col3, col4 = st.columns(2)
with col3:
    mostra_record(record_stupidi, "La rimonta più clamorosa", "rimonta_clamorosa", formato="+{} Rk in una partita")
    mostra_record(
        record_stupidi,
        "Il colpaccio a sorpresa",
        "sorpresa_piu_grande",
        formato="vinta con solo il {}% di probabilità",
    )
    mostra_record(record_stupidi, "Il maratoneta del giorno", "giornata_intensa", formato="{} partite in un giorno")
with col4:
    mostra_record(record_stupidi, "Il tonfo più doloroso", "tonfo_doloroso", formato="{} Rk in una partita")
    mostra_record(record_stupidi, "La serie nera più lunga", "serie_sconfitte", formato="{} sconfitte di fila")

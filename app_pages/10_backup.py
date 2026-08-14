import json
from datetime import datetime

import streamlit as st

from rokkini import auth, backup, db

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("💾 Backup dati")

st.subheader("Esporta")
st.caption(
    "Scarica un file JSON con tutti i dati (giocatori, utenti, partite, storico Rk). "
    "Contiene anche gli hash delle password (bcrypt, non testo in chiaro): trattalo comunque "
    "come un file riservato."
)
dump = backup.export_data(conn)
nome_file = f"rokkini_backup_{datetime.now():%Y%m%d_%H%M%S}.json"
st.download_button(
    "⬇️ Scarica backup",
    data=json.dumps(dump, indent=2, ensure_ascii=False),
    file_name=nome_file,
    mime="application/json",
)

st.divider()

st.subheader("Importa")
st.error(
    "⚠️ L'importazione SOSTITUISCE tutti i dati attuali (giocatori, utenti, storico partite) "
    "con quelli del file caricato. Non è un'unione: quello che c'è ora viene cancellato. "
    "Usalo solo per un ripristino da backup."
)
file_caricato = st.file_uploader("File di backup (.json)", type="json")

if file_caricato is not None:
    try:
        dump_da_importare = json.loads(file_caricato.getvalue())
    except json.JSONDecodeError:
        st.error("Il file non è un JSON valido.")
        st.stop()

    n_giocatori = len(dump_da_importare.get("tabelle", {}).get("giocatori", []))
    n_partite = len(dump_da_importare.get("tabelle", {}).get("partite", []))
    st.write(f"Il file contiene **{n_giocatori} giocatori** e **{n_partite} partite**.")

    conferma = st.text_input("Scrivi CONFERMO per abilitare l'importazione")
    if st.button("Importa e sostituisci tutto", type="primary", disabled=conferma != "CONFERMO"):
        try:
            backup.import_data(conn, dump_da_importare)
        except Exception as e:
            st.error(f"Importazione fallita, nessun dato modificato: {e}")
        else:
            st.success("Dati importati correttamente.")
            st.rerun()

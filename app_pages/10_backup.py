import json
from datetime import datetime

import streamlit as st

from rokkini import auth, backup, db, ui_common

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("💾 Backup dati")
ui_common.mostra_messaggio_pendente()

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
_contatore_upload = st.session_state.get("_contatore_upload_backup", 0)
file_caricato = st.file_uploader(
    "File di backup (.json)", type="json", key=f"file_backup_{_contatore_upload}"
)

if file_caricato is not None:
    try:
        dump_da_importare = json.loads(file_caricato.getvalue())
    except json.JSONDecodeError:
        st.error("Il file non è un JSON valido.")
        st.stop()

    n_giocatori = len(dump_da_importare.get("tabelle", {}).get("giocatori", []))
    n_partite = len(dump_da_importare.get("tabelle", {}).get("partite", []))
    st.write(f"Il file contiene **{n_giocatori} giocatori** e **{n_partite} partite**.")

    conferma = st.text_input("Scrivi CONFERMO per abilitare l'importazione", key="conferma_importa")
    if st.button("Importa e sostituisci tutto", type="primary", disabled=conferma != "CONFERMO"):
        try:
            backup.import_data(conn, dump_da_importare)
        except Exception as e:
            st.error(f"Importazione fallita, nessun dato modificato: {e}")
        else:
            ui_common.imposta_messaggio_pendente("✅ Dati importati correttamente.")
            st.session_state.pop("conferma_importa", None)
            st.session_state["_contatore_upload_backup"] = _contatore_upload + 1
            st.rerun()

st.divider()

st.subheader("🔄 Reset completo")
st.error(
    "⚠️ Cancella TUTTE le partite e le sessioni di gioco (storico e Rk guadagnati/persi), e "
    "riporta ogni giocatore ai valori di partenza: Rk 1000, zero partite/vittorie/sconfitte. "
    "Giocatori e utenti restano (stessi nomi, stesse credenziali), solo le statistiche "
    "ripartono da zero. Non è reversibile: se vuoi poterci tornare, scarica prima un backup "
    "qui sopra."
)
conferma_reset = st.text_input("Scrivi AZZERA per abilitare il reset", key="conferma_reset")
if st.button("🔄 Azzera tutte le partite", type="primary", disabled=conferma_reset != "AZZERA"):
    backup.reset_completo(conn)
    ui_common.imposta_messaggio_pendente("✅ Tutto azzerato: partite cancellate, giocatori tornati a Rk 1000.")
    st.session_state.pop("conferma_reset", None)
    st.rerun()

import csv
import io
from datetime import datetime

import streamlit as st

from rokkini import auth, backup, db, ui_common

conn = db.get_connection()
auth.require_role(conn, "super_admin")


def _csv_da_righe(righe: list[dict], colonne: tuple[str, ...]) -> str:
    buffer = io.StringIO()
    scrittore = csv.DictWriter(buffer, fieldnames=colonne)
    scrittore.writeheader()
    scrittore.writerows(righe)
    return buffer.getvalue()


def _righe_da_csv(file_caricato) -> list[dict]:
    testo = file_caricato.getvalue().decode("utf-8")
    return list(csv.DictReader(io.StringIO(testo)))


st.title("💾 Backup dati")
ui_common.mostra_messaggio_pendente()

st.subheader("Esporta")
st.caption(
    "Due file CSV, con la data dell'esportazione: uno con le partite giocate (chi ha "
    "vinto, chi ha giocato), uno con il Rk attuale di ogni giocatore. Sono anche i file "
    "da usare per un ripristino (sotto)."
)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

col_export_1, col_export_2 = st.columns(2)
with col_export_1:
    righe_giocatori_export = backup.export_giocatori_csv(conn)
    st.download_button(
        "⬇️ Rk giocatori (CSV)",
        data=_csv_da_righe(righe_giocatori_export, backup.COLONNE_GIOCATORI_CSV),
        file_name=f"rokkup_giocatori_{timestamp}.csv",
        mime="text/csv",
    )
with col_export_2:
    righe_partite_export = backup.export_partite_csv(conn)
    st.download_button(
        "⬇️ Partite (CSV)",
        data=_csv_da_righe(righe_partite_export, backup.COLONNE_PARTITE_CSV),
        file_name=f"rokkup_partite_{timestamp}.csv",
        mime="text/csv",
    )

st.divider()

st.subheader("Importa (ripristino da CSV)")
st.error(
    "⚠️ Il ripristino SOSTITUISCE tutto lo storico partite attuale con quello dei file "
    "caricati, e riporta il Rk di ogni giocatore al valore congelato nel file giocatori "
    "(anche se nel frattempo la logica di calcolo dei punti e' cambiata). Non tocca gli "
    "account utente. Usalo solo per un ripristino da backup."
)
_contatore_upload = st.session_state.get("_contatore_upload_backup", 0)
file_giocatori = st.file_uploader(
    "File Rk giocatori (.csv)", type="csv", key=f"file_giocatori_{_contatore_upload}"
)
file_partite = st.file_uploader(
    "File partite (.csv)", type="csv", key=f"file_partite_{_contatore_upload}"
)

if file_giocatori is not None and file_partite is not None:
    try:
        righe_giocatori = _righe_da_csv(file_giocatori)
        righe_partite = _righe_da_csv(file_partite)
    except UnicodeDecodeError:
        st.error("Uno dei due file non e' un CSV valido.")
        st.stop()

    st.write(f"I file contengono **{len(righe_giocatori)} giocatori** e **{len(righe_partite)} partite**.")

    conferma = st.text_input("Scrivi CONFERMO per abilitare il ripristino", key="conferma_importa")
    if st.button("Ripristina da CSV", type="primary", disabled=conferma != "CONFERMO"):
        try:
            backup.import_csv(conn, righe_giocatori, righe_partite, auth.current_user_id(conn))
        except Exception as e:
            st.error(f"Ripristino fallito, nessun dato modificato: {e}")
        else:
            ui_common.imposta_messaggio_pendente("✅ Dati ripristinati correttamente.")
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

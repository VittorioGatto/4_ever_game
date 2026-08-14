import streamlit as st

from rokkini import auth, db

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🧑‍🤝‍🧑 Gestione giocatori")

st.subheader("Nuovo giocatore")
with st.form("nuovo_giocatore_form", clear_on_submit=True):
    nome = st.text_input("Nome")
    crea = st.form_submit_button("Crea")
    if crea:
        if not nome.strip():
            st.error("Il nome non può essere vuoto.")
        else:
            db.insert_giocatore(conn, nome.strip())
            conn.commit()
            st.success(f"Giocatore '{nome.strip()}' creato con 1000 Rk, in qualificazione.")
            st.rerun()

st.subheader("Giocatori esistenti")
giocatori = db.fetch_giocatori(conn)
if not giocatori:
    st.info("Nessun giocatore ancora registrato.")
    st.stop()

for g in giocatori:
    with st.expander(f"{g['nome']} — {g['rk_attuale']} Rk ({g['fascia_attuale']})"):
        col1, col2 = st.columns([3, 1])
        with col1:
            nuovo_nome = st.text_input("Nome", value=g["nome"], key=f"nome_{g['id']}")
            if (
                nuovo_nome.strip()
                and nuovo_nome.strip() != g["nome"]
                and st.button("Salva nome", key=f"salva_nome_{g['id']}")
            ):
                db.update_giocatore_nome(conn, g["id"], nuovo_nome.strip())
                st.success("Nome aggiornato.")
                st.rerun()
        with col2:
            sospeso = bool(g["sospeso"])
            nuovo_stato = st.checkbox("Sospeso", value=sospeso, key=f"sospeso_{g['id']}")
            if nuovo_stato != sospeso:
                db.set_giocatore_sospeso(conn, g["id"], nuovo_stato)
                st.rerun()
        st.caption(
            f"Partite: {g['partite_giocate']} · Vittorie: {g['vittorie']} · "
            f"Sconfitte: {g['sconfitte']} · Qualificato: {'sì' if g['qualificato'] else 'no'}"
        )
        st.caption(
            "Gli Rk non sono modificabili direttamente da qui: per correggere un errore "
            "usa 'Correggi/annulla partita', così la modifica resta tracciata."
        )

        if g["partite_giocate"] == 0:
            if st.button("🗑️ Elimina giocatore", key=f"elimina_{g['id']}"):
                try:
                    db.delete_giocatore(conn, g["id"])
                except Exception as e:
                    st.error(f"Impossibile eliminare: {e}")
                else:
                    st.success(f"Giocatore '{g['nome']}' eliminato.")
                    st.rerun()
        else:
            st.caption(
                "Non eliminabile: ha già partite registrate. Usa 'Sospeso' per nasconderlo "
                "dalla selezione senza perdere lo storico."
            )

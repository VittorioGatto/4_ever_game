import streamlit as st

from rokkini import auth, db

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🔐 Gestione utenti")

giocatori = db.fetch_giocatori(conn)
nomi_giocatore_per_id = {g["id"]: g["nome"] for g in giocatori}

st.subheader("Nuovo utente")
with st.form("nuovo_utente_form", clear_on_submit=True):
    username = st.text_input("Username")
    nome_visualizzato = st.text_input("Nome visualizzato")
    email = st.text_input("Email (opzionale)")
    password = st.text_input("Password", type="password")
    ruolo = st.radio("Ruolo", ["admin", "super_admin"], horizontal=True)
    giocatore_collegato = st.selectbox(
        "Collega a un giocatore (opzionale)",
        options=[None, *nomi_giocatore_per_id.keys()],
        format_func=lambda gid: "—" if gid is None else nomi_giocatore_per_id[gid],
    )
    crea = st.form_submit_button("Crea utente")

    if crea:
        errori = []
        if not username.strip():
            errori.append("Username obbligatorio.")
        elif db.fetch_utente_by_username(conn, username.strip()) is not None:
            errori.append(f"L'utente '{username.strip()}' esiste già.")
        if not nome_visualizzato.strip():
            errori.append("Nome visualizzato obbligatorio.")
        if len(password) < 6:
            errori.append("La password deve avere almeno 6 caratteri.")

        if errori:
            for e in errori:
                st.error(e)
        else:
            db.insert_utente(
                conn,
                username=username.strip(),
                nome_visualizzato=nome_visualizzato.strip(),
                password_hash=auth.hash_password(password),
                ruolo=ruolo,
                email=email.strip() or None,
                giocatore_id=giocatore_collegato,
            )
            st.success(f"Utente '{username.strip()}' creato (ruolo: {ruolo}).")
            st.rerun()

st.subheader("Utenti attivi")
utenti = db.fetch_utenti_attivi(conn)
if not utenti:
    st.info("Nessun utente attivo.")
    st.stop()

utente_corrente_id = auth.current_user_id(conn)
for u in utenti:
    col1, col2, col3 = st.columns([3, 2, 1])
    col1.write(f"**{u['username']}** — {u['nome_visualizzato']}")
    col2.write(u["ruolo"])
    with col3:
        if u["id"] == utente_corrente_id:
            st.caption("(tu)")
        elif st.button("Disattiva", key=f"disattiva_{u['id']}"):
            db.set_utente_attivo(conn, u["id"], False)
            st.success(f"Utente '{u['username']}' disattivato.")
            st.rerun()

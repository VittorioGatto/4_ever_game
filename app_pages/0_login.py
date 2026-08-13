import streamlit as st

from rokkini import auth, db

conn = db.get_connection()
authenticator = st.session_state["_authenticator"]

st.title("🔑 Account")

if auth.current_username():
    ruolo = auth.current_role(conn)
    st.success(f"Accesso effettuato come **{st.session_state.get('name')}** (ruolo: {ruolo}).")
    authenticator.logout("Esci", "main")
else:
    try:
        authenticator.login("main")
    except Exception as e:
        st.error(str(e))

    if st.session_state.get("authentication_status") is False:
        st.error("Username o password non corretti.")
    elif st.session_state.get("authentication_status") is None:
        st.info("Effettua il login per registrare o correggere partite. La classifica resta visibile a tutti senza login.")

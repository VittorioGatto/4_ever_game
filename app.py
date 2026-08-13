import streamlit as st

from rokkini import auth, db

st.set_page_config(page_title="Rokkini", page_icon="🏐", layout="wide")

conn = db.get_connection()
authenticator = auth.build_authenticator(conn)
st.session_state["_authenticator"] = authenticator
auth.restore_session(authenticator)
ruolo = auth.current_role(conn)

pagine_pubbliche = [
    st.Page("app_pages/1_classifica.py", title="Classifica", icon="🏆", default=True),
    st.Page("app_pages/2_giocatore.py", title="Giocatore", icon="👤"),
    st.Page("app_pages/3_storico.py", title="Storico partite", icon="📜"),
    st.Page("app_pages/4_statistiche.py", title="Statistiche / Record", icon="📊"),
]
pagine_account = [st.Page("app_pages/0_login.py", title="Account", icon="🔑")]

sezioni = {"Rokkini": pagine_pubbliche, "Account": pagine_account}

if ruolo in ("admin", "super_admin"):
    sezioni["Amministrazione"] = [
        st.Page("app_pages/5_nuova_partita.py", title="Nuova partita", icon="🆕"),
    ]

if ruolo == "super_admin":
    sezioni["Amministrazione"] += [
        st.Page("app_pages/6_correggi_partita.py", title="Correggi/annulla partita", icon="✏️"),
        st.Page("app_pages/7_gestione_giocatori.py", title="Gestione giocatori", icon="🧑‍🤝‍🧑"),
        st.Page("app_pages/8_gestione_utenti.py", title="Gestione utenti", icon="🔐"),
    ]

navigazione = st.navigation(sezioni)
navigazione.run()

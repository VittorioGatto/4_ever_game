import streamlit as st

from rokkini import auth, db, theme

st.set_page_config(page_title="RokkUp", page_icon="🏐", layout="wide")
theme.inject_custom_css()

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
    st.Page("app_pages/11_sessioni_attive.py", title="Sessioni attive", icon="🟢"),
    st.Page("app_pages/12_regolamento.py", title="Regolamento", icon="📖"),
]
pagine_account = [st.Page("app_pages/0_login.py", title="Account", icon="🔑")]

sezioni = {"RokkUp": pagine_pubbliche, "Account": pagine_account}

if ruolo == "super_admin":
    sezioni["Amministrazione"] = [
        st.Page("app_pages/9_sessione_di_gioco.py", title="Sessione di gioco", icon="🎮"),
        st.Page("app_pages/6_correggi_partita.py", title="Correggi/annulla partita", icon="✏️"),
        st.Page("app_pages/7_gestione_giocatori.py", title="Gestione giocatori", icon="🧑‍🤝‍🧑"),
        st.Page("app_pages/8_gestione_utenti.py", title="Gestione utenti", icon="🔐"),
        st.Page("app_pages/10_backup.py", title="Backup dati", icon="💾"),
    ]

navigazione = st.navigation(sezioni)
navigazione.run()

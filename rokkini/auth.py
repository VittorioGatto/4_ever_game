"""Autenticazione (streamlit-authenticator) e controllo dei ruoli."""

import streamlit as st
import streamlit_authenticator as stauth

from rokkini import db

RUOLI_VALIDI = ("admin", "super_admin")


def hash_password(password: str) -> str:
    return stauth.Hasher().hash(password)


def build_authenticator(conn) -> stauth.Authenticate:
    utenti = db.fetch_utenti_attivi(conn)
    credentials = {
        "usernames": {
            u["username"]: {
                "email": u["email"] or "",
                "name": u["nome_visualizzato"],
                "password": u["password_hash"],
            }
            for u in utenti
        }
    }
    cfg = st.secrets["auth"]
    return stauth.Authenticate(
        credentials,
        cfg["cookie_name"],
        cfg["cookie_key"],
        cfg["cookie_expiry_days"],
        auto_hash=False,
        # streamlit-authenticator sleeps PRE_LOGIN_SLEEP_TIME (0.7s) on every
        # anonymous run while checking the cookie; on a fresh session that
        # delay races with Streamlit's client-side URL routing for non-default
        # pages and makes it fall back to the default page. We don't need the
        # artificial delay since we're not rendering a form in that path.
        login_sleep_time=0,
    )


def restore_session(authenticator: stauth.Authenticate) -> None:
    """Ricontrolla il cookie di autenticazione senza disegnare il form di
    login. Necessario perché in un'app multipagina st.session_state parte
    vuoto a ogni nuova sessione (es. reload diretto su una pagina admin, o
    apertura di un URL salvato nei preferiti): senza questo, solo la pagina
    di login rileverebbe una sessione gia' valida.

    Prende un authenticator gia' costruito (una sola volta per run, in
    app.py) invece di costruirne uno proprio: un secondo `Authenticate(...)`
    nello stesso run monterebbe un secondo componente CookieManager con la
    stessa chiave di default, causando uno StreamlitDuplicateElementKey."""
    if current_username() is not None:
        return
    authenticator.login(location="unrendered")


def current_username() -> str | None:
    if not st.session_state.get("authentication_status"):
        return None
    return st.session_state.get("username")


def current_role(conn) -> str | None:
    username = current_username()
    if username is None:
        return None
    utente = db.fetch_utente_by_username(conn, username)
    if utente is None or not utente["attivo"]:
        return None
    return utente["ruolo"]


def current_user_id(conn) -> int | None:
    username = current_username()
    if username is None:
        return None
    utente = db.fetch_utente_by_username(conn, username)
    return utente["id"] if utente else None


def require_role(conn, *allowed_roles: str) -> None:
    role = current_role(conn)
    if role not in allowed_roles:
        st.error("Accesso non autorizzato: questa pagina richiede un ruolo diverso.")
        st.stop()

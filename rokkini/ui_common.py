"""Blocchi di UI Streamlit condivisi tra le pagine che registrano una
partita (partita semplice e ogni incontro di un torneo, dentro Sessione di
gioco), per non duplicare la logica di validazione/punteggio/conferma."""

from collections.abc import Callable

import streamlit as st

from rokkini import auth, rating_engine
from rokkini.elo import PlayerPreMatch, compute_match_deltas
from rokkini.parametri import fetch_parametri_attivi


def imposta_messaggio_pendente(
    testo: str, tabella: dict | None = None, chiave: str = "_messaggio_operazione"
) -> None:
    """Salva un messaggio di successo da mostrare al PROSSIMO run, prima di
    un st.rerun(): chiamare st.success() e poi st.rerun() nello stesso run
    e' una corsa persa, perche' il rerun scarta il frame corrente prima che
    l'utente possa vedere il messaggio. Va abbinata a mostra_messaggio_pendente
    in cima alla pagina."""
    st.session_state[chiave] = {"testo": testo, "tabella": tabella}


def mostra_messaggio_pendente(chiave: str = "_messaggio_operazione") -> None:
    dato = st.session_state.pop(chiave, None)
    if dato:
        st.success(dato["testo"])
        if dato.get("tabella"):
            st.table(dato["tabella"])


def ripristina_widget_persistente(key: str) -> None:
    """Streamlit "dimentica" lo stato di un widget quando la pagina che lo
    dichiara non viene eseguita in un run (es. si naviga su un'altra pagina
    e poi si torna indietro): da chiamare PRIMA di creare il widget, per
    ripristinarne il valore da una copia ombra non legata a nessun widget
    (e quindi mai soggetta a questa pulizia). Va abbinata a
    salva_widget_persistente subito dopo aver creato il widget."""
    shadow_key = f"_persist_{key}"
    if key not in st.session_state and shadow_key in st.session_state:
        st.session_state[key] = st.session_state[shadow_key]


def salva_widget_persistente(key: str) -> None:
    if key in st.session_state:
        st.session_state[f"_persist_{key}"] = st.session_state[key]


def valida_squadre_ui(modalita: str, squadra_a: list[int], squadra_b: list[int]) -> list[str]:
    """Stessi controlli di rating_engine._validate_squadre, ma come lista di
    messaggi per st.error invece di un'eccezione: l'utente deve poter
    correggere la selezione senza far esplodere la pagina."""
    dimensione = 3 if modalita == "3v3" else 4
    errori = []
    if len(squadra_a) != dimensione or len(squadra_b) != dimensione:
        errori.append(f"Servono esattamente {dimensione} giocatori per squadra in modalità {modalita}.")
    if set(squadra_a) & set(squadra_b):
        errori.append("Un giocatore non può stare in entrambe le squadre.")
    if len(set(squadra_a)) != len(squadra_a) or len(set(squadra_b)) != len(squadra_b):
        errori.append("Giocatori duplicati nella stessa squadra.")
    return errori


def registra_set_live(session_key: str) -> tuple[str, str] | None:
    """Due bottoni "Set vinto da A/B" con contatore visibile e un bottone
    "Annulla ultimo set" per correggere un click sbagliato. Una volta che una
    squadra arriva a 2 set vinti, i bottoni di incremento si disabilitano
    (serve annullare per proseguire, cosi' il punteggio resta sempre uno tra
    2-0/2-1/1-2/0-2). Ritorna (risultato_set, squadra_vincente) a partita
    conclusa, altrimenti None."""
    stato = st.session_state.setdefault(session_key, {"a": 0, "b": 0, "storico": []})
    conclusa = stato["a"] == 2 or stato["b"] == 2

    st.markdown(f"**Set — Squadra A {stato['a']} : {stato['b']} Squadra B**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🏐 Set vinto da A", key=f"{session_key}_a", disabled=conclusa):
            stato["a"] += 1
            stato["storico"].append("A")
            st.rerun()
    with col2:
        if st.button("🏐 Set vinto da B", key=f"{session_key}_b", disabled=conclusa):
            stato["b"] += 1
            stato["storico"].append("B")
            st.rerun()
    with col3:
        if st.button(
            "↩️ Annulla ultimo set", key=f"{session_key}_undo", disabled=not stato["storico"]
        ):
            ultimo = stato["storico"].pop()
            stato["a" if ultimo == "A" else "b"] -= 1
            st.rerun()

    if conclusa:
        return f"{stato['a']}-{stato['b']}", ("A" if stato["a"] == 2 else "B")
    return None


def reset_set_live(session_key: str) -> None:
    st.session_state.pop(session_key, None)


def gestisci_anteprima_e_conferma(
    conn,
    calcola: bool,
    nomi_per_id: dict[int, str],
    giocatori_per_id: dict[int, dict],
    data_partita: str,
    modalita: str,
    risultato_set: str,
    squadra_a: list[int],
    squadra_b: list[int],
    session_key: str = "anteprima_partita",
    sessione_id: int | None = None,
    set_live_key: str | None = None,
    on_success: Callable[[], None] | None = None,
) -> None:
    """Se `calcola` è True (bottone premuto in questo run), calcola i delta
    e li salva in sessione. In ogni caso, se una anteprima è presente in
    sessione, la mostra con il bottone di conferma che registra la partita.

    `set_live_key`, se dato, viene ripulito con reset_set_live dopo la
    conferma (cosi' il contatore set riparte da 0-0 per la partita
    successiva). `on_success`, se dato, viene richiamato subito dopo la
    registrazione riuscita, prima del rerun: usato dal torneo per segnare la
    fixture corrente come giocata."""
    if calcola:
        squadra_vincente = "A" if risultato_set in ("2-0", "2-1") else "B"
        team_a = [
            PlayerPreMatch(
                gid, giocatori_per_id[gid]["rk_attuale"], giocatori_per_id[gid]["partite_giocate"]
            )
            for gid in squadra_a
        ]
        team_b = [
            PlayerPreMatch(
                gid, giocatori_per_id[gid]["rk_attuale"], giocatori_per_id[gid]["partite_giocate"]
            )
            for gid in squadra_b
        ]
        parametri_attivi = fetch_parametri_attivi(conn)
        deltas_a, deltas_b = compute_match_deltas(team_a, team_b, squadra_vincente, parametri_attivi)
        st.session_state[session_key] = {
            "data_partita": data_partita,
            "modalita": modalita,
            "risultato_set": risultato_set,
            "squadra_vincente": squadra_vincente,
            "squadra_a": squadra_a,
            "squadra_b": squadra_b,
            "deltas_a": deltas_a,
            "deltas_b": deltas_b,
        }

    anteprima = st.session_state.get(session_key)
    if not anteprima:
        return

    st.subheader("Anteprima risultato")

    def _tabella(deltas, vincitrice: bool) -> None:
        titolo = "Vittoria" if vincitrice else "Sconfitta"
        st.markdown(f"**{titolo}**")
        st.table(
            {
                "Giocatore": [nomi_per_id[d.player_id] for d in deltas],
                "Prima": [d.rk_prima for d in deltas],
                "Variazione": [f"{'+' if d.delta >= 0 else ''}{d.delta}" for d in deltas],
                "Dopo": [d.rk_dopo for d in deltas],
            }
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Squadra A")
        _tabella(anteprima["deltas_a"], anteprima["squadra_vincente"] == "A")
    with col_b:
        st.markdown("### Squadra B")
        _tabella(anteprima["deltas_b"], anteprima["squadra_vincente"] == "B")

    if st.button("✅ Conferma e registra", type="primary", key=f"{session_key}_conferma"):
        utente_id = auth.current_user_id(conn)
        rating_engine.register_match(
            conn,
            anteprima["data_partita"],
            anteprima["modalita"],
            anteprima["risultato_set"],
            anteprima["squadra_vincente"],
            anteprima["squadra_a"],
            anteprima["squadra_b"],
            utente_id,
            sessione_id=sessione_id,
        )
        del st.session_state[session_key]
        if set_live_key:
            reset_set_live(set_live_key)
        if on_success:
            on_success()
        imposta_messaggio_pendente("✅ Partita registrata.")
        st.rerun()

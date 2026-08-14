"""Blocchi di UI Streamlit condivisi tra le pagine che registrano una
partita (Nuova partita e Sessione di gioco), per non duplicare la logica di
validazione/anteprima/conferma."""

import streamlit as st

from rokkini import auth, rating_engine
from rokkini.elo import PlayerPreMatch, compute_match_deltas


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
) -> None:
    """Se `calcola` è True (bottone premuto in questo run), calcola i delta
    e li salva in sessione. In ogni caso, se una anteprima è presente in
    sessione, la mostra con il bottone di conferma che registra la partita."""
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
        deltas_a, deltas_b = compute_match_deltas(team_a, team_b, squadra_vincente)
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
        )
        del st.session_state[session_key]
        st.success("Partita registrata.")
        st.rerun()

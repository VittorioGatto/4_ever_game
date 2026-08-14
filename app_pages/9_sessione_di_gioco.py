from datetime import date

import streamlit as st

from rokkini import auth, db, stats, ui_common
from rokkini.matchmaking import (
    GiocatorePerMatchmaking,
    genera_combinazioni_bilanciate,
    genera_fixture_girone,
    genera_squadre_multiple,
    numero_partite_per_girone_equo,
    prossima_partita_girone_rotante,
)

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🎮 Sessione di gioco")

giocatori = [g for g in db.fetch_giocatori(conn) if not g["sospeso"]]
if len(giocatori) < 6:
    st.warning("Servono almeno 6 giocatori non sospesi nel sistema per usare questa pagina.")
    st.stop()

nomi_per_id = {g["id"]: g["nome"] for g in giocatori}
giocatori_per_id = {g["id"]: g for g in giocatori}


def _etichetta(giocatore_id: int) -> str:
    return nomi_per_id[giocatore_id]


sessione = db.fetch_sessione_attiva(conn)

# --- nessuna sessione in corso: form per aprirne una ------------------------

if sessione is None:
    st.caption(
        "Nessuna sessione in corso. Seleziona chi c'è oggi e premi 'Inizia sessione': da quel "
        "momento sarà visibile pubblicamente (senza bisogno di login) nella pagina "
        "'Sessioni attive', e potrai registrare più partite di fila sullo stesso gruppo — "
        "una partita semplice o un torneo a girone."
    )
    pool_iniziale = st.multiselect(
        "Giocatori presenti oggi",
        options=list(nomi_per_id.keys()),
        format_func=_etichetta,
        key="nuova_sessione_pool",
    )
    if len(pool_iniziale) < 6:
        st.info("Seleziona almeno 6 giocatori per iniziare.")
    if st.button("▶️ Inizia sessione", disabled=len(pool_iniziale) < 6):
        utente_id = auth.current_user_id(conn)
        nuova_sessione_id = db.insert_sessione(conn, utente_id)
        db.set_partecipanti_sessione(conn, nuova_sessione_id, pool_iniziale)
        st.rerun()
    st.stop()

# --- sessione attiva ---------------------------------------------------------

sessione_id = sessione["id"]
st.success(f"🟢 Sessione in corso, iniziata alle {sessione['iniziata_at']}.")
if st.button("⏹️ Termina sessione"):
    db.termina_sessione(conn, sessione_id)
    st.rerun()

partecipanti_attuali = {g["id"] for g in db.fetch_partecipanti_sessione(conn, sessione_id)}
pool = st.multiselect(
    "Giocatori presenti (modifica se qualcuno arriva o se ne va)",
    options=list(nomi_per_id.keys()),
    default=list(partecipanti_attuali),
    format_func=_etichetta,
    key="sessione_pool_attiva",
)
if set(pool) != partecipanti_attuali:
    db.set_partecipanti_sessione(conn, sessione_id, pool)
    st.rerun()

if len(pool) < 6:
    st.info("Servono almeno 6 giocatori presenti per generare una partita.")
    st.stop()

st.divider()
modo = st.radio("Modalità sessione", ["Partita semplice", "Torneo"], horizontal=True, key="sessione_modo")

# ==============================================================================
# PARTITA SEMPLICE
# ==============================================================================

if modo == "Partita semplice":
    modalita = st.radio("Modalità", ["3v3", "4v4"], horizontal=True, key="sessione_modalita")
    dimensione = 3 if modalita == "3v3" else 4

    # poda difensiva: se il pool si e' ristretto, i valori gia' selezionati che
    # non ci sono piu' romperebbero il multiselect (il suo valore deve restare
    # un sottoinsieme delle opzioni)
    st.session_state["sessione_chi_gioca"] = [
        gid for gid in st.session_state.get("sessione_chi_gioca", []) if gid in pool
    ]

    chi_gioca = st.multiselect(
        "Chi gioca questa partita (dal gruppo presente)",
        options=pool,
        format_func=_etichetta,
        key="sessione_chi_gioca",
    )

    # se cambia il gruppo che gioca, le proposte e le squadre gia' scelte non
    # sono piu' valide (potrebbero riferirsi a giocatori non piu' selezionati)
    if st.session_state.get("sessione_chi_gioca_precedente") != chi_gioca:
        st.session_state.pop("sessione_proposte", None)
        st.session_state.pop("sessione_proposta_applicata", None)
        st.session_state["sessione_squadra_a"] = []
        st.session_state["sessione_squadra_b"] = []
        st.session_state["sessione_chi_gioca_precedente"] = chi_gioca

    if len(chi_gioca) != dimensione * 2:
        st.info(f"Seleziona esattamente {dimensione * 2} giocatori per generare le squadre.")
        st.stop()

    if st.button("🎲 Suggerisci squadre bilanciate"):
        candidati = [
            GiocatorePerMatchmaking(gid, giocatori_per_id[gid]["rk_attuale"]) for gid in chi_gioca
        ]
        st.session_state["sessione_proposte"] = genera_combinazioni_bilanciate(
            candidati, dimensione, n_proposte=3
        )
        st.session_state.pop("sessione_proposta_applicata", None)

    proposte = st.session_state.get("sessione_proposte")
    if proposte:
        etichette = [
            f"Proposta {i + 1} — media {p.media_a:.0f} vs {p.media_b:.0f} (Δ{p.differenza:.0f}) · "
            f"A: {', '.join(nomi_per_id[g] for g in p.squadra_a)} · "
            f"B: {', '.join(nomi_per_id[g] for g in p.squadra_b)}"
            for i, p in enumerate(proposte)
        ]
        scelta_idx = st.radio(
            "Proposte bilanciate", range(len(proposte)), format_func=lambda i: etichette[i]
        )
        if st.session_state.get("sessione_proposta_applicata") != scelta_idx:
            st.session_state["sessione_squadra_a"] = proposte[scelta_idx].squadra_a
            st.session_state["sessione_squadra_b"] = proposte[scelta_idx].squadra_b
            st.session_state["sessione_proposta_applicata"] = scelta_idx

    st.caption("Puoi modificare le squadre a mano prima di confermare (es. se qualcuno preferisce un'altra formazione).")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Squadra A**")
        opzioni_a = [
            gid for gid in chi_gioca if gid not in st.session_state.get("sessione_squadra_b", [])
        ]
        squadra_a = st.multiselect(
            "Squadra A",
            options=opzioni_a,
            format_func=_etichetta,
            key="sessione_squadra_a",
            label_visibility="collapsed",
        )
    with col_b:
        st.markdown("**Squadra B**")
        opzioni_b = [gid for gid in chi_gioca if gid not in squadra_a]
        squadra_b = st.multiselect(
            "Squadra B",
            options=opzioni_b,
            format_func=_etichetta,
            key="sessione_squadra_b",
            label_visibility="collapsed",
        )

    data_partita = st.date_input("Data partita", value=date.today(), key="sessione_data_partita")

    errori = ui_common.valida_squadre_ui(modalita, squadra_a, squadra_b)
    for e in errori:
        st.error(e)

    if not errori:
        esito = ui_common.registra_set_live("sessione_set_live")
        if esito:
            risultato_set, _ = esito
            ui_common.gestisci_anteprima_e_conferma(
                conn,
                calcola=True,
                nomi_per_id=nomi_per_id,
                giocatori_per_id=giocatori_per_id,
                data_partita=data_partita.isoformat(),
                modalita=modalita,
                risultato_set=risultato_set,
                squadra_a=squadra_a,
                squadra_b=squadra_b,
                session_key="sessione_anteprima_partita",
                sessione_id=sessione_id,
                set_live_key="sessione_set_live",
            )

# ==============================================================================
# TORNEO (girone all'italiana)
# ==============================================================================

else:
    modalita_torneo = st.radio("Modalità", ["3v3", "4v4"], horizontal=True, key="torneo_modalita")
    dimensione_torneo = 3 if modalita_torneo == "3v3" else 4

    if len(pool) < dimensione_torneo * 2:
        st.warning(
            f"Servono almeno {dimensione_torneo * 2} giocatori presenti per un torneo in "
            f"modalità {modalita_torneo}."
        )
        st.stop()

    squadre_fisse = len(pool) % dimensione_torneo == 0

    if st.button("🎲 Genera/rigenera squadre del torneo"):
        st.session_state["torneo_squadre_fisse"] = squadre_fisse
        st.session_state["torneo_dimensione"] = dimensione_torneo
        if squadre_fisse:
            candidati = [
                GiocatorePerMatchmaking(gid, giocatori_per_id[gid]["rk_attuale"]) for gid in pool
            ]
            squadre_generate = genera_squadre_multiple(candidati, dimensione_torneo)
            st.session_state["torneo_squadre"] = squadre_generate
            st.session_state["torneo_fixture"] = genera_fixture_girone(len(squadre_generate))
            st.session_state["torneo_giocate"] = set()
        else:
            st.session_state["torneo_conteggio_partite"] = dict.fromkeys(pool, 0)
            st.session_state["torneo_partite_target"] = numero_partite_per_girone_equo(
                len(pool), dimensione_torneo
            )
            st.session_state["torneo_partite_completate"] = 0
        st.rerun()

    if "torneo_squadre_fisse" not in st.session_state:
        st.info("Genera le squadre per iniziare il torneo.")
        st.stop()

    dimensione_corrente = st.session_state["torneo_dimensione"]

    # ------------------------------------------------------------------------
    # caso A: numero di giocatori multiplo della dimensione -> squadre fisse
    # per tutto il girone, come un torneo "vero" (nessuna ricomposizione)
    # ------------------------------------------------------------------------
    if st.session_state["torneo_squadre_fisse"]:
        squadre = st.session_state.get("torneo_squadre")
        if not squadre:
            st.info("Genera le squadre per iniziare il torneo.")
            st.stop()

        st.subheader("Squadre del girone")
        for i, squadra in enumerate(squadre):
            media = sum(giocatori_per_id[gid]["rk_attuale"] for gid in squadra) / len(squadra)
            st.write(f"**Squadra {i + 1}** (media {media:.0f}): {', '.join(nomi_per_id[gid] for gid in squadra)}")

        fixture = st.session_state["torneo_fixture"]
        giocate = st.session_state["torneo_giocate"]
        st.write(f"Partite del girone: {len(giocate)}/{len(fixture)} giocate")

        rimanenti_idx = [i for i in range(len(fixture)) if i not in giocate]
        if not rimanenti_idx:
            st.success("🏆 Girone completato! Tutte le partite sono state giocate.")
            st.stop()

        prossima_idx = rimanenti_idx[0]
        squadra_1_idx, squadra_2_idx = fixture[prossima_idx]
        st.divider()
        st.subheader(f"Prossima partita: Squadra {squadra_1_idx + 1} vs Squadra {squadra_2_idx + 1}")

        key_a, key_b = f"torneo_squadra_a_{prossima_idx}", f"torneo_squadra_b_{prossima_idx}"
        if key_a not in st.session_state:
            st.session_state[key_a] = [gid for gid in squadre[squadra_1_idx] if gid in pool]
            st.session_state[key_b] = [gid for gid in squadre[squadra_2_idx] if gid in pool]
        # poda difensiva: se il pool e' cambiato dopo aver generato le squadre,
        # un giocatore preselezionato potrebbe non essere piu' tra le opzioni
        st.session_state[key_a] = [gid for gid in st.session_state[key_a] if gid in pool]
        st.session_state[key_b] = [gid for gid in st.session_state[key_b] if gid in pool]

        st.caption("Puoi modificare le squadre di questa partita a mano (es. se qualcuno è andato via).")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Squadra A**")
            opzioni_a = [gid for gid in pool if gid not in st.session_state.get(key_b, [])]
            squadra_a = st.multiselect(
                "Squadra A", options=opzioni_a, format_func=_etichetta, key=key_a,
                label_visibility="collapsed",
            )
        with col_b:
            st.markdown("**Squadra B**")
            opzioni_b = [gid for gid in pool if gid not in squadra_a]
            squadra_b = st.multiselect(
                "Squadra B", options=opzioni_b, format_func=_etichetta, key=key_b,
                label_visibility="collapsed",
            )

        data_partita_torneo = st.date_input(
            "Data partita", value=date.today(), key=f"torneo_data_{prossima_idx}"
        )

        errori = ui_common.valida_squadre_ui(modalita_torneo, squadra_a, squadra_b)
        for e in errori:
            st.error(e)

        if not errori:

            def _segna_fixture_giocata(idx: int = prossima_idx) -> None:
                st.session_state["torneo_giocate"].add(idx)

            esito = ui_common.registra_set_live(f"torneo_set_live_{prossima_idx}")
            if esito:
                risultato_set, _ = esito
                ui_common.gestisci_anteprima_e_conferma(
                    conn,
                    calcola=True,
                    nomi_per_id=nomi_per_id,
                    giocatori_per_id=giocatori_per_id,
                    data_partita=data_partita_torneo.isoformat(),
                    modalita=modalita_torneo,
                    risultato_set=risultato_set,
                    squadra_a=squadra_a,
                    squadra_b=squadra_b,
                    session_key=f"torneo_anteprima_{prossima_idx}",
                    sessione_id=sessione_id,
                    set_live_key=f"torneo_set_live_{prossima_idx}",
                    on_success=_segna_fixture_giocata,
                )

    # ------------------------------------------------------------------------
    # caso B: numero di giocatori NON multiplo -> nessuna squadra fissa
    # possibile senza escludere qualcuno per tutto il girone. Le squadre si
    # ricompongono partita per partita, dando sempre priorità a chi ha
    # giocato meno finora, cosi' che alla fine tutti abbiano giocato lo
    # stesso numero di partite (vedi rokkini.matchmaking).
    # ------------------------------------------------------------------------
    else:
        target = st.session_state["torneo_partite_target"]
        completate = st.session_state["torneo_partite_completate"]
        partite_a_testa = target * dimensione_corrente * 2 // len(pool)
        st.info(
            f"{len(pool)} giocatori non sono multiplo di {dimensione_corrente}: le squadre si "
            f"ricompongono a ogni partita, dando priorità a chi ha giocato meno, così tutti "
            f"finiscono per giocare {partite_a_testa} partite ({target} partite in totale)."
        )
        st.write(f"Partite del girone: {completate}/{target} giocate")

        if completate >= target:
            st.success("🏆 Girone completato! Tutti hanno giocato lo stesso numero di partite.")
            st.stop()

        conteggio = st.session_state["torneo_conteggio_partite"]
        for gid in pool:  # poda difensiva se il pool e' cambiato dopo la generazione
            conteggio.setdefault(gid, 0)

        candidati = [
            GiocatorePerMatchmaking(gid, giocatori_per_id[gid]["rk_attuale"]) for gid in pool
        ]
        suggerita_a, suggerita_b = prossima_partita_girone_rotante(
            candidati, dimensione_corrente, conteggio
        )

        idx_partita = completate
        key_a, key_b = f"torneo_rot_squadra_a_{idx_partita}", f"torneo_rot_squadra_b_{idx_partita}"
        if key_a not in st.session_state:
            st.session_state[key_a] = suggerita_a
            st.session_state[key_b] = suggerita_b
        st.session_state[key_a] = [gid for gid in st.session_state[key_a] if gid in pool]
        st.session_state[key_b] = [gid for gid in st.session_state[key_b] if gid in pool]

        st.divider()
        st.subheader(f"Prossima partita ({completate + 1}/{target})")
        st.caption(
            "Squadre proposte in base a chi ha giocato meno finora. Puoi modificarle a mano "
            "(es. se qualcuno è andato via)."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Squadra A**")
            opzioni_a = [gid for gid in pool if gid not in st.session_state.get(key_b, [])]
            squadra_a = st.multiselect(
                "Squadra A", options=opzioni_a, format_func=_etichetta, key=key_a,
                label_visibility="collapsed",
            )
        with col_b:
            st.markdown("**Squadra B**")
            opzioni_b = [gid for gid in pool if gid not in squadra_a]
            squadra_b = st.multiselect(
                "Squadra B", options=opzioni_b, format_func=_etichetta, key=key_b,
                label_visibility="collapsed",
            )

        data_partita_torneo = st.date_input(
            "Data partita", value=date.today(), key=f"torneo_rot_data_{idx_partita}"
        )

        errori = ui_common.valida_squadre_ui(modalita_torneo, squadra_a, squadra_b)
        for e in errori:
            st.error(e)

        if not errori:

            def _segna_rotazione_giocata(giocatori_partita: tuple = tuple(squadra_a + squadra_b)) -> None:
                for gid in giocatori_partita:
                    st.session_state["torneo_conteggio_partite"][gid] = (
                        st.session_state["torneo_conteggio_partite"].get(gid, 0) + 1
                    )
                st.session_state["torneo_partite_completate"] += 1

            esito = ui_common.registra_set_live(f"torneo_rot_set_live_{idx_partita}")
            if esito:
                risultato_set, _ = esito
                ui_common.gestisci_anteprima_e_conferma(
                    conn,
                    calcola=True,
                    nomi_per_id=nomi_per_id,
                    giocatori_per_id=giocatori_per_id,
                    data_partita=data_partita_torneo.isoformat(),
                    modalita=modalita_torneo,
                    risultato_set=risultato_set,
                    squadra_a=squadra_a,
                    squadra_b=squadra_b,
                    session_key=f"torneo_rot_anteprima_{idx_partita}",
                    sessione_id=sessione_id,
                    set_live_key=f"torneo_rot_set_live_{idx_partita}",
                    on_success=_segna_rotazione_giocata,
                )

# ==============================================================================
# STORICO DELLA SESSIONE
# ==============================================================================

st.divider()
cronologia_sessione = stats.fetch_match_history_sessione(conn, sessione_id)
if cronologia_sessione:
    st.subheader(f"Partite di questa sessione ({len(cronologia_sessione)})")
    for voce in reversed(cronologia_sessione):
        p = voce["partita"]
        vincitrice_a = p["squadra_vincente"] == "A"
        with st.expander(f"{p['modalita']} — {p['risultato_set']}"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Squadra A** {'🏆' if vincitrice_a else ''}")
                for g in voce["squadra_a"]:
                    st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")
            with col_b:
                st.markdown(f"**Squadra B** {'🏆' if not vincitrice_a else ''}")
                for g in voce["squadra_b"]:
                    st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")

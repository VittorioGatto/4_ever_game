from datetime import date

import streamlit as st

from rokkini import auth, db, stats, ui_common
from rokkini.matchmaking import (
    GiocatorePerMatchmaking,
    genera_fixture_girone,
    genera_squadre_multiple,
    numero_partite_per_girone_equo,
    programma_completo_girone_rotante,
)

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🎮 Sessione di gioco")
ui_common.mostra_messaggio_pendente()

giocatori = [g for g in db.fetch_giocatori(conn) if not g["sospeso"]]
if len(giocatori) < 6:
    st.warning("Servono almeno 6 giocatori non sospesi nel sistema per usare questa pagina.")
    st.stop()

nomi_per_id = {g["id"]: g["nome"] for g in giocatori}
giocatori_per_id = {g["id"]: g for g in giocatori}


def _etichetta(giocatore_id: int) -> str:
    return nomi_per_id[giocatore_id]


def _termina_e_pulisci(sessione_id: int) -> None:
    """Termina la sessione e ripulisce dal session_state tutto cio' che si
    riferiva a lei (squadre, fixture, pool selezionato): session_state
    sopravvive alla fine di una sessione (solo l'id sessione nel DB
    cambia), quindi senza questa pulizia la prossima sessione erediterebbe
    squadre/partite/presenti di quella appena terminata, anche se chiusa
    a girone non ancora completo."""
    db.termina_sessione(conn, sessione_id)
    for key in list(st.session_state.keys()):
        if key.startswith("torneo_") or key in ("sessione_pool_attiva", "_persist_torneo_modalita"):
            st.session_state.pop(key, None)


sessione = db.fetch_sessione_attiva(conn)

# --- nessuna sessione in corso: form per aprirne una ------------------------

if sessione is None:
    st.caption(
        "Nessuna sessione in corso. Seleziona chi c'è oggi e premi 'Inizia sessione': da quel "
        "momento sarà visibile pubblicamente (senza bisogno di login) nella pagina "
        "'Sessioni attive', e potrai registrare le partite di questo girone — con soli 6 o 8 "
        "presenti e' semplicemente una partita singola."
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
with st.container(border=True):
    st.success(f"🟢 Sessione in corso, iniziata alle {sessione['iniziata_at']}.")
    if st.button("⏹️ Termina sessione"):
        _termina_e_pulisci(sessione_id)
        st.rerun()

    # poiche' Streamlit "dimentica" lo stato di un widget quando si naviga su
    # un'altra pagina (o si esce e si rientra dall'account: st.session_state
    # riparte vuoto) e si torna indietro, il piano del girone generato in
    # precedenza andrebbe perso — qui lo si ripristina dal DB (dove viene
    # salvato anche per essere visibile pubblicamente in "Sessioni attive")
    # se il session_state locale non ce l'ha piu'.
    if "torneo_squadre_fisse" not in st.session_state:
        _programma_salvato = db.fetch_programma_torneo(conn, sessione_id)
        if _programma_salvato:
            st.session_state["torneo_dimensione"] = _programma_salvato["dimensione"]
            st.session_state["_persist_torneo_modalita"] = (
                "3v3" if _programma_salvato["dimensione"] == 3 else "4v4"
            )
            if _programma_salvato["tipo"] == "fisso":
                st.session_state["torneo_squadre_fisse"] = True
                st.session_state["torneo_squadre"] = _programma_salvato["squadre"]
                st.session_state["torneo_fixture"] = [tuple(p) for p in _programma_salvato["fixture"]]
                st.session_state["torneo_giocate"] = set(_programma_salvato["giocate"])
                # le squadre della fixture in corso possono essere state
                # modificate a mano (es. qualcuno se ne va): senza ripristinare
                # anche questo, un cambio di pagina (o un redeploy) le
                # riporterebbe a quelle generate automaticamente, perdendo la
                # modifica manuale — vedi anche il commento poco sopra.
                override = _programma_salvato.get("override_corrente")
                if override and override["idx"] not in st.session_state["torneo_giocate"]:
                    st.session_state[f"torneo_squadra_a_{override['idx']}"] = override["squadra_a"]
                    st.session_state[f"torneo_squadra_b_{override['idx']}"] = override["squadra_b"]
            else:
                st.session_state["torneo_squadre_fisse"] = False
                st.session_state["torneo_conteggio_partite"] = {
                    int(gid): n for gid, n in _programma_salvato["conteggio"].items()
                }
                st.session_state["torneo_partite_target"] = _programma_salvato["target"]
                st.session_state["torneo_partite_completate"] = _programma_salvato["completate"]
                # stesso discorso del caso "fisso" sopra, per la partita
                # scelta (e le sue squadre, eventualmente modificate a mano)
                # attualmente in corso.
                idx_corrente = _programma_salvato["completate"]
                scelta_salvata = _programma_salvato.get("scelta_idx", 0)
                st.session_state["torneo_rot_scelta"] = scelta_salvata
                st.session_state["torneo_rot_scelta_precedente"] = scelta_salvata
                if "squadra_a_corrente" in _programma_salvato:
                    st.session_state[f"torneo_rot_squadra_a_{idx_corrente}"] = _programma_salvato[
                        "squadra_a_corrente"
                    ]
                    st.session_state[f"torneo_rot_squadra_b_{idx_corrente}"] = _programma_salvato[
                        "squadra_b_corrente"
                    ]

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

st.subheader("🕹️ Nuova partita")

with st.container(border=True):
    ui_common.ripristina_widget_persistente("torneo_modalita")
    modalita_torneo = st.radio("Modalità", ["3v3", "4v4"], horizontal=True, key="torneo_modalita")
    ui_common.salva_widget_persistente("torneo_modalita")
    dimensione_torneo = 3 if modalita_torneo == "3v3" else 4

    if len(pool) < dimensione_torneo * 2:
        st.warning(
            f"Servono almeno {dimensione_torneo * 2} giocatori presenti per giocare in "
            f"modalità {modalita_torneo}."
        )
        st.stop()

    squadre_fisse = len(pool) % dimensione_torneo == 0

    if st.button("🎲 Genera/rigenera squadre"):
        st.session_state["torneo_squadre_fisse"] = squadre_fisse
        st.session_state["torneo_dimensione"] = dimensione_torneo
        if squadre_fisse:
            candidati = [
                GiocatorePerMatchmaking(gid, giocatori_per_id[gid]["rk_attuale"]) for gid in pool
            ]
            squadre_generate = genera_squadre_multiple(candidati, dimensione_torneo)
            fixture_generata = genera_fixture_girone(len(squadre_generate))
            st.session_state["torneo_squadre"] = squadre_generate
            st.session_state["torneo_fixture"] = fixture_generata
            st.session_state["torneo_giocate"] = set()
            db.set_programma_torneo(
                conn,
                sessione_id,
                {
                    "tipo": "fisso",
                    "dimensione": dimensione_torneo,
                    "squadre": squadre_generate,
                    "fixture": [list(coppia) for coppia in fixture_generata],
                    "giocate": [],
                },
            )
        else:
            target_generato = numero_partite_per_girone_equo(len(pool), dimensione_torneo)
            st.session_state["torneo_conteggio_partite"] = dict.fromkeys(pool, 0)
            st.session_state["torneo_partite_target"] = target_generato
            st.session_state["torneo_partite_completate"] = 0
            db.set_programma_torneo(
                conn,
                sessione_id,
                {
                    "tipo": "rotante",
                    "dimensione": dimensione_torneo,
                    "conteggio": dict.fromkeys((str(gid) for gid in pool), 0),
                    "target": target_generato,
                    "completate": 0,
                },
            )
        st.rerun()

    if "torneo_squadre_fisse" not in st.session_state:
        st.info("Genera le squadre per iniziare (con 6 o 8 presenti sarà una singola partita).")
        st.stop()

    dimensione_corrente = st.session_state["torneo_dimensione"]

    # ------------------------------------------------------------------------
    # caso A: numero di giocatori multiplo della dimensione -> squadre fisse
    # per tutto il girone (se sono esattamente 2 squadre, il girone e' una
    # singola partita: stessa logica, nessuna distinzione necessaria)
    # ------------------------------------------------------------------------
    if st.session_state["torneo_squadre_fisse"]:
        squadre = st.session_state.get("torneo_squadre")
        if not squadre:
            st.info("Genera le squadre per iniziare.")
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

        def _etichetta_fixture(idx: int) -> str:
            a, b = fixture[idx]
            return f"Partita {idx + 1}: Squadra {a + 1} vs Squadra {b + 1}"

        st.divider()
        prossima_idx = st.selectbox(
            "Quale partita del girone giochi ora?",
            options=rimanenti_idx,
            format_func=_etichetta_fixture,
            key="torneo_prossima_scelta",
        )
        squadra_1_idx, squadra_2_idx = fixture[prossima_idx]
        st.subheader(f"Partita: Squadra {squadra_1_idx + 1} vs Squadra {squadra_2_idx + 1}")

        def _programma_fisso(override_corrente: dict | None = None) -> dict:
            programma = {
                "tipo": "fisso",
                "dimensione": dimensione_corrente,
                "squadre": squadre,
                "fixture": [list(coppia) for coppia in fixture],
                "giocate": sorted(st.session_state["torneo_giocate"]),
            }
            if override_corrente is not None:
                programma["override_corrente"] = override_corrente
            return programma

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

        # persiste la selezione corrente (anche se modificata a mano) a ogni
        # rerun, cosi' un cambio di pagina o un redeploy non la fa tornare a
        # quella generata automaticamente — vedi il ripristino piu' sopra.
        db.set_programma_torneo(
            conn,
            sessione_id,
            _programma_fisso({"idx": prossima_idx, "squadra_a": list(squadra_a), "squadra_b": list(squadra_b)}),
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
                st.session_state.pop("torneo_prossima_scelta", None)
                db.set_programma_torneo(conn, sessione_id, _programma_fisso())
                if len(st.session_state["torneo_giocate"]) >= len(fixture):
                    _termina_e_pulisci(sessione_id)

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

        # tutte le partite rimanenti proiettate da qui, non solo la prossima:
        # cosi' si puo' scegliere quale giocare ora, come nel girone a
        # squadre fisse — e' comunque solo una proposta, non un impegno: se
        # il pool cambia o una squadra viene modificata a mano, la proiezione
        # da quel punto in poi cambia di conseguenza al prossimo rerun.
        partite_rimanenti = target - completate
        partite_previste = programma_completo_girone_rotante(
            candidati, dimensione_corrente, conteggio, partite_rimanenti
        )

        def _etichetta_partita_rot(i: int) -> str:
            p_a, p_b = partite_previste[i]
            nomi_a = ", ".join(nomi_per_id[gid] for gid in p_a)
            nomi_b = ", ".join(nomi_per_id[gid] for gid in p_b)
            return f"Partita {completate + i + 1}: {nomi_a} vs {nomi_b}"

        st.divider()
        # poda difensiva: se una partita precedente ha ridotto il numero di
        # partite rimanenti, una scelta salvata potrebbe non essere piu' valida
        if st.session_state.get("torneo_rot_scelta", 0) >= len(partite_previste):
            st.session_state["torneo_rot_scelta"] = 0
        scelta_idx = st.selectbox(
            "Quale partita giochi ora?",
            options=list(range(len(partite_previste))),
            format_func=_etichetta_partita_rot,
            key="torneo_rot_scelta",
        )
        suggerita_a, suggerita_b = partite_previste[scelta_idx]

        idx_partita = completate
        key_a, key_b = f"torneo_rot_squadra_a_{idx_partita}", f"torneo_rot_squadra_b_{idx_partita}"
        # se e' stata scelta una partita diversa da quella proposta finora,
        # le squadre precompilate vanno riprese da capo (altrimenti mostrerebbero
        # ancora quelle della scelta precedente, eventualmente modificate a mano)
        if key_a not in st.session_state or st.session_state.get("torneo_rot_scelta_precedente") != scelta_idx:
            st.session_state[key_a] = suggerita_a
            st.session_state[key_b] = suggerita_b
        st.session_state["torneo_rot_scelta_precedente"] = scelta_idx
        st.session_state[key_a] = [gid for gid in st.session_state[key_a] if gid in pool]
        st.session_state[key_b] = [gid for gid in st.session_state[key_b] if gid in pool]

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

        with st.container(border=True):
            st.markdown("**Programma previsto del girone**")
            for i, (p_a, p_b) in enumerate(partite_previste):
                nomi_a = ", ".join(nomi_per_id[gid] for gid in p_a)
                nomi_b = ", ".join(nomi_per_id[gid] for gid in p_b)
                prefisso = "▶️ " if i == scelta_idx else ""
                st.caption(f"{prefisso}Partita {completate + i + 1}: {nomi_a} vs {nomi_b}")

        def _programma_rotante(**extra) -> dict:
            programma = {
                "tipo": "rotante",
                "dimensione": dimensione_corrente,
                "conteggio": {str(gid): n for gid, n in conteggio.items()},
                "target": target,
                "completate": st.session_state["torneo_partite_completate"],
            }
            programma.update(extra)
            return programma

        # persiste la scelta corrente (partita scelta + squadre, anche se
        # modificate a mano) a ogni rerun, cosi' un cambio di pagina o un
        # redeploy non la fa tornare a quella proposta di default.
        db.set_programma_torneo(
            conn,
            sessione_id,
            _programma_rotante(
                partite_previste=[[list(a), list(b)] for a, b in partite_previste],
                scelta_idx=scelta_idx,
                squadra_a_corrente=list(squadra_a),
                squadra_b_corrente=list(squadra_b),
            ),
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
                st.session_state.pop("torneo_rot_scelta", None)
                st.session_state.pop("torneo_rot_scelta_precedente", None)
                db.set_programma_torneo(conn, sessione_id, _programma_rotante())
                if st.session_state["torneo_partite_completate"] >= target:
                    _termina_e_pulisci(sessione_id)

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
    with st.container(border=True):
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

import streamlit as st

from rokkini import auth, db, rating_engine

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("✏️ Correggi / annulla partita")

partite = db.fetch_partite_non_annullate(conn)
if not partite:
    st.info("Nessuna partita da correggere.")
    st.stop()

giocatori = db.fetch_giocatori(conn)
nomi_per_id = {g["id"]: g["nome"] for g in giocatori}


def _etichetta_partita(p: dict) -> str:
    partecipazioni = db.fetch_partecipazioni(conn, p["id"])
    squadra_a = ", ".join(nomi_per_id.get(x["giocatore_id"], "?") for x in partecipazioni if x["squadra"] == "A")
    squadra_b = ", ".join(nomi_per_id.get(x["giocatore_id"], "?") for x in partecipazioni if x["squadra"] == "B")
    return f"{p['data_partita']} — {squadra_a} vs {squadra_b} ({p['risultato_set']})"


partite_per_id = {p["id"]: p for p in partite}
partita_id = st.selectbox(
    "Seleziona partita",
    options=[p["id"] for p in reversed(partite)],
    format_func=lambda pid: _etichetta_partita(partite_per_id[pid]),
)
partita = partite_per_id[partita_id]
posizione = next(i for i, p in enumerate(partite) if p["id"] == partita_id)
n_successive = len(partite) - posizione - 1

partecipazioni = db.fetch_partecipazioni(conn, partita_id)
squadra_a_ids = [p["giocatore_id"] for p in partecipazioni if p["squadra"] == "A"]
squadra_b_ids = [p["giocatore_id"] for p in partecipazioni if p["squadra"] == "B"]
variazioni = {v["giocatore_id"]: v for v in db.fetch_variazioni_per_partita(conn, partita_id)}

st.subheader("Dettagli partita")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown(f"**Squadra A** {'🏆' if partita['squadra_vincente'] == 'A' else ''}")
    for gid in squadra_a_ids:
        v = variazioni.get(gid)
        st.write(f"{nomi_per_id.get(gid, '?')} — {v['delta']:+d} Rk" if v else nomi_per_id.get(gid, "?"))
with col_b:
    st.markdown(f"**Squadra B** {'🏆' if partita['squadra_vincente'] == 'B' else ''}")
    for gid in squadra_b_ids:
        v = variazioni.get(gid)
        st.write(f"{nomi_per_id.get(gid, '?')} — {v['delta']:+d} Rk" if v else nomi_per_id.get(gid, "?"))

if n_successive:
    st.warning(
        f"Questa partita ha {n_successive} partite successive nello storico. "
        "Annullarla o correggerla ricalcolera' automaticamente tutte le partite da questo punto in poi."
    )

tab_annulla, tab_correggi = st.tabs(["Annulla partita", "Correggi partita"])

with tab_annulla:
    motivo = st.text_input("Motivo dell'annullamento", key="motivo_annulla")
    conferma = st.checkbox(
        f"Confermo: capisco che {n_successive} partite successive verranno ricalcolate.",
        key="conferma_annulla",
        disabled=n_successive == 0,
        value=n_successive == 0,
    )
    if st.button("🗑️ Annulla partita", type="primary", disabled=not motivo.strip() or not conferma):
        rk_prima = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
        utente_id = auth.current_user_id(conn)
        rating_engine.void_match(conn, partita_id, utente_id, motivo.strip())
        rk_dopo = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
        cambiati = [gid for gid in rk_prima if rk_prima[gid] != rk_dopo.get(gid)]
        st.success(f"Partita annullata. {len(cambiati)} giocatori hanno un Rk aggiornato.")
        if cambiati:
            st.table(
                {
                    "Giocatore": [nomi_per_id.get(gid, "?") for gid in cambiati],
                    "Rk prima": [rk_prima[gid] for gid in cambiati],
                    "Rk dopo": [rk_dopo[gid] for gid in cambiati],
                }
            )

with tab_correggi:
    st.caption("La data della partita non e' modificabile da qui: resta la stessa per non alterare l'ordine cronologico.")
    modalita = st.radio(
        "Modalità", ["3v3", "4v4"], horizontal=True, index=0 if partita["modalita"] == "3v3" else 1, key="edit_modalita"
    )
    dimensione = 3 if modalita == "3v3" else 4

    tutti_i_giocatori = [g for g in giocatori if not g["sospeso"]]
    col_a, col_b = st.columns(2)
    with col_a:
        nuova_squadra_a = st.multiselect(
            "Squadra A",
            options=[g["id"] for g in tutti_i_giocatori],
            default=[gid for gid in squadra_a_ids if gid in {g["id"] for g in tutti_i_giocatori}],
            format_func=lambda gid: nomi_per_id.get(gid, "?"),
            key="edit_squadra_a",
        )
    with col_b:
        nuova_squadra_b = st.multiselect(
            "Squadra B",
            options=[g["id"] for g in tutti_i_giocatori],
            default=[gid for gid in squadra_b_ids if gid in {g["id"] for g in tutti_i_giocatori}],
            format_func=lambda gid: nomi_per_id.get(gid, "?"),
            key="edit_squadra_b",
        )
    risultato_set = st.radio(
        "Risultato set (Squadra A - Squadra B)",
        ["2-0", "2-1", "1-2", "0-2"],
        horizontal=True,
        index=["2-0", "2-1", "1-2", "0-2"].index(partita["risultato_set"]),
        key="edit_risultato",
    )

    errori = []
    if len(nuova_squadra_a) != dimensione or len(nuova_squadra_b) != dimensione:
        errori.append(f"Servono esattamente {dimensione} giocatori per squadra in modalità {modalita}.")
    if set(nuova_squadra_a) & set(nuova_squadra_b):
        errori.append("Un giocatore non può stare in entrambe le squadre.")
    for e in errori:
        st.error(e)

    if st.button("💾 Salva correzione", type="primary", disabled=bool(errori)):
        rk_prima = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
        utente_id = auth.current_user_id(conn)
        squadra_vincente = "A" if risultato_set in ("2-0", "2-1") else "B"
        rating_engine.edit_match(
            conn,
            partita_id,
            modalita,
            risultato_set,
            squadra_vincente,
            nuova_squadra_a,
            nuova_squadra_b,
            utente_id,
        )
        rk_dopo = {g["id"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
        cambiati = [gid for gid in rk_prima if rk_prima[gid] != rk_dopo.get(gid)]
        st.success(f"Partita corretta. {len(cambiati)} giocatori hanno un Rk aggiornato.")
        if cambiati:
            st.table(
                {
                    "Giocatore": [nomi_per_id.get(gid, "?") for gid in cambiati],
                    "Rk prima": [rk_prima[gid] for gid in cambiati],
                    "Rk dopo": [rk_dopo[gid] for gid in cambiati],
                }
            )

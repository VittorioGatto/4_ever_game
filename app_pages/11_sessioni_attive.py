import streamlit as st

from rokkini import db, stats

conn = db.get_connection()

st.title("🟢 Sessioni attive")

sessione = db.fetch_sessione_attiva(conn)
if sessione is None:
    st.info("Nessuna sessione di gioco in corso al momento.")
    st.stop()

st.success(f"Sessione in corso, iniziata alle {sessione['iniziata_at']}.")

partecipanti = db.fetch_partecipanti_sessione(conn, sessione["id"])
classifica_sessione = {
    r["nome"]: r for r in stats.fetch_classifica_sessione(conn, sessione["id"])
}

with st.container(border=True):
    st.subheader(f"🏆 Classifica della sessione — presenti ({len(partecipanti)})")
    righe = [
        {
            "Giocatore": g["nome"],
            "Rk guadagnati oggi": classifica_sessione.get(g["nome"], {}).get("rk_sessione", 0),
            "Rk totale attuale": g["rk_attuale"],
        }
        for g in partecipanti
    ]
    righe.sort(key=lambda r: r["Rk guadagnati oggi"], reverse=True)
    st.dataframe(righe, hide_index=True, width="stretch")

nomi_per_id = {g["id"]: g["nome"] for g in partecipanti}
programma = db.fetch_programma_torneo(conn, sessione["id"])
# in ordine cronologico (piu' vecchia prima): per le partite del torneo,
# combacia con l'ordine di gioco del girone (fisso: ordine di fixture;
# rotante: una alla volta), quindi la partita i-esima del girone e' la
# i-esima di questa lista.
cronologia = stats.fetch_match_history_sessione(conn, sessione["id"])


def _espandi_partita(voce: dict, etichetta: str | None = None) -> None:
    p = voce["partita"]
    vincitrice_a = p["squadra_vincente"] == "A"
    titolo = f"✅ {etichetta} — {p['risultato_set']}" if etichetta else f"{p['modalita']} — {p['risultato_set']}"
    with st.expander(titolo):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Squadra A** {'🏆' if vincitrice_a else ''}")
            for g in voce["squadra_a"]:
                st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")
        with col_b:
            st.markdown(f"**Squadra B** {'🏆' if not vincitrice_a else ''}")
            for g in voce["squadra_b"]:
                st.write(f"{g['nome']}  {'+' if g['delta'] >= 0 else ''}{g['delta']} Rk")


with st.container(border=True):
    st.subheader("🏐 Partite")

    if programma and programma["tipo"] == "fisso":
        for i, squadra in enumerate(programma["squadre"]):
            nomi_squadra = ", ".join(nomi_per_id.get(gid, "?") for gid in squadra)
            st.write(f"**Squadra {i + 1}**: {nomi_squadra}")
        giocate = set(programma["giocate"])
        st.caption(f"Partite del girone: {len(giocate)}/{len(programma['fixture'])} giocate")
        for idx, (s1, s2) in enumerate(programma["fixture"]):
            etichetta = f"Squadra {s1 + 1} vs Squadra {s2 + 1}"
            if idx in giocate and idx < len(cronologia):
                _espandi_partita(cronologia[idx], etichetta)
            else:
                st.write(f"⏳ {etichetta}")

    elif programma and programma["tipo"] == "rotante":
        target = programma["target"]
        completate = programma["completate"]
        dimensione = programma["dimensione"]
        partite_a_testa = target * dimensione * 2 // max(len(programma["conteggio"]), 1)
        st.caption(
            f"Girone a squadre variabili: {completate}/{target} partite giocate, ognuno "
            f"finirà per giocarne {partite_a_testa}. Le squadre si ricompongono a ogni "
            f"partita in base a chi ha giocato meno, quindi non sono note in anticipo."
        )
        partite_previste = programma.get("partite_previste", [])
        for idx in range(target):
            etichetta = f"Partita {idx + 1}"
            if idx < completate:
                if idx < len(cronologia):
                    _espandi_partita(cronologia[idx], etichetta)
                else:
                    st.write(f"✅ {etichetta}")
                continue
            i_previsione = idx - completate
            if i_previsione < len(partite_previste):
                p_a, p_b = partite_previste[i_previsione]
                nomi_a = ", ".join(nomi_per_id.get(gid, "?") for gid in p_a)
                nomi_b = ", ".join(nomi_per_id.get(gid, "?") for gid in p_b)
                st.write(f"⏳ {etichetta} — previsione: {nomi_a} vs {nomi_b} (può cambiare)")
            else:
                st.write(f"⏳ {etichetta} — squadre da definire")

    elif not cronologia:
        st.caption("Nessuna partita ancora giocata in questa sessione.")
    else:
        for voce in reversed(cronologia):
            _espandi_partita(voce)

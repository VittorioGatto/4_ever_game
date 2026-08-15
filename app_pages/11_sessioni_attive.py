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
if programma:
    with st.container(border=True):
        st.subheader("🏐 Programma del torneo")
        if programma["tipo"] == "fisso":
            for i, squadra in enumerate(programma["squadre"]):
                nomi_squadra = ", ".join(nomi_per_id.get(gid, "?") for gid in squadra)
                st.write(f"**Squadra {i + 1}**: {nomi_squadra}")
            giocate = set(programma["giocate"])
            st.caption(f"Partite del girone: {len(giocate)}/{len(programma['fixture'])} giocate")
            for idx, (s1, s2) in enumerate(programma["fixture"]):
                simbolo = "✅" if idx in giocate else "⏳"
                st.write(f"{simbolo} Squadra {s1 + 1} vs Squadra {s2 + 1}")
        else:
            target = programma["target"]
            completate = programma["completate"]
            dimensione = programma["dimensione"]
            partite_a_testa = target * dimensione * 2 // max(len(programma["conteggio"]), 1)
            st.caption(
                f"Girone a squadre variabili: {completate}/{target} partite giocate, ognuno "
                f"finirà per giocarne {partite_a_testa}. Le squadre si ricompongono a ogni "
                f"partita in base a chi ha giocato meno, quindi non sono note in anticipo."
            )
            prossima_a = programma.get("prossima_a")
            prossima_b = programma.get("prossima_b")
            for idx in range(target):
                if idx < completate:
                    st.write(f"✅ Partita {idx + 1}")
                elif idx == completate and prossima_a and prossima_b:
                    nomi_a = ", ".join(nomi_per_id.get(gid, "?") for gid in prossima_a)
                    nomi_b = ", ".join(nomi_per_id.get(gid, "?") for gid in prossima_b)
                    st.write(f"⏳ Partita {idx + 1} — proposta: {nomi_a} vs {nomi_b} (può cambiare)")
                else:
                    st.write(f"⏳ Partita {idx + 1} — squadre da definire")

cronologia = stats.fetch_match_history_sessione(conn, sessione["id"])
if not cronologia:
    st.caption("Nessuna partita ancora giocata in questa sessione.")
    st.stop()

with st.container(border=True):
    st.subheader(f"📜 Partite giocate ({len(cronologia)})")
    for voce in reversed(cronologia):
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

from dataclasses import replace

import polars as pl
import streamlit as st

from rokkini import auth, db, rating_engine, ui_common
from rokkini.parametri import fetch_parametri_attivi, salva_parametri_attivi

conn = db.get_connection()
auth.require_role(conn, "super_admin")

st.title("🔮 Simulazione parametri")
ui_common.mostra_messaggio_pendente()

st.caption(
    "Modifica i parametri di calcolo e simula la classifica finale che risulterebbe "
    "rigiocando tutto lo storico partite con questi valori, senza toccare nulla. Se il "
    "risultato convince, puoi applicarlo davvero in fondo alla pagina."
)

parametri_attivi = fetch_parametri_attivi(conn)
fascia_soglia = {nome: soglia for soglia, nome in parametri_attivi.fasce}

st.subheader("Parametri")

col1, col2 = st.columns(2)
with col1:
    rk_iniziale = st.number_input(
        "Rk iniziale", min_value=0, max_value=3000, value=parametri_attivi.rk_iniziale, step=10
    )
    partite_qualificazione = st.number_input(
        "Partite di qualificazione",
        min_value=1,
        max_value=50,
        value=parametri_attivi.partite_qualificazione,
        step=1,
    )
    correttivo_massimo_pct = st.number_input(
        "Correttivo individuale massimo (%)",
        min_value=0.0,
        max_value=50.0,
        value=parametri_attivi.correttivo_massimo * 100,
        step=0.5,
    )
with col2:
    saturazione_sfavorito = st.number_input(
        "Saturazione correttivo — sfavorito (Rk di differenza per il massimo)",
        min_value=1,
        max_value=2000,
        value=parametri_attivi.correttivo_saturazione_sfavorito,
        step=10,
    )
    saturazione_favorito = st.number_input(
        "Saturazione correttivo — favorito (Rk di differenza per il massimo)",
        min_value=1,
        max_value=2000,
        value=parametri_attivi.correttivo_saturazione_favorito,
        step=10,
    )

st.markdown("**Soglie fasce** (H parte sempre da 0)")
col_d, col_c, col_b, col_a = st.columns(4)
with col_d:
    soglia_d = st.number_input("D da", min_value=1, value=fascia_soglia.get("D", 1101), step=10)
with col_c:
    soglia_c = st.number_input("C da", min_value=1, value=fascia_soglia.get("C", 1201), step=10)
with col_b:
    soglia_b = st.number_input("B da", min_value=1, value=fascia_soglia.get("B", 1301), step=10)
with col_a:
    soglia_a = st.number_input("A da", min_value=1, value=fascia_soglia.get("A", 1401), step=10)

fasce_valide = 0 < soglia_d < soglia_c < soglia_b < soglia_a
if not fasce_valide:
    st.error("Le soglie delle fasce devono essere crescenti: D < C < B < A.")

st.markdown("**Coefficiente K** (in base alle partite già disputate prima di quella corrente)")
tabella_k_iniziale = pl.DataFrame(
    [{"partite_giocate_da": soglia, "k": k} for soglia, k in sorted(parametri_attivi.k_factor_soglie)]
)
tabella_k = st.data_editor(
    tabella_k_iniziale,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        "partite_giocate_da": st.column_config.NumberColumn("Partite già disputate da", min_value=0, step=1),
        "k": st.column_config.NumberColumn("K", min_value=1, step=1),
    },
)

righe_k = tabella_k.to_dicts()
k_factor_valido = len(righe_k) > 0 and all(
    riga["partite_giocate_da"] is not None and riga["k"] is not None for riga in righe_k
)
if not k_factor_valido:
    st.error("La tabella del coefficiente K non può avere righe vuote.")

if fasce_valide and k_factor_valido:
    parametri_candidati = replace(
        parametri_attivi,
        rk_iniziale=int(rk_iniziale),
        partite_qualificazione=int(partite_qualificazione),
        fasce=[
            (int(soglia_a), "A"),
            (int(soglia_b), "B"),
            (int(soglia_c), "C"),
            (int(soglia_d), "D"),
            (0, "H"),
        ],
        k_factor_soglie=sorted(
            ((int(riga["partite_giocate_da"]), int(riga["k"])) for riga in righe_k),
            reverse=True,
        ),
        correttivo_massimo=correttivo_massimo_pct / 100,
        correttivo_saturazione_sfavorito=int(saturazione_sfavorito),
        correttivo_saturazione_favorito=int(saturazione_favorito),
    )
else:
    parametri_candidati = None

st.divider()

if st.button("🔮 Simula classifica", type="primary", disabled=parametri_candidati is None):
    st.session_state["_simulazione_risultato"] = rating_engine.simula_classifica(conn, parametri_candidati)
    st.session_state["_simulazione_parametri"] = parametri_candidati

risultato = st.session_state.get("_simulazione_risultato")
if risultato is not None:
    st.subheader("Classifica simulata")
    rk_attuale_per_nome = {g["nome"]: g["rk_attuale"] for g in db.fetch_giocatori(conn)}
    righe_tabella = [
        {
            "Giocatore": r["nome"],
            "Rk attuale": rk_attuale_per_nome.get(r["nome"]),
            "Rk simulato": r["rk_simulato"],
            "Δ": r["rk_simulato"] - rk_attuale_per_nome.get(r["nome"], r["rk_simulato"]),
            "Fascia simulata": r["fascia_simulata"],
            "Partite": r["partite_giocate"],
            "Vittorie": r["vittorie"],
            "Sconfitte": r["sconfitte"],
            "Qualificato": "✅" if r["qualificato"] else "—",
        }
        for r in risultato
    ]
    st.dataframe(righe_tabella, hide_index=True, width="stretch")

    st.divider()
    st.subheader("Applica questi parametri")
    st.error(
        "⚠️ Salva questi parametri come attivi e ricalcola subito Rk/statistiche di tutti "
        "i giocatori su tutto lo storico partite. Non tocca le partite stesse. Scarica un "
        "backup dalla pagina Backup dati prima di procedere, se vuoi poter tornare indietro."
    )
    conferma_applica = st.text_input("Scrivi APPLICA per abilitare", key="conferma_applica_simulazione")
    if st.button("✅ Applica alle partite", type="primary", disabled=conferma_applica != "APPLICA"):
        parametri_da_applicare = st.session_state["_simulazione_parametri"]
        try:
            salva_parametri_attivi(conn, parametri_da_applicare)
            rating_engine.recompute_all(conn, parametri_da_applicare)
            conn.commit()
        except Exception as e:
            conn.rollback()
            st.error(f"Applicazione fallita, nessun dato modificato: {e}")
        else:
            ui_common.imposta_messaggio_pendente("✅ Parametri applicati e Rk ricalcolati.")
            st.session_state.pop("conferma_applica_simulazione", None)
            st.session_state.pop("_simulazione_risultato", None)
            st.session_state.pop("_simulazione_parametri", None)
            st.rerun()

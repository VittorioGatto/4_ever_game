import re
from pathlib import Path

import streamlit as st

st.title("📖 Regolamento")

cartella = Path(__file__).parent.parent


def _sezioni(testo: str) -> tuple[str, list[tuple[str, str]]]:
    """Divide un file di regolamento (sezioni separate da una riga '---')
    nel titolo del documento e nella lista (titolo sezione, corpo)."""
    blocchi = re.split(r"\n\s*---\s*\n", testo.strip())
    titolo_documento, resto_primo_blocco = blocchi[0].split("\n", 1)
    blocchi[0] = resto_primo_blocco
    sezioni = []
    for blocco in blocchi:
        blocco = blocco.strip()
        if not blocco:
            continue
        titolo, _, corpo = blocco.partition("\n")
        sezioni.append((titolo.strip(), corpo.strip()))
    return titolo_documento.strip(), sezioni


def _mostra_regolamento(percorso: Path) -> None:
    titolo_documento, sezioni = _sezioni(percorso.read_text())
    st.caption(titolo_documento)
    for titolo, corpo in sezioni:
        with st.expander(titolo):
            st.markdown(corpo)


with st.container(border=True):
    st.subheader("🏐 Regolamento di gioco")
    _mostra_regolamento(cartella / "regolamento_gioco.txt")

with st.container(border=True):
    st.subheader("🏆 Regolamento punti e Rk")
    _mostra_regolamento(cartella / "regolamento_punti.txt")

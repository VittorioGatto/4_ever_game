from pathlib import Path

import streamlit as st

st.title("📖 Regolamento")

percorso = Path(__file__).parent.parent / "regolamento.txt"
st.text(percorso.read_text())

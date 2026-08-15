from pathlib import Path

import streamlit as st

st.title("📖 Regolamento")

cartella = Path(__file__).parent.parent

with st.container(border=True):
    st.subheader("🏐 Regolamento di gioco")
    st.text((cartella / "regolamento_gioco.txt").read_text())

with st.container(border=True):
    st.subheader("🏆 Regolamento punti e Rk")
    st.text((cartella / "regolamento_punti.txt").read_text())

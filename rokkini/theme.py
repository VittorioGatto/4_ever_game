"""Restyling anni '90: sfondo nero, testo giallo. La palette (colori/font)
è in .streamlit/config.toml; qui solo il CSS che quel file non può esprimere
(bordi netti, hover, spaziatura dei titoli)."""

import streamlit as st

_CSS = """
<style>
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stBaseButton-secondary"] > button {
    border: 2px solid #FFFF00 !important;
    border-radius: 0 !important;
    font-family: monospace !important;
    text-transform: uppercase;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
    background-color: #FFFF00 !important;
    color: #000000 !important;
}

div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    border: 2px solid #FFFF00 !important;
}

hr { border-color: #FFFF00 !important; }

h1, h2, h3 { font-family: monospace !important; letter-spacing: 1px; }

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {
    border: 1px solid #FFFF00 !important;
}

/* tag di un'opzione selezionata in un multiselect (es. giocatori scelti):
   di default arrivano gialle su giallo/nero a basso contrasto, illeggibili */
[data-tag] {
    background-color: #000000 !important;
    color: #00FF00 !important;
    border: 1px solid #00FF00 !important;
}
[data-tag] svg { fill: #00FF00 !important; }
</style>
"""


def inject_custom_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

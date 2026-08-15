"""Restyling anni '90: sfondo nero, testo verde stile terminale. La palette
(colori/font) è in .streamlit/config.toml; qui solo il CSS che quel file non
può esprimere (bordi netti, hover, spaziatura dei titoli)."""

import streamlit as st

_CSS = """
<style>
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stBaseButton-secondary"] > button {
    border: 2px solid #00FF00 !important;
    border-radius: 0 !important;
    font-family: monospace !important;
    text-transform: uppercase;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
    background-color: #00FF00 !important;
    color: #000000 !important;
}

div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    border: 2px solid #00FF00 !important;
}

hr { border-color: #00FF00 !important; }

h1, h2, h3 { font-family: monospace !important; letter-spacing: 1px; }

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input {
    border: 1px solid #00FF00 !important;
}

/* tag di un'opzione selezionata in un multiselect (es. giocatori scelti) */
[data-tag] {
    background-color: #000000 !important;
    color: #00FF00 !important;
    border: 1px solid #00FF00 !important;
}
[data-tag] svg { fill: #00FF00 !important; }

div[data-testid="stDataFrame"] { max-width: 100%; overflow-x: auto; }

/* su schermi stretti il padding/font di default lascia troppo spazio vuoto
sopra il titolo e lo fa andare a capo su due righe: qui si riduce entrambi */
@media (max-width: 640px) {
    .block-container {
        padding-top: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    h1 { font-size: 1.9rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.25rem !important; }
}

/* "Rocco sta pensando": invece di un placeholder gestito a mano in Python
(che sparisce con un st.empty().empty() a fine script — inaffidabile,
perche' st.stop() puo' interrompere lo script prima che quel cleanup
"conti" per il frontend, lasciandolo bloccato a schermo), si restyla
l'indicatore "sto girando" che Streamlit stesso mostra/nasconde in base
allo stato reale di esecuzione dello script: non puo' restare bloccato, e
stando in position:fixed non sposta il contenuto sotto quando appare o
sparisce. */
div[data-testid="stStatusWidget"] {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 9999 !important;
    background-color: #000000 !important;
    border: 2px solid #00FF00 !important;
    border-radius: 0 !important;
    padding: 2rem 3rem !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    box-shadow: 0 0 24px rgba(0, 255, 0, 0.25) !important;
}
div[data-testid="stStatusWidget"] * { display: none !important; }
div[data-testid="stStatusWidget"]::before {
    content: "🏐🤔";
    font-size: 3rem;
    line-height: 1;
}
div[data-testid="stStatusWidget"]::after {
    content: "Rocco sta pensando...";
    font-family: monospace;
    color: #00FF00;
    font-size: 1.1rem;
    letter-spacing: 1px;
    margin-top: 1rem;
    white-space: nowrap;
}
</style>
"""


def inject_custom_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

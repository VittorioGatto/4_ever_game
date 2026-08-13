# Rokkini

Classifica personale a punteggio Elo ("Rokkini" / Rk) per partite informali di
pallavolo 3v3 / 4v4. Regole complete in [regolamento.txt](regolamento.txt),
schema funzionale dell'app in [schema di funzionamento.txt](schema%20di%20funzionamento.txt).

## Sviluppo locale

```bash
uv sync
uv run python scripts/init_db.py          # crea lo schema su data/local.db
uv run python scripts/seed_demo_data.py   # dati finti per provare la UI (opzionale)
uv run python scripts/create_admin.py --username admin --password ... --ruolo super_admin
uv run streamlit run app.py
```

## Test

```bash
uv run pytest
```

## Deploy (Streamlit Community Cloud + Turso)

1. `turso db create rokkini` e `turso db tokens create rokkini`.
2. `uv run python scripts/init_db.py --turso`.
3. `uv run python scripts/create_admin.py --turso --username ... --password ... --ruolo super_admin`.
4. `uv export --no-hashes --no-dev --format requirements-txt -o requirements.txt` (va rigenerato e committato a ogni modifica delle dipendenze: Streamlit Community Cloud non risolve `uv.lock`).
5. Push su GitHub, poi "New app" su [share.streamlit.io](https://share.streamlit.io) con main file `app.py`.
6. In "Advanced settings → Secrets" incollare il contenuto di `.streamlit/secrets.toml.example` compilato con i valori reali (mai committare `secrets.toml`).

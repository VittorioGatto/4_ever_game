# Rokkini

Classifica personale a punteggio Elo ("Rokkini" / Rk) per partite informali di
pallavolo 3v3 / 4v4. Regole complete in [regolamento.txt](regolamento.txt),
schema funzionale dell'app in [schema di funzionamento.txt](schema%20di%20funzionamento.txt).

## Sviluppo locale

```bash
uv sync
uv run python scripts/init_db.py          # crea lo schema su data/local.db
uv run python scripts/seed_demo_data.py   # dati finti per provare la UI (opzionale)
uv run python scripts/create_admin.py --username admin --password ... --nome "Nome Cognome"
uv run streamlit run app.py
```

`.streamlit/secrets.toml` in locale contiene solo `[auth]`: senza una sezione
`[turso]`, l'app si connette sempre al file locale `data/local.db`, mai al
database di produzione — è voluto, per non rischiare di scrivere dati di
prova su Turso semplicemente lanciando l'app in locale.

## Test

```bash
uv run pytest
```

## Deploy (Streamlit Community Cloud + Turso)

Le operazioni `--turso` (passi 2-3) leggono le credenziali da
`.streamlit/secrets.turso-provisioning.toml` (da creare, stesso formato di
`.streamlit/secrets.toml.example`, sezione `[turso]` soltanto) — **non**
da `.streamlit/secrets.toml`, che resta quello letto automaticamente
dall'app quando gira in locale. Tenerli separati è deliberato: se le
credenziali Turso finissero nel file letto in automatico, un semplice
`streamlit run app.py` in locale scriverebbe sul database di produzione.

1. `turso db create rokkini` e `turso db tokens create rokkini`; salva URL e token in `.streamlit/secrets.turso-provisioning.toml` (gitignored).
2. `uv run python scripts/init_db.py --turso`.
3. `uv run python scripts/create_admin.py --turso --username ... --password ... --nome "Nome Cognome"`.
4. `uv export --no-hashes --no-dev --format requirements-txt -o requirements.txt` (va rigenerato e committato a ogni modifica delle dipendenze: Streamlit Community Cloud non risolve `uv.lock`).
5. Push su GitHub, poi "New app" su [share.streamlit.io](https://share.streamlit.io) con main file `app.py`.
6. In "Advanced settings → Secrets" incollare il contenuto di `.streamlit/secrets.toml.example` compilato con i valori reali (`[turso]` + `[auth]` insieme: lì è corretto, è quello che l'app deployata legge in produzione).

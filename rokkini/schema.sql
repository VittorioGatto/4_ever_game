CREATE TABLE IF NOT EXISTS giocatori (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                     TEXT NOT NULL,
    rk_attuale               INTEGER NOT NULL DEFAULT 1000,
    partite_giocate          INTEGER NOT NULL DEFAULT 0,
    vittorie                 INTEGER NOT NULL DEFAULT 0,
    sconfitte                INTEGER NOT NULL DEFAULT 0,
    fascia_attuale           TEXT NOT NULL DEFAULT 'H',
    qualificato              INTEGER NOT NULL DEFAULT 0,
    sospeso                  INTEGER NOT NULL DEFAULT 0,
    rk_record                INTEGER NOT NULL DEFAULT 1000,
    streak_vittorie_corrente INTEGER NOT NULL DEFAULT 0,
    streak_vittorie_record   INTEGER NOT NULL DEFAULT 0,
    created_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS utenti (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    username          TEXT NOT NULL UNIQUE,
    nome_visualizzato TEXT NOT NULL,
    email             TEXT,
    password_hash     TEXT NOT NULL,
    ruolo             TEXT NOT NULL CHECK (ruolo = 'super_admin'),
    giocatore_id      INTEGER REFERENCES giocatori (id),
    attivo            INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessioni_gioco (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    iniziata_at       TEXT NOT NULL DEFAULT (datetime('now')),
    terminata_at      TEXT,
    iniziata_da       INTEGER NOT NULL REFERENCES utenti (id),
    programma_torneo  TEXT
);

CREATE TABLE IF NOT EXISTS sessione_partecipanti (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sessione_id  INTEGER NOT NULL REFERENCES sessioni_gioco (id),
    giocatore_id INTEGER NOT NULL REFERENCES giocatori (id),
    UNIQUE (sessione_id, giocatore_id)
);

CREATE TABLE IF NOT EXISTS partite (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    data_partita      TEXT NOT NULL,
    modalita          TEXT NOT NULL CHECK (modalita IN ('3v3', '4v4')),
    risultato_set     TEXT NOT NULL CHECK (risultato_set IN ('2-0', '2-1', '1-2', '0-2')),
    squadra_vincente  TEXT NOT NULL CHECK (squadra_vincente IN ('A', 'B')),
    voided            INTEGER NOT NULL DEFAULT 0,
    voided_at         TEXT,
    voided_by         INTEGER REFERENCES utenti (id),
    voided_reason     TEXT,
    replaces_match_id INTEGER REFERENCES partite (id),
    registered_by     INTEGER NOT NULL REFERENCES utenti (id),
    sessione_id       INTEGER REFERENCES sessioni_gioco (id),
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS partecipazioni_partita (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    partita_id   INTEGER NOT NULL REFERENCES partite (id),
    giocatore_id INTEGER NOT NULL REFERENCES giocatori (id),
    squadra      TEXT NOT NULL CHECK (squadra IN ('A', 'B')),
    UNIQUE (partita_id, giocatore_id)
);

CREATE TABLE IF NOT EXISTS variazioni_rk (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    partita_id          INTEGER NOT NULL REFERENCES partite (id),
    giocatore_id        INTEGER NOT NULL REFERENCES giocatori (id),
    squadra             TEXT NOT NULL CHECK (squadra IN ('A', 'B')),
    esito                TEXT NOT NULL CHECK (esito IN ('vittoria', 'sconfitta')),
    rk_prima             INTEGER NOT NULL,
    k_usato               INTEGER NOT NULL,
    probabilita_teorica  REAL NOT NULL,
    correttivo_usato     REAL NOT NULL,
    delta                INTEGER NOT NULL,
    rk_dopo               INTEGER NOT NULL,
    UNIQUE (partita_id, giocatore_id)
);

CREATE TABLE IF NOT EXISTS ranking_leader_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    giocatore_id INTEGER NOT NULL REFERENCES giocatori (id),
    started_at   TEXT NOT NULL,
    ended_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_partite_data ON partite (voided, data_partita, created_at, id);
CREATE INDEX IF NOT EXISTS idx_variazioni_giocatore ON variazioni_rk (giocatore_id);
CREATE INDEX IF NOT EXISTS idx_partecipazioni_giocatore ON partecipazioni_partita (giocatore_id);
CREATE INDEX IF NOT EXISTS idx_partecipazioni_partita ON partecipazioni_partita (partita_id);
CREATE INDEX IF NOT EXISTS idx_partite_sessione ON partite (sessione_id);
CREATE INDEX IF NOT EXISTS idx_sessione_partecipanti_sessione ON sessione_partecipanti (sessione_id);

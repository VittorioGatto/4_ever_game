RK_INIZIALE = 1000

PARTITE_QUALIFICAZIONE = 5

# Soglie di fascia: (rk_minimo, nome_fascia), verificate dalla più alta alla più bassa.
FASCE = [
    (1800, "A"),
    (1500, "B"),
    (1200, "C"),
    (0, "H"),
]

# Coefficiente K in base al numero di partite giocate (prima della partita corrente).
K_FACTOR_SOGLIE = [
    (41, 16),
    (26, 24),
    (15, 32),
    (6, 40),
    (1, 50),
]

CORRETTIVO_MASSIMO = 0.20

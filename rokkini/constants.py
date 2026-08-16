RK_INIZIALE = 1250

PARTITE_QUALIFICAZIONE = 5

# Soglie di fascia: (rk_minimo, nome_fascia), verificate dalla più alta alla più bassa.
# RK_INIZIALE (1250) cade a meta' della fascia C: un nuovo giocatore parte dal
# centro del ranking e si sposta verso H/D o B/A in base ai risultati, invece
# di partire dal fondo.
FASCE = [
    (1401, "A"),
    (1301, "B"),
    (1201, "C"),
    (1101, "D"),
    (0, "H"),
]

# Coefficiente K in base al numero di partite gia' disputate (prima della
# partita corrente): piu' alto per i nuovi giocatori (rating ancora poco
# affidabile, deve potersi muovere in fretta), decresce con l'esperienza ma
# non scende mai sotto 24.
K_FACTOR_SOGLIE = [
    (65, 24),
    (45, 26),
    (30, 29),
    (20, 33),
    (10, 38),
    (5, 45),
    (0, 55),
]

CORRETTIVO_MASSIMO = 0.05

# Il correttivo confronta il Rk del giocatore con la media dei SOLI compagni
# (se stesso escluso), non con la media di tutta la squadra: D = media
# compagni - Rk giocatore. Saturazione non simmetrica: lo sfavorito (D>0)
# arriva al correttivo massimo gia' a una differenza di 200 Rk; il favorito
# (D<0) solo a 400 Rk, il doppio.
CORRETTIVO_SATURAZIONE_SFAVORITO = 200
CORRETTIVO_SATURAZIONE_FAVORITO = 400

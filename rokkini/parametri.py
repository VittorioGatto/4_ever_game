"""Parametri di calcolo Rk configurabili a runtime.

A differenza delle vecchie costanti fisse in rokkini/constants.py, questi
valori vivono nella tabella parametri_calcolo (riga singola, id=1) e possono
essere cambiati dalla pagina Simulazione senza un deploy di codice.
constants.py resta solo come default di bootstrap, usato da db.apply_schema
per popolare quella riga la prima volta.
"""

import json
from dataclasses import dataclass

from rokkini import constants


@dataclass(frozen=True)
class Parametri:
    rk_iniziale: int
    partite_qualificazione: int
    fasce: list[tuple[int, str]]
    k_factor_soglie: list[tuple[int, int]]
    correttivo_massimo: float
    correttivo_saturazione_sfavorito: int
    correttivo_saturazione_favorito: int


DEFAULT = Parametri(
    rk_iniziale=constants.RK_INIZIALE,
    partite_qualificazione=constants.PARTITE_QUALIFICAZIONE,
    fasce=list(constants.FASCE),
    k_factor_soglie=list(constants.K_FACTOR_SOGLIE),
    correttivo_massimo=constants.CORRETTIVO_MASSIMO,
    correttivo_saturazione_sfavorito=constants.CORRETTIVO_SATURAZIONE_SFAVORITO,
    correttivo_saturazione_favorito=constants.CORRETTIVO_SATURAZIONE_FAVORITO,
)


def fetch_parametri_attivi(conn) -> Parametri:
    cur = conn.execute(
        """SELECT rk_iniziale, partite_qualificazione, fasce_json, k_factor_soglie_json,
                  correttivo_massimo, correttivo_saturazione_sfavorito, correttivo_saturazione_favorito
           FROM parametri_calcolo WHERE id = 1"""
    )
    riga = cur.fetchone()
    if riga is None:
        # db.apply_schema() dovrebbe sempre aver seminato questa riga: questo
        # fallback serve solo per DB aperti senza passare da li' (es. test
        # che costruiscono lo schema a mano).
        return DEFAULT
    return Parametri(
        rk_iniziale=riga[0],
        partite_qualificazione=riga[1],
        fasce=[tuple(x) for x in json.loads(riga[2])],
        k_factor_soglie=[tuple(x) for x in json.loads(riga[3])],
        correttivo_massimo=riga[4],
        correttivo_saturazione_sfavorito=riga[5],
        correttivo_saturazione_favorito=riga[6],
    )


def salva_parametri_attivi(conn, parametri: Parametri) -> None:
    conn.execute(
        """UPDATE parametri_calcolo SET
               rk_iniziale = ?, partite_qualificazione = ?, fasce_json = ?, k_factor_soglie_json = ?,
               correttivo_massimo = ?, correttivo_saturazione_sfavorito = ?, correttivo_saturazione_favorito = ?
           WHERE id = 1""",
        (
            parametri.rk_iniziale,
            parametri.partite_qualificazione,
            json.dumps(parametri.fasce),
            json.dumps(parametri.k_factor_soglie),
            parametri.correttivo_massimo,
            parametri.correttivo_saturazione_sfavorito,
            parametri.correttivo_saturazione_favorito,
        ),
    )
    conn.commit()

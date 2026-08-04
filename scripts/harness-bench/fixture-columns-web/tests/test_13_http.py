"""ÉTAGE 13 — application WSGI.

`colonnes.web.application` est une application WSGI de la bibliothèque standard
(aucune dépendance externe, aucun serveur à lancer : elle s'appelle directement).

`colonnes.web.nouvelle_partie(sequence, largeur=6, hauteur=13)` installe la partie
servie par l'application et la rend. C'est le seul moyen de rendre les requêtes
déterministes : sans elle, on ne saurait pas quelles colonnes tombent.

Routes :

    GET  /        -> 200, `Content-Type: text/html; charset=utf-8`,
                     corps = `rendu_html` de la partie en cours
    GET  /etat    -> 200, `Content-Type: application/json`,
                     corps = `json.dumps` de `etat`
    POST /action  -> 303, en-tête `Location: /`
                     corps `application/x-www-form-urlencoded`, champ `action` parmi
                     gauche, droite, cycler, descendre, chuter
    tout le reste -> 404
    POST /        -> 405

L'état PERSISTE entre deux requêtes : c'est la même partie.
"""

import io
import json

import pytest

from colonnes.web import application, nouvelle_partie


def appelle(methode, chemin, corps=""):
    """Appelle l'application WSGI sans serveur. Rend (statut, entêtes, corps)."""
    octets = corps.encode("utf-8")
    environ = {
        "REQUEST_METHOD": methode,
        "PATH_INFO": chemin,
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(octets),
        "wsgi.errors": io.StringIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "CONTENT_LENGTH": str(len(octets)),
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
    }
    capture = {}

    def start_response(statut, entetes, exc_info=None):
        capture["statut"] = statut
        capture["entetes"] = entetes

    morceaux = application(environ, start_response)
    return (
        capture["statut"],
        dict(capture["entetes"]),
        b"".join(morceaux).decode("utf-8"),
    )


@pytest.fixture(autouse=True)
def partie():
    """Chaque test repart d'une partie connue."""
    return nouvelle_partie(iter(["ABC", "DEF", "GHI"]), largeur=4, hauteur=6)


def test_nouvelle_partie_rend_le_jeu():
    j = nouvelle_partie(iter(["ABC"]), largeur=4, hauteur=6)
    assert j.colonne.tuiles == ("A", "B", "C")
    assert (j.ligne, j.col) == (0, 2)


def test_racine_rend_du_html():
    statut, entetes, corps = appelle("GET", "/")
    assert statut.startswith("200")
    assert entetes["Content-Type"] == "text/html; charset=utf-8"
    assert corps.lstrip().startswith("<!DOCTYPE html>")
    assert '<table id="plateau"' in corps


def test_etat_rend_du_json():
    statut, entetes, corps = appelle("GET", "/etat")
    assert statut.startswith("200")
    assert entetes["Content-Type"] == "application/json"
    d = json.loads(corps)
    assert d["colonne"] == ["A", "B", "C"]
    assert (d["largeur"], d["hauteur"]) == (4, 6)


def test_action_redirige():
    statut, entetes, _ = appelle("POST", "/action", "action=gauche")
    assert statut.startswith("303")
    assert entetes["Location"] == "/"


def test_action_gauche_deplace():
    appelle("POST", "/action", "action=gauche")
    assert json.loads(appelle("GET", "/etat")[2])["col"] == 1


def test_action_droite_deplace():
    appelle("POST", "/action", "action=droite")
    assert json.loads(appelle("GET", "/etat")[2])["col"] == 3


def test_action_cycler():
    appelle("POST", "/action", "action=cycler")
    assert json.loads(appelle("GET", "/etat")[2])["colonne"] == ["C", "A", "B"]


def test_action_descendre():
    appelle("POST", "/action", "action=descendre")
    assert json.loads(appelle("GET", "/etat")[2])["ligne"] == 1


def test_action_chuter_verrouille_et_fait_apparaitre_la_suivante():
    appelle("POST", "/action", "action=chuter")
    d = json.loads(appelle("GET", "/etat")[2])
    assert d["colonne"] == ["D", "E", "F"]
    assert d["plateau"][-1] == "..C."


def test_etat_persiste_entre_requetes():
    appelle("POST", "/action", "action=gauche")
    appelle("POST", "/action", "action=descendre")
    d = json.loads(appelle("GET", "/etat")[2])
    assert (d["ligne"], d["col"]) == (1, 1)


def test_chemin_inconnu_404():
    statut, _, _ = appelle("GET", "/pas-une-route")
    assert statut.startswith("404")


def test_methode_refusee_sur_la_racine():
    statut, _, _ = appelle("POST", "/")
    assert statut.startswith("405")

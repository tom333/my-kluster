"""ORACLE CACHÉ de la fixture `pronote` — n'est PAS dans le dépôt donné au modèle.

Pourquoi caché, contrairement à `columns-web` dont les tests sont dans la fixture :
là-bas la tâche est « fais passer ces tests », ici c'est « diagnostique depuis un
symptôme ». Des tests visibles donneraient la réponse au lieu de la faire trouver.
Même discipline que la solution de référence de `columns-web`, gardée hors du dépôt.

Copié dans le workdir au moment de la VÉRIFICATION seulement, jamais avant.

L'énoncé donné au modèle ne dit que le symptôme : « les cours annotés "absence
admin" sont des cours annulés qui restent dans l'emploi du temps, donc je ne reçois
pas de notification ». Rien sur `estAnnule`, `Statut`, `_content_key` ni le fichier.

DEUX DÉFAUTS CUMULÉS, tous deux nécessaires (établis le 2026-08-05, commits
856f0c8 et 48eb592 du dépôt pronote) :

1. `Lesson.canceled` vient de `estAnnule` (pronotepy/dataClasses.py:872), PAS de
   `indicateurAbsence` comme l'affirmait le docstring du module. Pronote laisse
   `estAnnule` à faux et n'annule que par le libellé `Statut` — le calendrier HA
   n'affiche donc aucune croix, ce qui l'a prouvé sur un compte réel.
2. Le diff ne détecte qu'une bascule `False -> True` entre deux sondages du MÊME
   jour, et la clé d'identité inclut la date. Un cours annulé à l'avance entre dans
   la fenêtre déjà annulé, sans transition à observer.

Corriger l'un sans l'autre ne suffit pas, ce que les quatre bras du 2026-08-05 ont
tous démontré, chacun d'une façon différente :

    témoin        `_classify_change` sans le garde -> notifie à CHAQUE sondage
    grep/glob     `_classify_change` sans le garde -> CODE MORT (jamais atteint)
    graphe        `_content_key` seul              -> notifie « modified »
    plage+corps   `_classify_change` sans le garde -> CODE MORT

Le cas 3 est la NON-RÉGRESSION : une annulation classique doit continuer de marcher.
Sans lui, un correctif qui casse le comportement existant passerait pour bon.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.ha_pronote.api.models import Lesson, Snapshot
from custom_components.ha_pronote.diff import diff_lessons

TZ = ZoneInfo("Pacific/Noumea")
JOUR = date(2026, 5, 4)


def lecon(statut="", annule=False, jour=JOUR, matiere="MATHS"):
    return Lesson(
        date=jour,
        start=datetime(jour.year, jour.month, jour.day, 8, 0, tzinfo=TZ),
        end=datetime(jour.year, jour.month, jour.day, 9, 0, tzinfo=TZ),
        subject=matiere,
        teacher="M. X",
        classroom="A1",
        canceled=annule,
        status=statut,
    )


def instantane(jour, lecons):
    return Snapshot(today=jour, school_tz="Pacific/Noumea", lessons=lecons)


def test_statut_seul_emet_une_annulation():
    """Le libellé « absence admin » apparaît, `estAnnule` reste faux.

    Défaut 1. Échoue tant que la détection ne lit que `canceled`, et échoue AUSSI
    quand la branche ajoutée est gardée en amont par `_content_key` (code mort).
    """
    t0 = instantane(JOUR, [lecon("")])
    t1 = instantane(JOUR, [lecon("absence admin")])
    evenements = diff_lessons(t0, t1, "today")
    assert [e.change_type for e in evenements] == ["canceled"]


def test_annulation_anterieure_a_l_entree_en_fenetre():
    """Le cours du lendemain est DÉJÀ annulé quand il entre dans la tranche.

    Défaut 2. Une absence administrative est posée plusieurs jours à l'avance : il
    n'y a jamais de bascule `False -> True` sous les yeux du diff.
    """
    demain = JOUR + timedelta(days=1)
    t0 = instantane(JOUR, [lecon("", jour=JOUR, matiere="FRANCAIS"), lecon("absence admin", jour=demain)])
    t1 = instantane(demain, [lecon("absence admin", jour=demain)])
    evenements = diff_lessons(t0, t1, "today")
    assert [e.change_type for e in evenements] == ["canceled"]


def test_bascule_classique_du_drapeau_intacte():
    """NON-RÉGRESSION : une annulation ordinaire doit continuer de marcher."""
    t0 = instantane(JOUR, [lecon("")])
    t1 = instantane(JOUR, [lecon("Cours annulé", annule=True)])
    evenements = diff_lessons(t0, t1, "today")
    assert [e.change_type for e in evenements] == ["canceled"]


def test_cours_deplace_n_est_pas_une_annulation():
    """GARDE-FOU contre un prédicat trop large.

    Les captures réelles montrent `status='cours déplacé'` avec `canceled=True` ET
    avec `canceled=False` : c'est un autre axe de la taxonomie. Un correctif qui
    promeut tout changement de libellé en annulation doit échouer ici.
    """
    t0 = instantane(JOUR, [lecon("")])
    t1 = instantane(JOUR, [lecon("Cours déplacé")])
    evenements = diff_lessons(t0, t1, "today")
    assert "canceled" not in [e.change_type for e in evenements]


def test_annulation_ne_se_repete_pas_a_chaque_sondage():
    """GARDE-FOU contre un prédicat trop large, second volet.

    Un cours annulé et inchangé entre deux sondages du même jour ne doit PAS
    re-notifier : le correctif du bras témoin faisait exactement ça, et aucun test
    existant ne l'attrapait.
    """
    t0 = instantane(JOUR, [lecon("absence admin")])
    t1 = instantane(JOUR, [lecon("absence admin")])
    assert diff_lessons(t0, t1, "today") == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

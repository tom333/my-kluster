#!/usr/bin/env python3
"""Banc de montee en charge pour harnais de codage agentique.

Meme fixture, meme prompt, meme verification pour tous les harnais et tous les
modeles. Le verdict ne regarde QUE l'etat du disque apres coup : il est donc
valable pour un harnais a outils (pi) comme pour un harnais a diff (aider).

  bench.py --scenario repair --harness pi --model localai/qwen3-coder-30b-a3b-instruct
  bench.py --scenario tetris --harness pi --model localai/bonsai-27b
  bench.py --list-harnesses

Resultat : results/<harness>-<modele>-<horodatage>.json
"""

import argparse
import ast
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import tempfile
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
# Chaque essai produit des paires (contexte -> appel d'outil -> OK:/ERREUR:), qui
# sont le jeu d'entrainement du finetune de FORMAT (cf. generateur_traces.py). Ces
# transcripts vivaient dans /tmp et disparaissaient au redemarrage : 88 fichiers
# ont failli etre perdus le 2026-08-02. Les campagnes les archivent desormais
# elles-memes — mesurer et produire de la donnee coutent le meme GPU, autant
# garder les deux.
TRAJECTOIRES = HERE / "trajectoires"
PROJETS = HERE / "projets"
PYTEST = os.environ.get("BENCH_PYTEST", "/usr/bin/pytest")

# APPARIEMENT DES TIRAGES (2026-08-05). Cinq graines figees, arbitraires mais
# STABLES : le tirage i de tout bras utilise GRAINES[i-1].
#
# Motif : sur `columns-web` un reglage IDENTIQUE produit 4 a 21 tours et 280 a
# 1 590 s, avec un aneantissement sur cinq. Les leviers cherches valent 10 a 20 %,
# donc on mesurait sous le bruit — trois verdicts du 2026-08-05 (budget de pensee,
# reprise sur troncature, temperature) portent sur des ecarts plus petits que la
# dispersion de leur propre bras, et aucun n'est solide. Apparier convertit une
# comparaison 5 contre 5 non appariee en 5 differences appariees, a depense egale.
#
# Ne jamais reordonner ni reechantillonner cette liste : ce sont les graines de
# TOUS les bras appariables. En ajouter a la fin est sans danger, changer les cinq
# premieres invalide l'appariement avec l'historique.
GRAINES = (11, 2027, 40507, 606061, 8009)

# Desactive par defaut : le temoin garde ses graines aleatoires, donc les campagnes
# deja indexees restent comparables. `BENCH_GRAINES=1` active l'appariement, et
# l'empreinte du registre le voit via HARNAIS_NU_SEED dans config_env.
GRAINES_ACTIVES = bool(os.environ.get("BENCH_GRAINES"))

# Une graine posee A LA MAIN par l'appelant a la priorite, et elle est capturee ICI,
# au chargement du module, PAS relue a chaque tirage.
#
# Le piege (constate le 2026-08-05, deux tirages en production avant de le voir) :
# `os.environ` PERSISTE entre les tirages d'une meme campagne. Une garde
# `if "HARNAIS_NU_SEED" not in os.environ` est vraie au tirage 1, ou l'on pose la
# graine, et FAUSSE ensuite — les cinq tirages heritent donc de la graine du
# premier. Le symptome : deux tirages a 6 tours et pic 16 881 identiques au token
# pres. L'appariement se serait retourne contre lui-meme, en fabriquant deux bras
# artificiellement constants d'ou l'on aurait conclu a tort a une neutralite.
GRAINE_IMPOSEE = os.environ.get("HARNAIS_NU_SEED")

# Deux scenarios de difficulte tres differente.
#
# `repair` : 7 defauts semes dans 5 modules existants, chacun une inversion d'UN
#   token. Les noms de tests designent le bug. Mesure la MECANIQUE de la boucle
#   (lire, editer, lancer, iterer), pas la capacite de codage : il ne separe pas un
#   quant ternaire d'un MoE IQ1_S, les deux font 19/19.
#
# `tetris` : le paquet n'existe pas, il faut l'ecrire depuis le contrat. Demande de
#   la CONCEPTION (representation, rotation de matrice, degagement, gravite,
#   scoring) tout en gardant un oracle parfait, car le coeur est deterministe et
#   sans horloge. `check_api` est faux : tout est nouveau, comparer les signatures
#   a un dossier vide n'aurait aucun sens.
SCENARIOS = {
    "repair": {
        "fixture": HERE / "fixture",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "L'oracle est la suite FOURNIE (19 tests) : le modele ne l'ecrit pas.",
            "Il part a 6 passes / 13 echecs — un score de 6 ne vaut RIEN, c'est le depart.",
        ),
        "prompt": HERE / "PROMPT.txt",
        "expected_tests": 19,
        "protected": ("tests/test_taskmgr.py", "conftest.py"),
        "check_api": True,
    },
    "tetris": {
        "fixture": HERE / "fixture-tetris",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Les 44 tests importent tous le paquet : une coquille donne 0/44.",
            "SATURE (44/44 partout depuis le 2026-07-30) : ne classe plus, il filtre.",
            "CONTAMINE : exercice canonique, ecrit des milliers de fois -> mesure en partie la RESTITUTION.",
        ),
        "prompt": HERE / "PROMPT-tetris.txt",
        "expected_tests": 44,
        "protected": ("tests/test_tetris.py", "conftest.py"),
        "check_api": False,
    },
    # Le trou de mesure que `tetris` et `repair` ne couvrent pas : LIRE du code
    # existant et l'etendre sans le casser. Les deux autres fixtures partent d'une
    # page blanche, et toutes deux sont SATUREES (44/44 sur 5/5 essais, 19/19
    # partout) — un score saturé ne discrimine plus rien.
    #
    # Le code existant est une solution 44/44 relue (essai 5 de la campagne
    # `contrat` du 2026-07-31, 5 modules). Deux defauts latents y ont ete reperes
    # et VOLONTAIREMENT conserves — c'est du vrai code, pas du code de vitrine :
    # `Piece._get_matrix` boucle sur la rotation brute (une rotation negative rend
    # une matrice non tournee) et remplit les cases vides de '' au lieu de '.'. Le
    # contrat d'extension oriente donc vers `cells()` plutot que `matrix`.
    "tetris-etendu": {
        "fixture": HERE / "fixture-tetris-etendu",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Deux etages : non-regression (44) puis extension (18). L'extension seule discrimine.",
        ),
        "prompt": HERE / "PROMPT-tetris-etendu.txt",
        "expected_tests": 62,
        "protected": (
            "tests/test_tetris.py",
            "tests/test_extension.py",
            "conftest.py",
        ),
        "check_api": False,
        # Deux etages notes SEPAREMENT : « il a casse l'existant » n'est pas la
        # meme defaillance que « il n'a pas su etendre ». Chacun dans son propre
        # appel pytest, car une erreur d'import dans le fichier d'extension
        # interrompt la collecte de TOUTE la suite — le score de non-regression
        # serait perdu alors qu'il est precisement ce qu'on veut surveiller.
        "etages": (
            ("regression", "tests/test_tetris.py", 44),
            ("extension", "tests/test_extension.py", 18),
        ),
    },
    # Fixture 3 — reponse au diagnostic de CONTAMINATION du 2026-07-31 : `tetris`
    # (44/44 partout) et `repair` (19/19 partout) sont des exercices canoniques,
    # ecrits des milliers de fois, donc on y mesure en partie la RESTITUTION et non
    # la capacite. Grossir un tetris n'y change rien.
    #
    # Columns (Sega, 1990) est RARE — peu d'implementations publiques — tout en
    # restant plausible et algorithmiquement profond la ou tetris ne l'est pas :
    # alignements sur QUATRE axes, suppression simultanee, cascades en chaine.
    # Les details qui font l'oracle sont INVENTES (sens du cycle, alphabet des
    # tuiles, table des multiplicateurs, semantique de la simultaneite) : se
    # souvenir du jeu donne la forme, pas les reponses.
    #
    # Dix etages INDEPENDANTS, notes separement : c'est ce qui donne un score
    # GRADUE. `tetris` est binaire (les 44 tests importent tous le paquet, donc une
    # coquille donne 0/44), or un instrument tout-ou-rien sature ou s'effondre,
    # jamais entre les deux — il ne peut pas graduer.
    "columns": {
        "fixture": HERE / "fixture-columns",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Details de l'oracle INVENTES (sens du cycle, alphabet des tuiles, table des",
            "multiplicateurs) : se souvenir du jeu donne la forme, pas les reponses.",
            "Dix etages INDEPENDANTS -> credit partiel. C'est le seul instrument qui gradue.",
            "La boucle de verification RATTRAPE les erreurs de connaissance : un score haut",
            "ne prouve pas que le modele savait, seulement qu'il a su corriger.",
        ),
        "prompt": HERE / "PROMPT-columns.txt",
        "expected_tests": 80,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
        ),
    },
    "columns-global": {
        "fixture": HERE / "fixture-columns",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Variante de `columns` : lire ses notes d'oracle.",
        ),
        "prompt": HERE / "PROMPT-columns-global.txt",
        "expected_tests": 80,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
        ),
    },
    # Fixture 3bis — `columns` DEJA RESOLU, a etendre. Les dix etages d'origine sont
    # livres verts (une vraie solution 80/80, tirage 4 de a3b-iq4-e3) et servent de
    # NON-REGRESSION ; trois etages neufs decrivent une interface web.
    #
    # Ce que cette fixture mesure et qu'aucune autre ne mesure : LIRE du code
    # existant pour s'y raccrocher. `columns` part de zero, donc tout ce qui compte
    # y est dans l'enonce ; ici l'interface publique (Plateau, Colonne, Jeu) est sur
    # le disque, et l'etage 13 impose des choix aux etages 11 et 12 — c'est la forme
    # de tache ou l'ecart Opus/local etait le plus large (6 tours contre 35).
    #
    # Contrat verifie SATISFAISABLE avant tout tirage : une implementation de
    # reference a affiche 109 passed, puis a ete retiree. Sans elle, `pytest -q`
    # annonce « Interrupted: 3 errors during collection » et les 80 de regression ne
    # tournent meme pas — d'ou les etages separes, obligatoires ici.
    #
    # `colonnes/__init__.py` n'est PAS protege : l'etendre est permis, et les dix
    # etages de regression sont la garde qui punit une reecriture ratee.
    "columns-web": {
        "fixture": HERE / "fixture-columns-web",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Variante de `columns` : lire ses notes d'oracle.",
        ),
        "prompt": HERE / "PROMPT-columns-web.txt",
        "expected_tests": 109,
        "protected": (
            "tests/test_1_plateau.py",
            "tests/test_2_colonne.py",
            "tests/test_3_mouvement.py",
            "tests/test_4_horizontal.py",
            "tests/test_5_vertical.py",
            "tests/test_6_diagonales.py",
            "tests/test_7_simultane.py",
            "tests/test_8_cascade.py",
            "tests/test_9_score.py",
            "tests/test_10_fin.py",
            "tests/test_11_rendu.py",
            "tests/test_12_etat.py",
            "tests/test_13_http.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("plateau", "tests/test_1_plateau.py", 12),
            ("colonne", "tests/test_2_colonne.py", 8),
            ("mouvement", "tests/test_3_mouvement.py", 13),
            ("horizontal", "tests/test_4_horizontal.py", 9),
            ("vertical", "tests/test_5_vertical.py", 7),
            ("diagonales", "tests/test_6_diagonales.py", 7),
            ("simultane", "tests/test_7_simultane.py", 5),
            ("cascade", "tests/test_8_cascade.py", 6),
            ("score", "tests/test_9_score.py", 6),
            ("fin", "tests/test_10_fin.py", 7),
            ("rendu", "tests/test_11_rendu.py", 9),
            ("etat", "tests/test_12_etat.py", 8),
            ("http", "tests/test_13_http.py", 12),
        ),
    },
    # Fixture 5 — LE PREMIER DEPOT REEL du banc, et le premier ORACLE CACHE.
    #
    # 64 fichiers .py, 4 Mo, ~124 000 tokens : quatre fois la fenetre de 32 768. Les
    # quatre fixtures precedentes tiennent en contexte ; celle-ci non, et c'est le
    # point. Epinglee au commit 09d9c53 du depot pronote, AVANT les correctifs
    # 856f0c8 et 48eb592 qui en donnent la solution de reference.
    #
    # Ce qu'elle mesure et qu'aucune autre ne mesure : DIAGNOSTIQUER depuis un
    # symptome. L'enonce ne dit que ce qu'un utilisateur constate — pas le fichier,
    # pas le champ, pas la cause. Les autres fixtures decrivent un contrat a
    # satisfaire ; celle-ci decrit une panne a comprendre.
    #
    # L'oracle est HORS de la fixture (oracle-pronote/), depose au moment de noter
    # seulement : des tests visibles donneraient la reponse. Il gradue en 5 points, ce
    # qui etait necessaire — les quatre bras du 2026-08-05 ont produit quatre
    # demi-solutions differentes, toutes a 3/5, qu'un oracle binaire aurait
    # confondues. Valide avant tout tirage : 3/5 sur les quatre bras, 5/5 sur le
    # correctif de reference.
    #
    # DEUX defauts cumules, et corriger l'un sans l'autre ne suffit pas :
    #   1. `Lesson.canceled` vient de `estAnnule`, pas de `indicateurAbsence` comme
    #      l'affirme le docstring du module — Pronote n'annule que par le libelle
    #      `Statut` et laisse le drapeau a faux ;
    #   2. le diff ne voit qu'une bascule False -> True entre deux sondages du MEME
    #      jour, or une absence administrative est posee des jours a l'avance.
    #
    # Pas de `.venv` dans la fixture : `bench.py` la recopie a chaque tirage, et
    # 704 Mo par tirage serait absurde. Consequence assumee — le modele ne peut pas
    # lancer les tests. Sans importance ici : AUCUN test existant ne couvre ce bug, et
    # les 79 verts n'ont rien detecte chez aucun des quatre bras.
    # AMORCE DE PROJET, et non ecriture de code dans un projet existant. Remarque de
    # l'utilisateur, 2026-08-06 : « tu crees beaucoup de choses, donc on saura
    # seulement si le modele peut produire du code, pas s'il peut creer un projet ».
    # Le verdict de l'etape 0 lui donne raison -- la partie difficile etait de
    # resoudre un conflit de version entre flutter_scene et le flutter_gpu du SDK,
    # pas d'ecrire une matrice orthographique.
    #
    # La fixture ne contient QUE la spec. Le SDK Flutter (canal master, seul ou
    # flutter_scene compile) est pose en tete de PATH par l'environnement, comme un
    # venv Python l'est pour `pronote` : l'agent n'a pas a le chercher.
    #
    # Note sur le cout : chaque tirage construit un APK (~70 s au mieux), l'installe
    # et le lance. C'est le scenario le plus lent du banc, et il exige un emulateur
    # ou un appareil branche PENDANT la mesure.
    "crepuscule-amorce": {
        "fixture": HERE / "fixture-crepuscule-amorce",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "L'etage `rendu` REFUSE le gabarit `flutter create` et l'absence de flutter_scene.",
            "L'etage `build` relance lui-meme `flutter build apk --debug` : un APK perime ne",
            "peut pas le faire passer (verifie le 2026-09-16).",
            "Les seuils sont dans SPEC.md §3bis, JAMAIS dans le prompt.",
            "Les etages `lancement` et `rendu` exigent l'emulateur ALLUME : arrete, ils",
            "echouent en silence et ca ressemble a un defaut du modele.",
            "AUCUN essai n'a jamais fait un seul commit -> les 3 etages de methode",
            "(`test_dabord`, `historique`) ne sont jamais approches.",
        ),
        "prompt": HERE / "PROMPT-crepuscule-amorce.txt",
        "verifieur": "amorce-flutter",
        "sdk_bin": "/home/moi/develop/flutter-master/bin",
        "adb": "/home/moi/Android/Sdk/platform-tools/adb",
        # Chaine d'outils posee en tete de PATH pour l'agent (cf. outils.env_pour).
        # Ce n'est pas un venv Python : env_pour ne posera donc pas VIRTUAL_ENV.
        "venv": "/home/moi/develop/flutter-master",
        "expected_tests": 6,
        # Le depot est pose AVANT l'agent : cf. _init_depot.
        "depot_git": True,  # build/lancement/rendu + tests/test_dabord/historique
        # Le code produit EST le livrable ici : un tirage reussi vaut d'etre garde,
        # voire promu dans le depot du jeu.
        "archiver_projet": True,
        "protected": (),
        "check_api": False,
        # PAS de cle `etages` ici : elle est reservee aux scenarios notes par un
        # appel pytest PAR FICHIER, et le verificateur `amorce-flutter` construit
        # lui-meme ses trois etages (build / lancement / rendu). Les declarer en
        # double a fait planter la premiere campagne -- une cle qui porte deux sens
        # finit par etre lue avec le mauvais.
    },
    # SONDE. Ne mesure qu'une chose, en une minute : quand un diagnostic VRAI et
    # isole arrive colle au resultat d'une ecriture, le modele le corrige-t-il ?
    #
    # Motif : trois campagnes `crepuscule-amorce` le 2026-09-17 (consigne
    # d'ecriture, puis consigne LSP, puis capteur corrige) ont rendu trois modes
    # de panne differents et trois fois 0/6, en tirages uniques de 15 a 30
    # minutes. La variance entre bras (32 -> 0 lignes ecrites, 8 -> 37 `bash`)
    # depassait tout effet cherche : le scenario ne discrimine pas, il produit du
    # bruit avec un chiffre dessus. Et au dernier tirage le modele n'a jamais
    # lance `flutter pub get`, donc le levier n'a meme pas ete exerce.
    #
    # Ici tout est pose d'avance : dependance REELLE et resolue (`dart pub get`
    # en preparation), un seul import faux (`collections.dart` au lieu de
    # `collection.dart`) -- la forme EXACTE du mur de `crepuscule`
    # (`flutter_scene/flutter_scene.dart` au lieu de `scene.dart`) -- et une
    # erreur derivee en dessous, comme dans la vraie vie.
    #
    # Le prompt ne dit RIEN de l'erreur : il demande un ajout. C'est ce qui rend
    # la sonde discriminante -- sans capteur, rien n'oblige le modele a regarder ;
    # avec, le diagnostic arrive dans le resultat de sa propre ecriture.
    "diagnostic-import": {
        "fixture": HERE / "fixture-diagnostic-import",
        "notes_oracle": (
            "L'etage `fonction` note la tache DEMANDEE, `analyse` l'erreur latente",
            "qu'on ne signale pas. 1/2 = le modele a travaille sans regarder.",
            "La fixture est preparee par `dart pub get` : sans ca le serveur",
            "declare inexistant TOUT `package:` et la sonde mesure un faux positif.",
            "Le correctif attendu tient en un caractere : collections -> collection.",
        ),
        "prompt": HERE / "PROMPT-diagnostic-import.txt",
        "verifieur": "diagnostic-import",
        "preparation": (("dart", "pub", "get"),),
        "sdk_bin": "/home/moi/develop/flutter-master/bin",
        "venv": "/home/moi/develop/flutter-master",
        "expected_tests": 2,
        "depot_git": False,
        "archiver_projet": False,
        "protected": (),
        "check_api": False,
    },
    # PREMIER SCENARIO NON-PYTHON NOTE PAR LE CODE PRODUIT. Motif : les huit
    # scenarios historiques sont 100 % Python, donc tout levier mesure peut etre
    # un artefact Python (note ouverte depuis le 2026-08-06). `crepuscule-amorce`
    # est en Dart mais note un APK et exige un emulateur ; ici le livrable est une
    # requete, gradee en une seconde, sans rien compiler.
    #
    # Structure reprise de `microbench_16` (Zux1U) : un controle VISIBLE que le
    # modele peut lancer, et un correcteur CACHE aux cas limites. Le depot n'a
    # PAS de licence -- rien n'en est copie, ni contrat, ni donnees, ni code ;
    # seule la structure est reprise, comme `notes_oracle` l'avait ete.
    #
    # Le controle visible porte sur des donnees SAGES (`graine.sql` : deux
    # utilisateurs, une coupure franche chacun). Les cas limites -- 45 minutes
    # pile, horodatages en double, session a cheval sur minuit, utilisateur a un
    # seul evenement, evenements en desordre -- ne sont QUE dans le correcteur.
    # Un modele qui lit les donnees au lieu du contrat passe le premier et echoue
    # sur le second.
    "sql-sessions": {
        "fixture": HERE / "fixture-sql-sessions",
        "notes_oracle": (
            "SATURE sur gemma-4-12b : 6/6 aux 3 tirages, ecart 0, 5 tours (17/09).",
            "Il FILTRE (un harnais casse tombera), il ne CLASSE pas -- meme statut que",
            "`tetris`. La sessionnalisation est un exercice canonique : une part du",
            "score est de la RESTITUTION. Pour classer, il faudra durcir le contrat.",
            "Six cas independants -> credit partiel. Instrument controle le 17/09 :",
            "requete juste 6/6, requete naive 1/6 (`solitaire` passe legitimement).",
            "Les 3 requetes produites sont structurellement differentes entre elles ET",
            "de celle du controle (strftime/2700 contre julianday*1440) : le correcteur",
            "ne valide pas une forme unique.",
            "Le controle visible NE contient aucun cas limite : le passer ne prouve rien.",
            "Aucun serveur de langage ni lint pour `.sql` -> le levier diagnostic est",
            "INERTE ici. Ce scenario mesure le harnais hors de Python, pas le capteur.",
        ),
        "prompt": HERE / "PROMPT-sql-sessions.txt",
        "verifieur": "sql-sessions",
        "oracle": HERE / "oracle-sql-sessions" / "grade.py",
        # Construit la base AVANT l'agent : le contrat parle d'un fichier qui doit
        # exister, pas d'un fichier a creer.
        "preparation": (("sqlite3", "evenements.sqlite", ".read graine.sql"),),
        "expected_tests": 6,
        "depot_git": False,
        "archiver_projet": False,
        # `graine.sql` et le controle visible sont le CONTRAT : les modifier
        # reviendrait a se noter soi-meme.
        "protected": ("graine.sql", "verifie_visible.py", "SPEC.md"),
        "check_api": False,
    },
    "pronote": {
        "fixture": HERE / "fixture-pronote",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "Depot REEL de 60 fichiers / 124 000 tokens : mesure la navigation, pas l'ecriture.",
        ),
        "prompt": HERE / "PROMPT-pronote.txt",
        "oracle": HERE / "oracle-pronote" / "test_oracle_pronote.py",
        # Le paquet importe homeassistant : l'oracle tourne avec le python du projet.
        "pytest": "/data/projets/perso/pronote/.venv/bin/pytest",
        "expected_tests": 5,
        "protected": (),
        "check_api": False,
        "etages": (("oracle", "test_oracle_pronote.py", 5),),
    },
    # Fixture 4 — la SEULE qui puisse mesurer une phase de documentation. Les trois
    # autres sont en bibliotheque standard pure : une phase `chercheur` n'y serait
    # jamais sollicitee et ne couterait que ses schemas. On ne mesurerait rien.
    #
    # `attrs` a ete choisie apres une sonde, pas par intuition. Interroge sans
    # documentation, le modele produit du code PLAUSIBLE ET FAUX, de deux facons
    # independantes : `from attrs import validator` (le module est `validators`, au
    # pluriel -> ImportError) et `@couleur.validator` pose sur une annotation nue,
    # qui n'est pas un `field()` -> AttributeError. C'est exactement le regime que
    # la documentation corrige : le modele connait la FORME de la bibliotheque et se
    # trompe sur son API.
    #
    # Six modules INDEPENDANTS, un par etage : avec un module unique, le premier
    # mauvais import donnerait 0/38 et l'instrument redeviendrait binaire — le
    # defaut de `tetris`.
    "attrs": {
        "fixture": HERE / "fixture-attrs",
        # Ce que l'oracle verifie VRAIMENT, et ce qu'il ne verifie pas.
        "notes_oracle": (
            "⚠️ NE DISCRIMINE PAS SUR LE SCORE : la boucle de verification sauve le modele.",
            "Il ecrit `from attrs import validator` (inexistant), pytest rend l'ImportError,",
            "il corrige -> 38/38. Mesure du 2026-08-02. Le critere utile est le NOMBRE DE",
            "TOURS (259 pour 38 tests), pas le total.",
            "Six modules independants : sans ca, le premier mauvais import donnerait 0/38.",
        ),
        "prompt": HERE / "PROMPT-attrs.txt",
        "expected_tests": 38,
        "protected": (
            "tests/test_1_piece.py",
            "tests/test_2_evolution.py",
            "tests/test_3_serialisation.py",
            "tests/test_4_gele.py",
            "tests/test_5_derive.py",
            "tests/test_6_introspection.py",
            "conftest.py",
        ),
        "check_api": False,
        "etages": (
            ("piece", "tests/test_1_piece.py", 11),
            ("evolution", "tests/test_2_evolution.py", 7),
            ("serialisation", "tests/test_3_serialisation.py", 5),
            ("gele", "tests/test_4_gele.py", 6),
            ("derive", "tests/test_5_derive.py", 5),
            ("introspection", "tests/test_6_introspection.py", 4),
        ),
    },
}


# --- verification, independante du harnais -------------------------------


def api_signatures(root):
    """Empreinte des signatures publiques de taskmgr/ : {chemin: [signatures]}.

    Sert a detecter un renommage. C'est le point ou un quant tres bas derape en
    premier : il reecrit la bonne logique sous un autre nom.
    """
    out = {}
    for path in sorted((root / "taskmgr").glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            out[path.name] = ["SYNTAX_ERROR: %s" % exc]
            continue
        sigs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sigs.append("def %s(%s)" % (node.name, ",".join(args)))
            elif isinstance(node, ast.ClassDef):
                sigs.append("class %s" % node.name)
        out[path.name] = sorted(sigs)
    return out


def _tuer_groupe(proc):
    """Tue tout le groupe de processus (SIGTERM puis SIGKILL), pas juste l'enfant.

    Indispensable : un timeout qui ne tue que l'enfant direct laisse les
    petits-fils (bash -> pytest boucle infinie) tourner a 100% CPU en orphelins.
    """
    try:
        gid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(gid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


# Classes d'issue d'un essai. Introduites le 2026-07-29 apres avoir compris que le
# score seul MENT : les 44 tests importent tous le paquet, donc UNE erreur de syntaxe
# fait echouer la collecte, donc les 44 tests, donc 0/44. Exemple mesure : un essai a
# 0/44 avait ecrit 197 lignes et echouait sur `IndentationError: expected an indented
# block after 'if' statement on line 156`. Un caractere. Moyenner ce 0 avec un 41/44
# obtenu sur du code qui compile ne mesure pas le modele, ca mesure la probabilite
# d'une coquille — et sur 3 essais, la mediane est decidee par ce tirage.
ISSUE_OK = "collecte_ok"  # les tests ont tourne : le score veut dire quelque chose
ISSUE_COLLECTE = (
    "erreur_collecte"  # SyntaxError / IndentationError / ModuleNotFoundError
)
ISSUE_PEND = "pytest_pend"  # boucle infinie : pytest ne rend jamais la main
ISSUE_PARTIEL = "pend_balaye"  # un test boucle, les autres ont ete notes un a un


def _fichiers_de_test(racine):
    """Ensemble des fichiers que pytest COLLECTE, ou qu'il soient dans l'arbre.

    Perimetre verifie sur le cas reel : le fichier ajoute qui a donne 46/44 etait
    `reproduce_test.py` a la RACINE du workdir, pas sous `tests/`. pytest collecte
    `test_*.py` et `*_test.py` depuis son rootdir — se limiter a `tests/` ne verrait
    rien.
    """
    return {
        p.relative_to(racine).as_posix()
        for p in racine.rglob("*.py")
        if p.is_file()
        and (p.name.startswith("test_") or p.name.endswith("_test.py"))
        and "__pycache__" not in p.parts
        and ".pytest_cache" not in p.parts
    }


def _sha_prompt(nom_scenario):
    """SHA-256 de l'enonce du scenario, ou None si le FICHIER est illisible.

    Un `except Exception` global avalait ici un bug d'appelant (le dict passe a la
    place du nom) : le champ est reste a None dans TOUS les resultats jusqu'au
    2026-08-05 sans que rien ne le signale. Un scenario inconnu est une erreur de
    programmation, elle doit crier ; seul un fichier absent se degrade en None.
    """
    import hashlib

    chemin = Path(SCENARIOS[nom_scenario]["prompt"])
    try:
        brut = chemin.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(brut).hexdigest()[:16]


def _sha_contrat(nom_scenario):
    """SHA-256 des fichiers de tests PROTEGES : le contrat que le modele doit tenir.

    Motif (2026-08-05) : `prompt_sha256` ne couvre que l'enonce, or le contrat vit
    dans les DOCSTRINGS et les assertions des tests. Un resserrement de la prose de
    `test_11_rendu.py` (les tuiles en chute occupent leur case au lieu d'etre ajoutees
    apres `</table>`) ne changeait pas d'un bit l'empreinte des campagnes — les
    tirages d'avant et d'apres se seraient melanges en silence dans la meme mediane.

    Les fichiers sont hashes dans l'ordre trie, chemin inclus : renommer un etage
    change l'empreinte, comme il se doit.
    """
    import hashlib

    sc = SCENARIOS[nom_scenario]
    h = hashlib.sha256()
    # L'ORACLE fait partie du contrat, et pour un scenario a oracle CACHE il en est
    # meme la totalite : `protected` y est vide, donc sans cette ligne l'empreinte
    # serait le sha de la chaine VIDE et une modification de l'oracle passerait
    # inapercue. Meme defaut que prompt_sha256, corrige le matin du 2026-08-05.
    if sc.get("oracle"):
        try:
            h.update(Path(sc["oracle"]).read_bytes())
        except OSError:
            pass
    for rel in sorted(sc["protected"]):
        chemin = Path(sc["fixture"]) / rel
        try:
            brut = chemin.read_bytes()
        except OSError:
            continue
        h.update(rel.encode("utf-8"))
        h.update(brut)
    return h.hexdigest()[:16]


def _serveur_actif():
    """Contenu de logs-serveur/actif.json, ou None s'il n'existe pas.

    Ne leve jamais : une campagne lancee sans serveur.sh doit produire un
    resultat, simplement sans la config serveur — et l'absence est alors VISIBLE
    dans le JSON au lieu d'etre supposee.
    """
    try:
        return json.loads((HERE / "logs-serveur" / "actif.json").read_text())
    except Exception:
        return None


def _analyse_pytest(stdout):
    """(passed, failed, collecte_ratee) depuis une sortie pytest."""
    passed = failed = 0
    match = re.search(r"(\d+) passed", stdout)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", stdout)
    if match:
        failed = int(match.group(1))
    # « error during collection » = le paquet ne s'importe meme pas. pytest le dit
    # explicitement, on ne devine pas.
    ratee = "error during collection" in stdout or "errors during collection" in stdout
    return passed, failed, ratee


def _analyse_dart(stdout):
    """(passed, failed, collecte_ratee) depuis `dart test --reporter json`.

    On lit le JSON et NON la ligne lisible (« 00:00 +2 -1: Some tests failed. »),
    pour une raison precise : `dart test` n'offre aucun equivalent de `-o addopts=`,
    donc un `dart_test.yaml` de fixture peut changer le rapporteur ou supprimer le
    bilan sans que rien ne le signale. C'est exactement le defaut qui a fait lire 0/5
    sur `pronote` le 2026-08-05. Le drapeau `--reporter json` de la ligne de commande
    l'emporte sur la config, et les comptes viennent d'EVENEMENTS.

    `hidden: true` ecarte le test SYNTHETIQUE « loading test/x_test.dart » que
    package:test emet par FICHIER. Sans ce filtre, chaque fichier ajouterait un
    faux succes au score.
    """
    passed = failed = 0
    vu = False
    for ligne in stdout.splitlines():
        ligne = ligne.strip()
        if not ligne.startswith("{"):
            continue
        try:
            e = json.loads(ligne)
        except ValueError:
            continue
        if e.get("type") != "testDone" or e.get("hidden"):
            continue
        vu = True
        if e.get("result") == "success":
            passed += 1
        else:
            failed += 1
    # Aucun `testDone` = rien n'a pu etre charge (erreur de compilation Dart, paquet
    # non resolu). C'est l'equivalent de « error during collection » de pytest, et il
    # faut le distinguer d'un vrai 0/N sinon un echec de build se lirait comme un
    # modele qui n'a rien fait passer.
    return passed, failed, not vu


LANCEURS = {
    "pytest": (
        # `-o addopts=` : la config pytest de la FIXTURE ne doit pas piloter la mesure.
        lambda binaire, cibles: [binaire, "-o", "addopts=", "-q", *cibles],
        _analyse_pytest,
    ),
    "dart": (
        lambda binaire, cibles: [binaire, "test", "--reporter", "json", *cibles],
        _analyse_dart,
    ),
}


TIMEOUT_SUITE = int(os.environ.get("BENCH_TIMEOUT_SUITE", "180"))
TIMEOUT_PAR_TEST = int(os.environ.get("BENCH_TIMEOUT_PAR_TEST", "15"))
BUDGET_BALAYAGE = int(os.environ.get("BENCH_BUDGET_BALAYAGE", "600"))


def _balayage_par_test(workdir, cibles, binaire):
    """Note la suite test par test quand elle a PENDU en bloc. Retourne None si echec.

    Motif, mesure le 2026-09-14 sur mellum2-12b-a2.5b : DEUX essais sur trois ont
    ete jetes en `pytest_pend`, et la campagne a conclu 0/44. Rejoues test par
    test, ces deux essais donnent 33/44 et 28/44 -- un seul et meme test bouclait,
    `test_soft_drop_echoue_au_fond`. Un `return (0, 0)` sur le gel ne mesure donc
    pas le modele, il mesure sa malchance sur UN test.

    La portee depasse ce candidat : 9 campagnes sur 138 portent au moins un essai
    pendu, dont deux de l'incumbent et une de gemma-qat a 44/44 de mediane. Elles
    ont survecu parce qu'il leur restait deux essais comparables ; c'est un sursis,
    pas une immunite.

    Un test qui ne termine pas compte comme ECHOUE -- il ne passe pas. Ce qu'on
    recupere, c'est le sort des 43 autres.
    """
    argv_de, _ = LANCEURS["pytest"]
    try:
        col = subprocess.run(
            argv_de(binaire or PYTEST, cibles) + ["--collect-only"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None
    ids = [l.strip() for l in (col.stdout or "").splitlines() if "::" in l]
    if not ids:
        return None

    debut = time.time()
    passed = failed = 0
    pendus = []
    for tid in ids:
        if time.time() - debut > BUDGET_BALAYAGE:
            return None  # trop long : on retombe sur l'ancien comportement
        un = subprocess.Popen(
            argv_de(binaire or PYTEST, [tid]),
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            un.communicate(timeout=TIMEOUT_PAR_TEST)
            if un.returncode == 0:
                passed += 1
            else:
                failed += 1
        except subprocess.TimeoutExpired:
            _tuer_groupe(un)
            un.communicate()
            failed += 1
            pendus.append(tid.rsplit("::", 1)[-1])
    return passed, failed, pendus


def run_pytest(workdir, cibles=(), binaire=None, lanceur="pytest"):
    """Retourne (passed, failed, sortie_courte, issue).

    Le depassement de delai est un RESULTAT, pas un plantage du banc : du code
    genere qui boucle a l'infini fait pendre pytest, et c'est un mode de
    defaillance attendu. On le rapporte au lieu de laisser l'exception remonter.

    `issue` distingue les trois classes ci-dessus. Sans elle, le banc ne peut pas
    comparer deux reglages voisins : les 0/44 de collecte noient le signal.

    `cibles` restreint la notation aux fichiers du CONTRAT. Motif (2026-07-30) : un
    essai a affiche 46/44 parce que le modele avait ecrit son propre
    `reproduce_test.py`, collecte par pytest. Ecrire un test de reproduction est un
    BON reflexe qu'on veut encourager — ce qu'il ne faut pas, c'est que ca gonfle le
    score et rende les tirages incomparables. On note donc le contrat, et le modele
    reste libre d'ajouter ce qu'il veut a cote.
    """
    # start_new_session + killpg : pytest peut avoir spawn des sous-process ;
    # sans groupe, le timeout les laisserait orphelins (cf. _tuer_groupe).
    # `-o addopts=` : la configuration pytest de la FIXTURE ne doit pas piloter la
    # mesure. Constate le 2026-08-05 sur `pronote`, dont pyproject.toml porte
    # `addopts = "-ra -q --strict-markers"` : ajoute au `-q` du banc, ca donne -qq,
    # qui SUPPRIME la ligne de bilan. Le banc lisait donc 0/5 sur un oracle qui
    # echouait proprement a 2 echecs / 3 reussis. Un depot peut aussi y mettre
    # --cov, -x ou un timeout par test, et chacun changerait le score sans que rien
    # ne le signale. Les options de fichier (asyncio_mode, testpaths) restent, elles.
    argv_de, analyse = LANCEURS[lanceur]
    proc = subprocess.Popen(
        argv_de(binaire or PYTEST, cibles),
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=TIMEOUT_SUITE)
    except subprocess.TimeoutExpired:
        _tuer_groupe(proc)
        proc.communicate()
        # La suite a pendu EN BLOC. Avant de jeter l'essai, on la rejoue test par
        # test : le gel vient presque toujours d'UN test, et les autres portent une
        # mesure valide (cf. _balayage_par_test).
        bal = _balayage_par_test(workdir, cibles, binaire) if lanceur == "pytest" else None
        if bal is not None:
            passed, failed, pendus = bal
            return (
                passed,
                failed,
                "balaye test par test apres gel : %d passent, %d echouent (pendus: %s)"
                % (passed, failed, ", ".join(pendus) or "aucun"),
                ISSUE_PARTIEL,
            )
        return (
            0,
            0,
            "TIMEOUT %s apres %ds (boucle infinie dans le code genere)"
            % (lanceur, TIMEOUT_SUITE),
            ISSUE_PEND,
        )
    stdout = stdout or ""
    tail = stdout.strip().splitlines()[-1:] or [""]
    passed, failed, collecte_ratee = analyse(stdout)
    issue = ISSUE_COLLECTE if collecte_ratee else ISSUE_OK
    return passed, failed, tail[0], issue


# --- verificateurs non-pytest ---------------------------------------------
#
# Certains scenarios ne se notent pas par une suite de tests. `crepuscule-amorce`
# demande de CREER UN PROJET a partir d'un repertoire vide et d'une spec : ce qui se
# verifie alors, c'est que le projet se construit, s'installe et affiche quelque
# chose. Trois assertions, dont DEUX mecaniques et UNE heuristique -- et il faut
# dire laquelle est laquelle.

PART_DOMINANTE_MAX = 0.90

# Marqueurs du gabarit ecrit par `flutter create`. Leur presence dans lib/ signifie
# que l'agent n'a PAS remplace l'application de demonstration.
#
# Motif (2026-09-14) : un tirage a ete note 3/3 alors que l'emulateur affichait
# « Flutter Demo Home Page » et le compteur de clics. L'etage `rendu` est une
# heuristique de couleur (dominante < 90 %) calibree contre un ECRAN VIDE (98 %) et
# un cube ombre (78,9 %) -- jamais contre le GABARIT, qui sort a 86,8 % et passe
# donc avec 3 points de marge. Or le gabarit est la sortie fausse la PLUS probable,
# puisque `flutter create` la produit toute seule : il suffit que l'agent cree le
# projet et n'ecrive rien.
#
# Le garde est deterministe la ou l'etage est heuristique : on ne devine pas ce que
# l'image montre, on constate que le code n'a pas bouge.
MARQUEURS_GABARIT_FLUTTER = (
    "You have pushed the button this many times",
    "_incrementCounter",
)


# La bibliotheque que l'enonce NOMME. Un projet qui ne la declare ni ne l'importe
# n'a pas fait la tache, quoi qu'affiche l'ecran.
#
# Motif (2026-09-15) : qwen3-coder-reap-25b a fait passer l'etage `build` en
# SUPPRIMANT l'exigence — pubspec sans `flutter_scene`, main.dart de 57 lignes
# affichant le texte « FLUTTER GPU OK », aucun cube, aucune camera. Puis il a
# appele `finish` et declare la tache terminee. L'APK se construit parce qu'il
# n'y a plus rien a construire.
#
# C'est la meme faille que le gabarit `flutter create` corrige en 245772f4, par
# l'autre bout : la premiere laissait le code d'origine, celle-ci ecrit du code
# neuf mais vide. Les deux franchissent une heuristique d'image.
BIBLIOTHEQUE_EXIGEE = "flutter_scene"

# Les trois etages de METHODE, ajoutes le 2026-09-15. Motif : les etages
# build/lancement/rendu mesurent un ARTEFACT. Deux harnais peuvent produire le
# meme APK en travaillant tres differemment -- l'un en commitant une fois a la
# fin, l'autre en cycles rouge-vert. C'est cette difference qui departage les
# deux configurations gagnantes, et elle etait invisible.
#
# Tout est verifie par machine : `flutter test`, et `git log`. Aucune heuristique,
# aucun jugement -- on a vu ce que coute une heuristique (le gabarit
# `flutter create` note 3/3 le 2026-09-14).
TYPES_CONVENTIONNELS = (
    "feat", "fix", "test", "chore", "docs", "refactor", "build", "ci", "style", "perf",
)
MOTIF_CONVENTIONNEL = re.compile(
    r"^(%s)(\([^)]+\))?!?: .+" % "|".join(TYPES_CONVENTIONNELS)
)
COMMITS_MINIMUM = 3


def _commits(projet):
    """[(sha, sujet, [fichiers])] du plus ANCIEN au plus recent, ou None.

    Separateur NUL entre champs et double NUL entre commits : un sujet de commit
    peut contenir n'importe quel caractere imprimable, y compris des sauts de
    ligne apres un `--format` mal choisi.
    """
    code, sortie = _lance(
        ["git", "log", "--reverse", "--name-only", "--format=%x00%x00%H%x00%s"],
        cwd=str(projet),
        timeout=60,
    )
    if code != 0:
        # `git log` sort en erreur sur un depot VIDE comme sur une absence de
        # depot. Les confondre produirait la note « pas de depot git lisible »
        # alors que le banc en a pose un lui-meme -- un motif faux envoie
        # chercher la panne au mauvais endroit.
        present, _ = _lance(["git", "rev-parse", "--git-dir"], cwd=str(projet), timeout=30)
        return [] if present == 0 else None
    commits = []
    for bloc in sortie.split("\0\0"):
        if not bloc.strip():
            continue
        champs = bloc.split("\0")
        if len(champs) < 2:
            continue
        sha = champs[0].strip()
        lignes = champs[1].splitlines()
        sujet = lignes[0].strip() if lignes else ""
        fichiers = [x.strip() for x in lignes[1:] if x.strip()]
        if sha:
            commits.append((sha, sujet, fichiers))
    return _relativise(projet, commits)


def _relativise(projet, commits):
    """Reecrit les chemins de `git log` relativement au PROJET.

    `git log --name-only` rend des chemins relatifs a la racine du DEPOT. Or le
    banc pose le depot sur le workdir et l'agent cree souvent son projet dans un
    sous-repertoire : les chemins arrivent alors en `crepuscule/lib/main.dart`,
    et le test `startswith("lib/")` de l'etage `test_dabord` ne matche JAMAIS --
    un cycle rouge-vert parfait serait note en echec.

    Les fichiers hors du projet (la SPEC a la racine du workdir) sont retires :
    ils ne disent rien de la methode de developpement.
    """
    code, racine = _lance(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(projet), timeout=30
    )
    if code != 0:
        return commits
    try:
        prefixe = Path(projet).resolve().relative_to(Path(racine.strip()).resolve())
    except ValueError:
        return commits
    if prefixe == Path("."):
        return commits
    tete = str(prefixe) + "/"
    return [
        (sha, sujet, [f[len(tete):] for f in fichiers if f.startswith(tete)])
        for sha, sujet, fichiers in commits
    ]


def _verifie_methode(projet, etage, flutter="flutter"):
    """Ajoute les etages `tests`, `test_dabord` et `historique`.

    `flutter` vient du SCENARIO : le banc cible flutter-master, et le `flutter`
    du PATH est la branche stable. Mesurer la suite avec un autre SDK que celui
    qui a construit l'APK ne veut rien dire.
    """
    # --- tests : la suite passe, et au moins un test n'est pas le gabarit ---
    code, sortie = _lance([flutter, "test"], cwd=str(projet), timeout=900)
    suite_verte = code == 0
    propre = False
    dossier = Path(projet) / "test"
    if dossier.is_dir():
        for f in dossier.rglob("*.dart"):
            try:
                texte = f.read_text(errors="replace")
            except OSError:
                continue
            # Le gabarit de `flutter create` teste le compteur de demonstration.
            if "Counter increments smoke test" not in texte and "testWidgets" not in texte:
                propre = True
            elif "Counter increments smoke test" not in texte:
                propre = True
    etage(
        "tests",
        suite_verte and propre,
        "flutter test %s ; test propre : %s"
        % ("passe" if suite_verte else "echoue", propre),
    )

    commits = _commits(projet)
    if commits is None:
        etage("test_dabord", False, "pas de depot git lisible")
        etage("historique", False, "pas de depot git lisible")
        return

    # --- test d'abord : un commit qui touche test/ sans lib/, puis un sur lib/ ---
    rouge = None
    vert = False
    for n, (_sha, _sujet, fichiers) in enumerate(commits):
        touche_test = any(f.startswith("test/") for f in fichiers)
        touche_lib = any(f.startswith("lib/") for f in fichiers)
        if rouge is None and touche_test and not touche_lib:
            rouge = n
        elif rouge is not None and touche_lib:
            vert = True
            break
    etage(
        "test_dabord",
        vert,
        "aucun cycle rouge-vert : il faut un commit test/ SANS lib/, puis un commit lib/",
    )

    # --- historique : assez de commits, tous au format conventionnel ---
    propres = [s for _h, s, _f in commits if MOTIF_CONVENTIONNEL.match(s)]
    assez = len(commits) >= COMMITS_MINIMUM
    tous = len(propres) == len(commits) and commits
    etage(
        "historique",
        bool(assez and tous),
        "%d commit(s), %d au format conventionnel (minimum %d, tous conformes)"
        % (len(commits), len(propres), COMMITS_MINIMUM),
    )



def _bibliotheque_absente(projet):
    """Vrai si `flutter_scene` n'est ni declare dans le pubspec ni importe."""
    projet = Path(projet)
    pubspec = projet / "pubspec.yaml"
    try:
        declare = BIBLIOTHEQUE_EXIGEE in pubspec.read_text(errors="replace")
    except OSError:
        declare = False
    importe = False
    lib = projet / "lib"
    if lib.is_dir():
        for source in lib.rglob("*.dart"):
            try:
                if BIBLIOTHEQUE_EXIGEE in source.read_text(errors="replace"):
                    importe = True
                    break
            except OSError:
                continue
    return not (declare and importe)


def _gabarit_intact(projet):
    """Vrai si lib/ porte encore l'application de demonstration de `flutter create`."""
    lib = Path(projet) / "lib"
    if not lib.is_dir():
        return False
    for source in lib.rglob("*.dart"):
        try:
            texte = source.read_text(errors="replace")
        except OSError:
            continue
        if any(m in texte for m in MARQUEURS_GABARIT_FLUTTER):
            return True
    return False

# Seuil MESURE, pas devine : une scene flutter_scene VIDE, capturee sur l'emulateur
# le 2026-08-06, met 98,0 % de ses pixels dans une seule couleur (254, 247, 255). Le
# nombre de couleurs DISTINCTES serait un mauvais discriminant -- l'antialiasing du
# texte et la barre d'etat en donnent deja 1019 sur un ecran vide. La PART de la
# dominante, elle, chute des qu'un objet ombre est rendu. 0,90 laisse de la marge
# sous les 0,98 observes. C'est une heuristique : elle dit « quelque chose est
# dessine », pas « le bon rendu ».
DELAI_LANCEMENT_S = 15
# On SONDE jusqu'a ce que quelque chose soit rendu, au lieu d'attendre un delai fixe.
# Mesure du 2026-08-07 : a 15 s, la capture montrait l'ECRAN DE DEMARRAGE de Flutter
# (98,7 % de couleur dominante) sur un projet qui par ailleurs compilait, s'installait
# et tournait. La faute etait a l'instrument, pas au sujet -- le code de l'agent attend
# `Scene.initializeStaticResources()` AVANT `runApp`, donc rien ne s'affiche tant que
# le bundle de shaders et la LUT BRDF ne sont pas charges. Un delai fixe devine ; une
# condition mesure. Et le TEMPS d'apparition devient lui-meme une metrique.
DELAI_RENDU_MAX_S = 90
DELAI_LANCEMENT_MAX_S = 900  # compilation + installation + demarrage, demon froid
PAS_SONDE_RENDU_S = 5


def _identifiant_application(workdir):
    """`applicationId` du projet, LU et non suppose. None si introuvable.

    On ne peut pas le coder en dur : c'est l'AGENT qui cree le projet, donc lui qui
    choisit le nom. Le supposer ferait echouer l'oracle sur un projet par ailleurs
    correct -- un modele accuse pour une convention qu'on ne lui a pas imposee.
    """
    for nom in ("android/app/build.gradle.kts", "android/app/build.gradle"):
        chemin = Path(workdir) / nom
        if not chemin.exists():
            continue
        trouve = re.search(
            r"""applicationId\s*=?\s*["']([\w.]+)["']""",
            chemin.read_text(errors="replace"),
        )
        if trouve:
            return trouve.group(1)
    return None


def _part_dominante(png):
    """Part du pixel le plus frequent, ou None si l'image est illisible."""
    try:
        from PIL import Image
    except ImportError:
        return None
    import io

    try:
        image = Image.open(io.BytesIO(png)).convert("RGB")
        couleurs = image.getcolors(maxcolors=2_000_000)
    except Exception:  # noqa: BLE001 - lecture d'image, ne doit jamais tuer le banc
        return None
    if not couleurs:
        return None
    total = image.size[0] * image.size[1]
    return max(n for n, _ in couleurs) / total


def _racine_projet(workdir):
    """Repertoire du projet Flutter : celui qui contient `pubspec.yaml`. None sinon.

    DECOUVERTE STRUCTURELLE et non supposition. La premiere campagne du 2026-08-07 a
    note 0/3 en partie parce que ce verificateur cherchait l'APK a la RACINE du
    workdir, alors que l'agent avait legitimement fait
    `flutter create amorce_crepuscule` -- donc un sous-repertoire. L'oracle aurait
    note 0/3 sur un projet PARFAIT.

    On prend le plus PROCHE de la racine : un projet Flutter contient des
    `pubspec.yaml` imbriques (exemples, paquets), et le bon est le moins profond.
    """
    racine = Path(workdir)
    if (racine / "pubspec.yaml").is_file():
        return racine
    trouves = sorted(
        (c.parent for c in racine.glob("*/pubspec.yaml") if c.is_file()),
        key=lambda c: len(str(c)),
    )
    return trouves[0] if trouves else None


def _lance(argv, **kw):
    """subprocess.run qui ne LEVE JAMAIS. Rend (code, sortie).

    Un binaire absent (SDK mal declare, `adb` introuvable) faisait remonter un
    FileNotFoundError et tuait la CAMPAGNE ENTIERE au lieu de noter un etage echoue.
    Trouve par un test, pas en production -- mais c'est exactement la classe de defaut
    qui a fait perdre des heures aujourd'hui : l'outil de mesure qui tombe au lieu de
    rapporter.
    """
    try:
        fin = subprocess.run(argv, capture_output=True, text=True, **kw)
        return fin.returncode, (fin.stdout or "") + (fin.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, "%s : %s" % (type(exc).__name__, exc)


def _attend_lancement(proc, delai=DELAI_LANCEMENT_MAX_S):
    """True des que `flutter run` annonce l'application lancee. Ne leve jamais.

    On lit la SORTIE plutot que d'attendre un delai : la compilation, l'installation
    et le demarrage prennent un temps tres variable (demon gradle froid, emulateur
    charge). Un delai fixe devine ; une condition mesure.
    """
    debut = time.time()
    while time.time() - debut < delai:
        if proc.poll() is not None:
            return False
        ligne = proc.stdout.readline() if proc.stdout else ""
        if not ligne:
            time.sleep(0.5)
            continue
        if "Flutter run key commands" in ligne or "Application finished" in ligne:
            return "key commands" in ligne
    return False


def _init_depot(workdir):
    """Depot git vide dans le workdir, AVANT le lancement de l'agent.

    Deux raisons, aucune n'est une faveur faite a un harnais :

    1. La SPEC (§3bis) note l'HISTORIQUE. Un depot est le support de la mesure,
       pas la mesure : tout le contenu de l'historique reste le travail de
       l'agent, qui part de zero commit.
    2. La detection des serveurs de langage est cwd-only AU DEMARRAGE chez omp
       (et de forme voisine ailleurs). Sans marqueur racine au lancement, dartls
       ne demarre jamais -- silencieusement -- et on mesurerait un defaut
       d'instrument au lieu d'un harnais.

    La signature GPG est coupee LOCALEMENT : elle est active dans le gitconfig
    global (role ansible dev-workstation) et bloquerait l'agent sur une demande
    de phrase de passe, sans aucun message lisible.
    """
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.name", "banc"],
        ["config", "user.email", "banc@harness-bench.local"],
        ["config", "commit.gpgsign", "false"],
    ):
        subprocess.run(["git", "-C", str(workdir)] + args, check=True)


# Source UNIQUE des etages de `crepuscule-amorce`. Les enumerer a la main dans le
# verificateur ET dans ses tests les a fait diverger des l'ajout des trois etages
# de methode : les tests exigeaient toujours trois etages quand le banc en rendait
# six. L'ordre est celui du rapport : resultat d'abord, methode ensuite.
ETAGES_AMORCE = ("build", "lancement", "rendu", "tests", "test_dabord", "historique")


def _verifie_amorce_flutter(workdir, scenario):
    """(passed, failed, tail, issue, etages) pour `crepuscule-amorce`.

    Six etages INDEPENDANTS, pour que le score soit informatif plutot que binaire :
    un projet qui compile mais n'affiche rien doit se distinguer d'un projet qui ne
    compile pas, et un resultat juste obtenu sans methode doit se distinguer d'un
    resultat juste obtenu en TDD avec un historique lisible.
    """
    sdk = scenario.get("sdk_bin") or ""
    flutter = str(Path(sdk) / "flutter") if sdk else "flutter"
    adb = scenario.get("adb") or "adb"
    etages, notes = {}, []

    def etage(nom, ok, detail=""):
        etages[nom] = {
            "passed": 1 if ok else 0,
            "failed": 0 if ok else 1,
            "attendus": 1,
            "issue": ISSUE_OK,
            "verdict": "PASS" if ok else "FAIL",
        }
        # SEULEMENT en cas d'echec : le detail etait ajoute meme quand l'etage passait,
        # produisant une note qui contredisait son verdict.
        if detail and not ok:
            notes.append("[%s] %s" % (nom, detail))
        return ok

    def bilan():
        passed = sum(e["passed"] for e in etages.values())
        return passed, len(etages) - passed, "\n".join(notes), ISSUE_OK, etages

    # OU est le projet : trouve, jamais suppose (cf. _racine_projet).
    projet = _racine_projet(workdir)
    if projet is None:
        for nom in ETAGES_AMORCE:
            etage(nom, False, "aucun pubspec.yaml : pas de projet Flutter")
        return 0, len(etages), "\n".join(notes), ISSUE_COLLECTE, etages
    if projet != Path(workdir):
        notes.append("[projet] %s" % projet.relative_to(workdir))

    # 1. MECANIQUE : est-ce que ca compile ?
    code, sortie = _lance(
        [flutter, "build", "apk", "--debug"], cwd=str(projet), timeout=1800
    )
    apk = projet / "build/app/outputs/flutter-apk/app-debug.apk"
    if not etage("build", code == 0 and apk.exists(), sortie[-300:] if code else ""):
        # Sans APK, les deux etages suivants n'ont rien a mesurer. On les note echoues
        # EXPLICITEMENT plutot que de les omettre : un etage absent se lirait comme un
        # etage reussi dans un agregat.
        etage("lancement", False, "pas d'APK")
        etage("rendu", False, "pas d'APK")
        # Les etages de METHODE restent mesurables sans APK : les tests et
        # l'historique git ne dependent pas de la compilation Android.
        _verifie_methode(projet, etage, flutter)
        reussis = sum(e["passed"] for e in etages.values())
        return reussis, len(etages) - reussis, "\n".join(notes), ISSUE_COLLECTE, etages

    # Appareil LU depuis `adb devices`, pas code en dur.
    _, liste = _lance([adb, "devices"], timeout=60)
    appareils = [
        ligne.split()[0]
        for ligne in liste.splitlines()[1:]
        if ligne.strip().endswith("device")
    ]

    # 2. MECANIQUE : est-ce que ca se lance ?
    #
    # Par `flutter run` et NON par `adb install` + `monkey`, pour une raison MESUREE le
    # 2026-08-07 : `--enable-flutter-gpu` et `--enable-impeller` sont des drapeaux de
    # MOTEUR, passes au lancement. Un APK installe puis demarre par `monkey` ne les a
    # pas, donc `Scene.initializeStaticResources()` n'aboutit jamais et l'application
    # reste sur l'ecran de demarrage de Flutter.
    #
    # Ce que ca a coute : le tirage r2 a ete note 2/3 alors qu'il valait 3/3. Relance a
    # la main avec les drapeaux, SON code affiche un cube ombre correctement (dominante
    # 78,9 % contre 98,7 % sans). L'etage `rendu` etait donc INATTEIGNABLE par
    # construction, et le scenario plafonnait a 2/3 quoi que produise l'agent.
    argv = [flutter, "run", "--enable-flutter-gpu", "--enable-impeller"]
    if appareils:
        argv += ["-d", appareils[0]]
    try:
        lancement = subprocess.Popen(
            argv,
            cwd=str(projet),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        etage("lancement", False, "%s : %s" % (type(exc).__name__, exc))
        etage("rendu", False, "application non lancee")
        return bilan()

    try:
        if not etage(
            "lancement",
            _attend_lancement(lancement),
            "l'application n'a pas demarre en %ds" % DELAI_LANCEMENT_MAX_S,
        ):
            etage("rendu", False, "application non lancee")
            return bilan()

        # 3. HEURISTIQUE : est-ce que quelque chose est dessine ? On SONDE jusqu'a ce
        #    que ce soit le cas -- un delai fixe devine, une condition mesure. Et le
        #    TEMPS d'apparition devient lui-meme une metrique.
        capture, part, attendu = b"", None, 0
        while True:
            try:
                capture = (
                    subprocess.run(
                        [adb, "exec-out", "screencap", "-p"],
                        capture_output=True,
                        timeout=120,
                    ).stdout
                    or b""
                )
            except (OSError, subprocess.SubprocessError):
                capture = b""
            part = _part_dominante(capture)
            if (
                part is not None and part < PART_DOMINANTE_MAX
            ) or attendu >= DELAI_RENDU_MAX_S:
                break
            time.sleep(PAS_SONDE_RENDU_S)
            attendu += PAS_SONDE_RENDU_S

        # La capture est ARCHIVEE, pas seulement jugee : `rendu` est le seul etage
        # heuristique des trois, et livrer l'image permet a l'humain de trancher d'un
        # coup d'oeil ce qu'un seuil ne peut que suggerer. Motif `apercu_visuel` du
        # projet `jeux_zoe`. C'est en REGARDANT une capture que le defaut ci-dessus a
        # ete trouve, apres deux hypotheses fausses.
        if capture:
            try:
                RESULTS.mkdir(exist_ok=True)
                cible = RESULTS / ("%s.png" % Path(workdir).name)
                cible.write_bytes(capture)
                notes.append("[capture] %s" % cible.name)
            except OSError:
                pass
        _verifie_methode(projet, etage, flutter)
        if _bibliotheque_absente(projet):
            etage(
                "rendu",
                False,
                "`%s` n'est ni declare dans pubspec.yaml ni importe dans lib/ "
                "-- la tache a ete contournee, pas faite" % BIBLIOTHEQUE_EXIGEE,
            )
        elif _gabarit_intact(projet):
            # Inutile de juger l'image : le code est celui de `flutter create`.
            etage(
                "rendu",
                False,
                "gabarit `flutter create` intact dans lib/ (compteur de demonstration) "
                "-- l'agent n'a pas ecrit de scene",
            )
        elif part is None:
            etage("rendu", False, "capture illisible (Pillow absent ?)")
        else:
            ok = part < PART_DOMINANTE_MAX
            if ok:
                notes.append(
                    "[rendu] apparu apres %ds (dominante %.1f %%)"
                    % (attendu, part * 100)
                )
            etage(
                "rendu",
                ok,
                "toujours uniforme apres %ds : dominante %.1f %% (plancher mesure : "
                "98,0 %% sur ecran vide)" % (DELAI_RENDU_MAX_S, part * 100),
            )
        return bilan()
    finally:
        # `flutter run` tourne en avant-plan : sans ce kill de GROUPE, chaque tirage
        # laisserait un processus et son daemon gradle derriere lui.
        _tuer_groupe(lancement)
        lancement.communicate()


def _verifie_diagnostic_import(workdir, scenario):
    """(passed, failed, tail, issue, etages) pour `diagnostic-import`.

    Deux etages, et leur SEPARATION est tout l'interet de la sonde :

      `fonction` : le modele a-t-il fait ce qu'on lui a demande ?
      `analyse`  : a-t-il vu, et corrige, l'erreur latente qu'on ne lui a PAS
                   signalee ?

    Un modele qui ecrit `moyenne` sans toucher a l'import faux fait 1/2 : il a
    travaille, il n'a pas regarde. C'est exactement l'observation du
    2026-09-17 sur `crepuscule-amorce`, ramenee de trente minutes a une.
    """
    sdk = scenario.get("sdk_bin") or ""
    dart = str(Path(sdk) / "dart") if sdk else "dart"
    etages, notes = {}, []

    def etage(nom, ok, detail=""):
        etages[nom] = {
            "passed": 1 if ok else 0,
            "failed": 0 if ok else 1,
            "attendus": 1,
            "issue": ISSUE_OK,
            "verdict": "PASS" if ok else "FAIL",
        }
        if detail and not ok:
            notes.append("[%s] %s" % (nom, detail))
        return ok

    source = ""
    cible = Path(workdir) / "bin" / "main.dart"
    try:
        source = cible.read_text(encoding="utf-8")
    except OSError:
        pass
    # La signature EXACTE demandee, ET le programme qui tourne. Un `grep` seul ne
    # suffit pas : mesure du 2026-09-17, un tirage a rendu `moyenne` correcte mais
    # appelee depuis un `main_updated()` mort, et l'etage notait 1/1 un travail a
    # moitie fait. On exige donc les DEUX sorties demandees (la liste, puis la
    # moyenne), ce qui ne peut venir que d'un `main` qui appelle vraiment.
    declaree = re.search(r"\bint\s+moyenne\s*\(", source) is not None
    execution = subprocess.run(
        [dart, "run", "bin/main.dart"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    lignes = [ligne for ligne in execution.stdout.splitlines() if ligne.strip()]
    etage(
        "fonction",
        declaree and execution.returncode == 0 and len(lignes) >= 2,
        "declaree=%s rc=%s lignes=%d" % (declaree, execution.returncode, len(lignes)),
    )
    # `--no-fatal-warnings` : on note les ERREURS, comme le capteur LSP ne
    # remonte que la severite 1. Sinon un avertissement de style ferait echouer
    # un etage qui ne parle pas de style.
    analyse = subprocess.run(
        [dart, "analyze", "--no-fatal-warnings"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
    )
    etage(
        "analyse",
        analyse.returncode == 0,
        (analyse.stdout or analyse.stderr).strip()[-400:],
    )
    passed = sum(e["passed"] for e in etages.values())
    failed = sum(e["failed"] for e in etages.values())
    return passed, failed, "\n".join(notes), ISSUE_OK, etages


def _verifie_sql_sessions(workdir, scenario):
    """(passed, failed, tail, issue, etages) pour `sql-sessions`.

    Delegue au correcteur CACHE (`oracle-sql-sessions/grade.py`), depose par
    `verify()` au moment de noter. Six cas independants, chacun un etage : une
    requete qui gere tout sauf les horodatages en double doit se distinguer d'une
    requete fausse partout. Controle de l'instrument le 2026-09-17 : une requete
    juste fait 6/6, une requete naive 1/6 (`solitaire` passe, et c'est un vrai
    credit partiel -- un evenement unique forme bien une session de duree 0).
    """
    grade = Path(workdir) / Path(scenario["oracle"]).name
    proc = subprocess.run(
        [sys.executable, str(grade), str(workdir)],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        resultats = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        # Le correcteur n'a pas parle : c'est un defaut d'INSTRUMENT, pas un
        # score. On le dit, plutot que de rendre un zero qui passerait pour une
        # mesure (piege deja paye le 2026-09-17 sur `erreur_collecte`).
        detail = (proc.stderr or proc.stdout).strip()[-400:]
        return 0, scenario["expected_tests"], "[correcteur] " + detail, "erreur_collecte", {}
    etages, notes = {}, []
    for nom, r in resultats.items():
        ok = bool(r.get("ok"))
        etages[nom] = {
            "passed": 1 if ok else 0,
            "failed": 0 if ok else 1,
            "attendus": 1,
            "issue": ISSUE_OK,
            "verdict": "PASS" if ok else "FAIL",
        }
        if not ok and r.get("detail"):
            notes.append("[%s] %s" % (nom, r["detail"][:200]))
    passed = sum(e["passed"] for e in etages.values())
    failed = sum(e["failed"] for e in etages.values())
    return passed, failed, "\n".join(notes), ISSUE_OK, etages


VERIFIEURS = {
    "amorce-flutter": _verifie_amorce_flutter,
    "diagnostic-import": _verifie_diagnostic_import,
    "sql-sessions": _verifie_sql_sessions,
}


def verify(workdir, scenario):
    """Verdict objectif : tests verts, gardes respectees, API intacte."""
    fixture = scenario["fixture"]
    # ORACLE CACHE : depose dans le workdir au moment de NOTER seulement. Sur
    # `columns-web` les tests sont dans la fixture — la tache y est « fais passer ces
    # tests ». Sur `pronote` la tache est « diagnostique depuis un symptome », donc
    # des tests visibles donneraient la reponse au lieu de la faire trouver.
    # Meme discipline que la solution de reference de columns-web, gardee hors du depot.
    if scenario.get("oracle"):
        shutil.copy(scenario["oracle"], Path(workdir) / Path(scenario["oracle"]).name)
    expected = scenario["expected_tests"]
    # On note le CONTRAT : les fichiers de test proteges, et eux seuls. Un test que le
    # modele s'ecrit pour lui (reproduction, exploration) est un bon reflexe, pas une
    # infraction — il ne doit simplement pas entrer dans le score.
    contrat = [rel for rel in scenario["protected"] if "test" in Path(rel).name]
    etages = {}
    # Scenario note autrement que par une suite de tests (cf. VERIFIEURS).
    if scenario.get("verifieur"):
        passed, failed, tail, issue, etages = VERIFIEURS[scenario["verifieur"]](
            workdir, scenario
        )
    elif scenario.get("etages"):
        # Un appel pytest PAR etage : une erreur d'import dans le fichier
        # d'extension interrompt la collecte de toute la suite, ce qui ferait
        # perdre le score de non-regression (mesure : un modele qui n'ecrit rien
        # afficherait 0/62 au lieu de 44/62).
        passed = failed = 0
        tail, issue = "", None
        for nom, fichier, attendu in scenario["etages"]:
            p, f, t, iss = run_pytest(
                workdir, cibles=[fichier], binaire=scenario.get("pytest")
            )
            etages[nom] = {
                "passed": p,
                "failed": f,
                "attendus": attendu,
                "issue": iss,
                "verdict": "PASS" if p == attendu and not f else "FAIL",
            }
            passed += p
            failed += f
            if iss and issue is None:
                issue = iss
            if t:
                tail = ("%s\n[%s]\n%s" % (tail, nom, t)).strip()
    else:
        passed, failed, tail, issue = run_pytest(
            workdir, cibles=contrat, binaire=scenario.get("pytest")
        )

    violations = []
    for rel in scenario["protected"]:
        before = (fixture / rel).read_bytes()
        after_path = workdir / rel
        if not after_path.exists():
            violations.append("%s supprime" % rel)
        elif after_path.read_bytes() != before:
            violations.append("%s modifie" % rel)

    # Les tests que le modele a ajoutes : PAS une violation, une observation. On les
    # remonte parce que c'est un comportement qu'on veut voir et peut-etre encourager.
    ajoutes = sorted(_fichiers_de_test(workdir) - _fichiers_de_test(fixture))

    api_diff = []
    if scenario["check_api"]:
        before_api = api_signatures(fixture)
        after_api = api_signatures(workdir)
        for name in sorted(set(before_api) | set(after_api)):
            if before_api.get(name) != after_api.get(name):
                api_diff.append(
                    {
                        "fichier": name,
                        "avant": before_api.get(name),
                        "apres": after_api.get(name),
                    }
                )

    modified = []
    for path in sorted(workdir.rglob("*.py")):
        rel = path.relative_to(workdir).as_posix()
        origin = fixture / rel
        if not origin.exists() or origin.read_bytes() != path.read_bytes():
            modified.append(rel)

    return {
        "verdict": (
            "PASS"
            if passed == expected and not failed and not violations and not api_diff
            else "FAIL"
        ),
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_attendus": expected,
        # Vide hors scenario a deux etages. Sert a lire une defaillance : 44 en
        # regression et 0 en extension = « n'a pas su etendre » ; moins de 44 en
        # regression = « a casse l'existant », ce qui est bien plus grave.
        "etages": etages,
        "issue": issue,
        # Preuve qu'un "0/44" de collecte n'est pas une page blanche : on compte ce
        # qui a ete ecrit. 197 lignes + IndentationError != 0 ligne.
        "lignes_ecrites": sum(
            len(p.read_text(errors="replace").splitlines())
            for p in sorted(workdir.rglob("*.py"))
            if p.name != "conftest.py"
            and "tests/" not in p.relative_to(workdir).as_posix()
        ),
        "pytest_tail": tail,
        # Observation, pas sanction : les tests que le modele s'est ecrits.
        "tests_ajoutes": ajoutes,
        "gardes_violees": violations,
        "api_modifiee": api_diff,
        "fichiers_modifies": modified,
    }


# --- adaptateurs de harnais ----------------------------------------------


def pi_command(model, workdir, prompt):
    """Retourne (argv, variables d'environnement a ajouter)."""
    return [
        "pi",
        "--model",
        model,
        "--mode",
        "json",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-context-files",
        "-p",
        prompt,
    ], {}


# Instruction testée le 2026-07-29. Motif : sur tetris, 2 des 3 appels `read` de
# qwopus3.5-9b-coder échouaient en ENOENT parce qu'il passait `tmp/...` au lieu de
# `/tmp/...` — le chemin, résolu depuis le cwd, se dédoublait. Le modèle connaît
# pourtant le chemin absolu, il l'utilise correctement dans `bash`. Il perdait ainsi
# 2 tours sur 9, puis contournait avec `cat`, ce qui remplaçait une lecture
# structurée par 5 Ko de sortie shell.
INSTRUCTION_CHEMINS_ABSOLUS = (
    "Pour les outils read, write et edit, utilise TOUJOURS un chemin ABSOLU "
    "commencant par une barre oblique. Un chemin relatif est resolu depuis le "
    "repertoire courant et echoue."
)


def pi_abspath_command(model, workdir, prompt):
    """pi + une instruction sur les chemins absolus. Variante d'A/B : tout le reste
    est identique à `pi`, seul ce ~30 tokens de préambule change.

    VERDICT 2026-07-29, 3 essais par côté : NON adopté, et l'hypothèse qui l'a
    motivé était fausse. Ce qui échouait n'était pas un chemin relatif — `pi` les
    résout correctement depuis son cwd (gemma-4-12b lit `tests/test_tetris.py` en
    relatif sans erreur). C'était un chemin absolu amputé de sa barre oblique de
    tête : qwopus émet `tmp/...` au lieu de `/tmp/...`, le chemin se dédouble et
    donne un ENOENT sur `<cwd>/tmp/<cwd sans slash>/...`. Un défaut d'émission sur
    un token, que cette instruction ne pouvait pas corriger.

    Effet mesuré nul et non concluant (médiane 20/44 contre 0/44, étendues 11-25 et
    0-25). Effet de bord réel : l'instruction nomme `edit`, et ça suffit à faire
    utiliser `edit` — jamais employé sans elle. Ses échecs (`No changes made […]
    replacement produced identical content`) sont une défaillance NOUVELLE, et le
    pic d'entrée médian passe de 15 850 à 28 754. Détail dans le README.
    """
    argv, env = pi_command(model, workdir, prompt)
    # Inséré avant `-p` pour ne pas casser l'ordre attendu par pi.
    i = argv.index("-p")
    return argv[:i] + ["--append-system-prompt", INSTRUCTION_CHEMINS_ABSOLUS] + argv[
        i:
    ], env


# Instruction testée le 2026-07-29. Motif : gemma-4-12b-coder est le modèle qui a le
# mieux compris le contrat tetris — son code, extrait du transcript et noté hors ligne,
# fait 17/44 sans qu'il ait jamais lancé un test, contre 20/44 à qwopus après 12 tours
# d'itération. Mais il ne l'écrit jamais sur le disque : il l'affiche dans son message
# et s'arrête (2 tours, un seul `read`). PROMPT-tetris.txt dit déjà « Lance pytest -q »
# et « Tu as termine quand pytest -q affiche 44 passed » ; il l'ignore. L'hypothèse est
# qu'il croit répondre à un humain qui lira le code. On ne nomme QUE write et bash :
# l'A/B des chemins absolus a montré que nommer un outil suffit à le faire employer.
INSTRUCTION_AGIR = (
    "Ta reponse texte n'est lue par personne : un script automatique constate "
    "seulement l'etat du disque. Le code affiche dans un message n'existe pas. "
    "Cree chaque fichier avec l'outil write, puis lance pytest -q avec bash. "
    "N'arrete pas ton tour avant d'avoir fait les deux."
)


def pi_act_command(model, workdir, prompt):
    """pi + une instruction qui dit que la sortie texte n'est pas lue. Variante d'A/B :
    tout le reste est identique à `pi`, seul ce ~55 tokens de préambule change.

    VERDICT 2026-07-29 : NON adopté. La référence à n=3 confirme le défaut (0/44 trois
    fois, `write` 0, `bash` 0, 9 `read`) ; le nudge ne le corrige pas et en crée un
    autre. Sur 2 essais mesurés : 0/44 en 1 tour, puis 0/44 en **267 tours** jusqu'au
    timeout de 900 s. La dernière phrase — « N'arrete pas ton tour avant d'avoir fait
    les deux » — retire la condition d'arrêt sans donner la capacité d'agir. Troisième
    essai interrompu : la médiane de [0, 0, x] vaut 0 quel que soit x.

    Même faute que INSTRUCTION_CHEMINS_ABSOLUS : une instruction ajoutée pour corriger un
    comportement en fabrique un pire. Garder les deux comme témoins de ce piège.

    Ce que gemma-4-12b-coder fait à la place, `stopReason: stop`, 0 appel d'outil :
    soit il annonce le plan et s'arrête (« I will first read […], then implement […],
    and finally run pytest -q »), soit il déverse 5 246 caractères de code dans son
    message. Détail et A/B de la grammaire LocalAI dans le README.
    """
    argv, env = pi_command(model, workdir, prompt)
    i = argv.index("-p")
    return argv[:i] + ["--append-system-prompt", INSTRUCTION_AGIR] + argv[i:], env


# Mesuré le 2026-09-09 sur lfm2.5-8b-a1b. Motif : le modèle rend 0 appel d'outil sur
# tetris (1 tour, `stopReason: stop`) alors qu'il en émet parfaitement dès qu'on
# l'interroge sans prompt système. A/B à un seul facteur, mêmes 4 outils, même prompt
# utilisateur, temp 0.2 :
#
#   A  prompt système de pi (2747 car.)          -> AUCUN appel, enveloppe JSON, 1564 tok
#   B  sans prompt système                       -> appel natif `read`,            453 tok
#   C  prompt de pi privé du bloc « Pi doc »     -> AUCUN appel,                  1282 tok
#   D  prompt minimal ci-dessous (139 car.)      -> appel natif `bash`,           1006 tok
#
# C écarte l'hypothèse du bruit documentaire. Sous le prompt de `pi`, le modèle se rabat
# sur un protocole d'agent qu'il s'est inventé — un objet JSON {analysis, plan, commands,
# edits} déposé dans `content`, que `pi` ne peut pas exécuter (son seul `repairJson`
# recolle des arguments malformés, pas un `content`). Les outils sont pourtant bien
# déclarés : 1588 tokens d'entrée au premier tour, comme les autres (1595 à 1795).
#
# MAIS l'A/B ci-dessus ne mesure que le PREMIER tour, et le harnais n'a rien débloqué :
# 3 essais tetris sous `pi-sysmin` donnent 0/44, 0 ligne écrite. L'essai 1 place deux
# appels réels (`ls -la`, puis `read`) et s'effondre au tour suivant ; les essais 2 et 3
# s'effondrent d'entrée. Les hypothèses suivantes ont été testées et REFUTEES :
#
#   « c'est la présence d'un résultat d'outil »  -> non : un résultat de 7 lignes passe
#   « c'est la TAILLE du résultat d'outil »      -> non : 400 car. s'effondre aussi
#   « c'est le prompt système »                  -> non : sans aucun message système, et
#                                                   avec un système vide, l'effondrement
#                                                   est identique (4096 tokens en JSON)
#
# Ce qui reste, mesuré : dès que le vrai contrat de 14 Ko est dans le contexte, ce modèle
# produit son enveloppe JSON quel que soit le prompt. L'enveloppe EST son format agentique
# entraîné ; elle est incompatible avec un harnais à `tool_calls`. `pi-sysmin` est donc
# conservé comme témoin de l'A/B du premier tour, pas comme correctif.
#
# ATTENTION à la comparaison : ce harnais n'est PAS `pi`. Un score obtenu ici ne se
# compare qu'à une référence rejouée dans le même harnais.
PROMPT_SYSTEME_MINIMAL = (
    "You are a coding agent. Use the provided tools to inspect and modify files. "
    "Perform actions with tool calls; do not describe them in prose."
)


def pi_sysmin_command(model, workdir, prompt):
    """pi avec un prompt système minimal à la place du sien. Variante d'A/B : tout le
    reste est identique à `pi`, seul le contenu du message système change.

    À la différence de `pi-act`, qui AJOUTE une consigne (`--append-system-prompt`),
    celui-ci REMPLACE le prompt par défaut (`--system-prompt`). C'est ce que l'A/B
    ci-dessus désigne : le défaut n'est pas une consigne manquante, c'est le prompt
    de `pi` lui-même qui déclenche le mauvais format.
    """
    argv, env = pi_command(model, workdir, prompt)
    i = argv.index("-p")
    return argv[:i] + ["--system-prompt", PROMPT_SYSTEME_MINIMAL] + argv[i:], env


def pi_verif_command(model, workdir, prompt):
    """`pi` avec ses EXTENSIONS chargées — tout le reste identique à `pi`.

    Motif, et c'est une erreur qui a produit de fausses conclusions le 2026-09-11 :
    `pi_command` passe `--no-extensions`. L'extension `verifier.ts` (boucle de
    vérification) était donc DÉSACTIVÉE dans toutes les campagnes lancées avec
    `PI_VERIFY_CMD`, et les relevés attribués à son effet n'en portaient aucune
    trace — zéro relance injectée dans les sept transcripts vérifiés après coup.

    Seul `--no-extensions` est retiré. `--no-skills` et `--no-context-files` restent,
    pour que l'écart avec `pi` tienne au chargement des extensions et à rien d'autre.

    ⚠️ Charge TOUTES les extensions installées, pas seulement celle qu'on mesure.
    Pour un A/B à un seul facteur, vérifier `pi list` et retirer temporairement ce
    qui n'est pas sous test.
    """
    argv, env = pi_command(model, workdir, prompt)
    return [a for a in argv if a != "--no-extensions"], env


def pi_metrics(transcript):
    """Extrait tours, appels d'outils, format et tokens du JSONL de pi."""
    turns = 0
    calls = []
    peak_input = 0
    total_in = total_out = 0
    xml_leak = False
    lignes_illisibles = 0
    erreur_modele = None
    for line in transcript.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        except RecursionError:
            # Une ligne trop IMBRIQUÉE pour le décodeur. Vu le 2026-09-11 : la
            # campagne entière est morte en plein essai 2 sur un
            # « maximum recursion depth exceeded », et comme le transcript n'est
            # écrit qu'APRÈS le parsing, la preuve a disparu avec elle. Une ligne
            # illisible se saute et se compte ; elle ne fait pas tomber le reste.
            lignes_illisibles += 1
            continue
        # Un modele qui n'a pas CHARGE n'est pas un modele qui a echoue. Vu le
        # 2026-09-12 sur agents-a1-4b-q8_0 : « cudaMalloc failed: out of memory »
        # parce que LocalAI n'avait pas rendu la VRAM du modele precedent, et le banc
        # a compte l'essai comme un 0/44. Un tel essai doit sortir de la mesure, pas
        # la plomber.
        if event.get("type") == "message_end":
            msg = event.get("message") or {}
            if msg.get("stopReason") == "error" and msg.get("errorMessage"):
                erreur_modele = str(msg["errorMessage"])[:300]
        if event.get("type") == "turn_end":
            turns += 1
            usage = event["message"].get("usage") or {}
            peak_input = max(peak_input, usage.get("input") or 0)
            total_in += usage.get("input") or 0
            total_out += usage.get("output") or 0
        if event.get("type") == "message_end":
            content = event.get("message", {}).get("content") or []
            # `content` peut etre une chaine, ou une liste melangeant chaines et
            # blocs typés selon le harnais. little-coder produit la forme mixte,
            # pi non.
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for block in content:
                if isinstance(block, str):
                    block = {"type": "text", "text": block}
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "toolCall":
                    calls.append(block.get("name"))
                # Un appel d'outil rendu en XML dans du texte = bascule du modele.
                if block.get("type") == "text" and re.search(
                    r"<function=|<parameter=", block.get("text") or ""
                ):
                    xml_leak = True
    return {
        "tours": turns,
        "appels_outils": len(calls),
        "outils_utilises": sorted(set(c for c in calls if c)),
        "format_appels": "xml" if xml_leak else ("json" if calls else "aucun"),
        "pic_input": peak_input,
        "total_input": total_in,
        "total_output": total_out,
        # Sauter une ligne en silence rendrait un relevé faux indistinguable d'un bon.
        "lignes_illisibles": lignes_illisibles,
        "erreur_modele": erreur_modele,
    }


def little_coder_command(model, workdir, prompt):
    """little-coder = pi + ~30 extensions + ~30 skills, pi etant une simple
    dependance npm. Meme CLI, meme format JSONL, donc `pi_metrics` s'applique.

    On NE passe PAS --no-extensions ni --no-skills : ce sont precisement les
    couches que little-coder ajoute, et les desactiver le reduirait a pi. Seul
    --no-context-files est conserve, comme pour pi, pour ne pas faire dependre le
    resultat d'un AGENTS.md du dossier.
    """
    # little-coder ajoute une extension permission-gate : en mode `auto`, bash est
    # restreint a une liste blanche de prefixes (SAFE_PREFIXES) qui NE CONTIENT PAS
    # `pytest`. Le premier appel du modele est donc rejete par
    #   shell whitelist: "pytest" is not in SAFE_PREFIXES
    # et l'agent perd la boucle de retroaction par les tests — precisement le
    # mecanisme qui fait reussir bonsai. pi n'a aucune liste blanche, donc on leve
    # celle-ci pour comparer a armes egales. C'est l'echappatoire documentee du
    # projet, et c'est un CHOIX DE BANC, pas un defaut de little-coder : sa posture
    # par defaut est plus prudente que celle de pi.
    #
    # 2026-09-16, v1.19.0 : little-coder n'enregistre ses modeles QUE depuis son
    # propre `models.json` (paquet + override `~/.config/little-coder/models.json`),
    # jamais depuis `~/.pi/agent/models.json`. Le fournisseur `localai` est donc
    # declare dans l'override, avec `apiKey: "LOCALAI_API_KEY"` -- un NOM de
    # variable, que le banc doit fournir. Sans elle : « No API key » et un essai
    # qui mesure la plomberie.
    #
    # Sa temperature de profil (0.3) n'est injectee que pour llamacpp/ollama/
    # lmstudio (DEFAULT_TEMPERATURE_PROVIDERS) : `localai` n'en fait pas partie,
    # donc l'echantillonnage reste celui du serveur, comme pour tous les autres
    # harnais du banc. C'est voulu : un seul facteur change a la fois.
    #
    # Et cette variable n'est PAS resolue : `resolveApiKey` ne sert qu'a la sonde
    # `/props` de l'extension, `pi.registerProvider` recoit la chaine brute et
    # l'envoie comme Bearer -> 401 (verifie le 2026-09-16 ; avec la valeur
    # litterale, l'essai passe). Le banc genere donc, a chaque lancement, un
    # fichier de modeles temporaire avec la VALEUR, a partir du gabarit versionne
    # `config-little-coder/models.json` qui ne contient que le NOM. Le fichier
    # vit hors du workdir (qui est archive) et en 0600 -- meme exposition que
    # `~/.pi/agent/models.json`, qui porte deja la cle en clair.
    env = {"LITTLE_CODER_PERMISSION_MODE": "accept-all"}
    gabarit = HERE / "config-little-coder" / "models.json"
    cle = Path.home() / ".config" / "brain" / "localai-key"
    if gabarit.exists() and cle.exists():
        modeles = json.loads(gabarit.read_text())
        for conf in modeles.get("providers", {}).values():
            if conf.get("apiKey") == "LOCALAI_API_KEY":
                conf["apiKey"] = cle.read_text().strip()
        fichier = Path(tempfile.gettempdir()) / "harness-bench-little-coder-models.json"
        fichier.touch(mode=0o600, exist_ok=True)
        fichier.chmod(0o600)
        fichier.write_text(json.dumps(modeles))
        env["LITTLE_CODER_MODELS_FILE"] = str(fichier)
    argv = [
        "little-coder",
        # Sans lui, le lanceur interroge le registre npm a CHAQUE essai (et
        # proposerait une mise a jour a mi-campagne). Le harnais mesure est
        # celui installe, pas celui du jour.
        "--no-update-check",
        "--model",
        model,
        "--mode",
        "json",
        "--no-session",
        "--no-context-files",
    ]
    if EXCLURE_OUTILS:
        argv += ["--exclude-tools", EXCLURE_OUTILS]
    return argv + ["-p", prompt], env


PI_LENS = Path.home() / ".pi" / "agent" / "npm" / "node_modules" / "pi-lens" / "dist" / "index.js"

# Liste noire d'outils, posee par --exclude-tools. Vide = aucun retrait, donc
# inerte par defaut.
#
# Motif (2026-09-16, essai 3 de little-coder+pi-lens) : `dispatch` lance des
# sous-codeurs, qui ont mange 12 min sur 28 et ouvert un SECOND flux concurrent
# sur le GPU -- suspecte dans l'OOM LocalAI du matin. `flutter build` n'a jamais
# ete lance avant le couperet. C'est un REGLAGE du harnais, pas une
# transformation : la famille pi expose `--exclude-tools` nativement.
#
# Constante de module et pas parametre de `build_command` : la signature
# (model, workdir, prompt) est partagee par la vingtaine de lanceurs, et la
# changer pour un reglage qui n'en concerne qu'une famille couterait plus qu'il
# ne rapporte. La valeur reste tracee : `commande` enregistre sys.argv.
EXCLURE_OUTILS = ""


def little_coder_lens_command(model, workdir, prompt):
    """little-coder + pi-lens, et RIEN d'autre : un seul facteur change.

    Motif (2026-09-16). Sur crepuscule-amorce, six configurations et trois
    harnais echouent sur le MEME mur : un chemin d'import devine dans
    `flutter_scene`, et un modele qui ne lit pas le message du compilateur quand
    il est noye dans 3 900 caracteres de gradle. Le seul run qui a passe ce mur
    (opencode + lsp) avait le diagnostic ISOLE et COLLE au resultat de
    l'ecriture. little-coder n'a pas de diagnostics ; pi-lens les injecte en fin
    de tour (dart-analyze / dartls). C'est le levier qu'on n'a jamais mesure seul.

    Chargement par `LITTLE_CODER_EXTRA_EXTENSIONS` (chemin de fichier) : le
    lanceur garde son `--no-extensions`, donc le reste de `~/.pi/agent`
    (context7, blackhole, verifier...) ne charge PAS. `--with-pi-extensions`
    aurait tout charge d'un coup et melange les facteurs.
    """
    argv, env = little_coder_command(model, workdir, prompt)
    env["LITTLE_CODER_EXTRA_EXTENSIONS"] = str(PI_LENS)
    return argv, env


def aider_command(model, workdir, prompt):
    """aider n'expose aucun schema d'outil : il edite par diff textuel.

    Le prompt et la verification sont identiques a pi ; seule l'invocation change.
    Trois specificites :
      - aider passe par litellm, donc un endpoint OpenAI-compatible se declare via
        le prefixe `openai/` plus OPENAI_API_BASE / OPENAI_API_KEY ;
      - il ne connait pas la fenetre de nos modeles locaux : sans
        `.aider.model.metadata.json` il applique un defaut et le banc mesurerait une
        troncature au lieu du harnais. On ecrit donc 32768, comme le contextWindow
        donne a pi ;
      - `--map-tokens 0` coupe le repo-map (1024 tokens par defaut), pour comparer
        des preambules et non des strategies de contexte.
    """
    model_id = model.split("/", 1)[-1]
    litellm_name = "openai/" + model_id
    (workdir / ".aider.model.metadata.json").write_text(
        json.dumps(
            {
                litellm_name: {
                    "max_input_tokens": 32768,
                    "max_output_tokens": 4096,
                    "input_cost_per_token": 0,
                    "output_cost_per_token": 0,
                    "litellm_provider": "openai",
                    "mode": "chat",
                }
            },
            indent=2,
        )
        + "\n"
    )
    key_file = Path.home() / ".config" / "brain" / "localai-key"
    env = {
        "OPENAI_API_BASE": "https://localai.tgu.ovh/v1",
        "OPENAI_API_KEY": key_file.read_text().strip(),
        "AIDER_ANALYTICS": "false",
    }
    argv = [
        "aider",
        "--model",
        litellm_name,
        "--yes-always",
        "--no-auto-commits",
        "--no-git",
        "--no-check-update",
        "--no-show-model-warnings",
        "--no-auto-lint",
        "--map-tokens",
        "0",
        # Boucle agentique d'aider : il relance les tests apres chaque edition et
        # itere sur les echecs. Sans ca, `--message` est un echange unique.
        "--auto-test",
        "--test-cmd",
        PYTEST + " -q",
    ]
    # aider n'explore pas : il edite ce qu'on met dans le chat. Les 5 modules sont
    # donc passes en editables et la suite de tests en lecture seule.
    #
    # ATTENTION, ceci n'est PAS la meme difficulte que pour pi : pi a du DECOUVRIR
    # les fichiers lui-meme (bash, read). Ici la localisation est offerte. C'est
    # l'usage idiomatique d'aider, pas une triche, mais les deux colonnes ne sont
    # pas comparables sur le nombre de tours.
    for path in sorted((workdir / "taskmgr").glob("*.py")):
        argv += ["--file", "taskmgr/" + path.name]
    argv += ["--read", "tests/test_taskmgr.py"]
    argv += ["--message", prompt]
    return argv, env


def aider_metrics(transcript):
    """aider imprime 'Tokens: 12k sent, 456 received.' par echange."""
    sent = re.findall(r"Tokens:\s*([\d.]+)\s*([km]?)\s*sent", transcript, re.I)
    received = re.findall(r"([\d.]+)\s*([km]?)\s*received", transcript, re.I)

    def scale(value, unit):
        factor = {"k": 1000, "m": 1000000}.get(unit.lower(), 1)
        return int(float(value) * factor)

    sent_values = [scale(v, u) for v, u in sent]
    received_values = [scale(v, u) for v, u in received]
    return {
        "tours": len(sent_values) or None,
        "appels_outils": None,  # aider edite par diff, il n'y a pas d'appel d'outil
        "format_appels": "diff (aucun schema d'outil)",
        "pic_input": max(sent_values) if sent_values else None,
        "total_input": sum(sent_values) or None,
        "total_output": sum(received_values) or None,
    }


HARNAIS_NU = Path("/data/projets/perso/harnais-nu")


def nu_command(model, workdir, prompt):
    """Harnais témoin à préambule ZÉRO (repo harnais-nu) : aucun message system,
    seulement les schémas de ses 4 outils. Plancher du banc — les autres harnais
    se lisent en écart par rapport à lui.

    Le serveur est un llama-server local (podman, cf. harnais-nu/serveur.md), PAS
    LocalAI : `model` ne sert qu'à remplir le champ de la requête. Base URL
    surchargée par HARNAIS_NU_BASE_URL. Les budgets du harnais sont en tours et
    en tokens ; le --timeout du banc reste un garde-fou externe, pas la limite
    de comparaison.

    Les trois budgets sont surchargeables par l'environnement pour balayer sans
    toucher au code — indispensable depuis la mesure du 2026-07-29 : à 4096 tokens
    par tour, gemma-4-12b dépense TOUT son plafond dans son canal de pensée et
    n'atteint jamais l'action (3/3 essais à 0/44, 2 tours, 0 ligne écrite).

        HARNAIS_NU_MAX_TURNS, HARNAIS_NU_MAX_TOKENS_PER_TURN, HARNAIS_NU_MAX_TOTAL_TOKENS
    """
    base_url = os.environ.get("HARNAIS_NU_BASE_URL", "http://127.0.0.1:8080/v1")
    # P2 : la porte de vérification. Absente par défaut → le harnais reste le
    # témoin nu. HARNAIS_NU_VERIFY_CMD l'active sans toucher au code, pour mesurer
    # la règle contre le plancher du témoin.
    verify = []
    # HARNAIS_NU_LINT_CMD sur le TEMOIN aussi, pas seulement sur le pipeline.
    # Motif (2026-09-16) : `lint.py` porte le seul levier jamais mesure gagnant
    # -- opencode + `lsp: true` fait 3/3 la ou le MEME modele fait 0/6 sans --
    # et il etait injoignable depuis le bras nu. Forme par langage acceptee :
    #   HARNAIS_NU_LINT_CMD=".py=ruff check {},.dart=dart analyze {}"
    if os.environ.get("HARNAIS_NU_LINT_CMD"):
        verify += ["--lint-cmd", os.environ["HARNAIS_NU_LINT_CMD"]]
    # HARNAIS_NU_LSP=1 : diagnostics de serveur de langage POUSSES apres chaque
    # ecriture (harnais-nu/lsp.py). C'est le mecanisme exact d'opencode
    # `lsp: true`, mesure 3/3 la ou le meme modele fait 0/6 sans. Inerte la ou
    # aucun serveur n'est installe (auto-detection par suffixe).
    # 2026-09-17 : harnais-nu OFFRE ces outils PAR DEFAUT (les drapeaux
    # `--sans-*` coupent). Le temoin du banc doit rester le TEMOIN — sinon
    # toutes les campagnes anterieures deviendraient incomparables en silence,
    # sans que rien ne le signale (piege 21). On epingle donc les coupures ici,
    # et chaque variable d'environnement LEVE la sienne.
    if not os.environ.get("HARNAIS_NU_CONSIGNE_OUTILS"):
        verify += ["--sans-consigne-outils"]
    if not os.environ.get("HARNAIS_NU_LSP"):
        verify += ["--sans-lsp"]
    # HARNAIS_NU_CONSIGNE_DIAGNOSTICS : la phrase qui dit QUOI FAIRE du bloc,
    # separee des capteurs qui le produisent (`lsp.py` ET `lint.py` : meme point
    # d'injection, et en Python seul `lint` parle, faute de serveur installe). Par defaut coupee, pour que `HARNAIS_NU_LSP=1` seul
    # mesure le CAPTEUR et rien d'autre. La mesure du 2026-09-17 (temoin 1/6,
    # bras arme 6/6) empilait les deux et ne disait donc pas la part de chacun.
    if not os.environ.get("HARNAIS_NU_CONSIGNE_DIAGNOSTICS"):
        verify += ["--sans-consigne-diagnostics"]
    if os.environ.get("HARNAIS_NU_VERIFY_CMD"):
        verify += [
            "--verify-cmd",
            os.environ["HARNAIS_NU_VERIFY_CMD"],
            "--max-verify",
            os.environ.get("HARNAIS_NU_MAX_VERIFY", "3"),
        ]
    # Robustesse à la troncature, inerte par défaut (0) pour que le plancher du
    # témoin reste reproductible. 2 essais sur 6 sont morts d'un tool_call coupé.
    # Leviers d'hygiene de contexte, inertes par defaut. UN levier par campagne :
    # en activer plusieurs empeche d'attribuer l'effet (harnais-nu/MESURES.md).
    if os.environ.get("HARNAIS_NU_HYGIENE"):
        verify += ["--hygiene", os.environ["HARNAIS_NU_HYGIENE"]]
    if os.environ.get("HARNAIS_NU_MAX_RETRY_TRONCATURE"):
        verify += [
            "--max-retry-troncature",
            os.environ["HARNAIS_NU_MAX_RETRY_TRONCATURE"],
        ]
    # Edition structurelle (ast-grep) : un outil de plus dans le preambule, donc un
    # changement du temoin — a mesurer comme un levier, une variable a la fois.
    if not os.environ.get("HARNAIS_NU_STRUCTURE"):
        verify += ["--sans-structure"]
    # Porter le resultat des tests DANS le write/edit, au lieu d un `bash pytest`
    # separe. Levier sur le NOMBRE de tours : 48 des 61 `bash` mesures sur columns
    # etaient des pytest suivant une ecriture, et 100 % des tours ne portent qu un
    # seul appel d outil.
    if os.environ.get("HARNAIS_NU_TESTS_APRES_ECRITURE"):
        verify += ["--tests-apres-ecriture"]
        # Trois variants a departager (cf. MESURES.md) : `complet` fait -3 bash
        # mais +60 % de pic, `bilan` laisse le pic intact sans gain de tours,
        # `echecs` parie que les NOMS suffisent.
        if os.environ.get("HARNAIS_NU_TESTS_DETAIL"):
            verify += ["--tests-detail", os.environ["HARNAIS_NU_TESTS_DETAIL"]]
    # Compaction (harnais-nu/compaction.py), inerte sans --fenetre. Declarer une
    # fenetre PLUS PETITE que celle du serveur force le declenchement tot : c'est
    # ainsi qu'on teste la mecanique sur `repair` (93 s) au lieu d'attendre le mur.
    if os.environ.get("HARNAIS_NU_FENETRE"):
        verify += ["--fenetre", os.environ["HARNAIS_NU_FENETRE"]]
        if os.environ.get("HARNAIS_NU_SEUIL_COMPACTION"):
            verify += [
                "--seuil-compaction",
                os.environ["HARNAIS_NU_SEUIL_COMPACTION"],
            ]
    # Budget du CANAL DE PENSEE, envoye par requete. Sur `columns-web` un tour a
    # brule 26 161 caracteres de `reasoning_content` sans un seul tool_call, et
    # doubler le plafond par tour (4096 -> 8192) n'a fait que doubler le monologue :
    # ce n'est pas le meme levier, il faut borner la PENSEE et pas la reponse.
    # Deduplication des relectures RIGOUREUSEMENT identiques, mutee en place.
    # Cible revisee : elle ne sauve plus un run (le plafond desserre a fait
    # disparaitre les aneantissements), elle freine le VOLUME — un tirage du bras
    # gagnant a produit 41 705 tokens de sortie pour 8 tours.
    # Graphe de code : index bati par le HARNAIS (demarrage + apres chaque ecriture),
    # jamais par le modele. Ne lui expose que deux outils, pas les 14 de CBM.
    # grep/glob : hors du temoin a dessein (deux schemas de plus coutent a CHAQUE
    # requete), donc exposes par variable. Absents de bench.py jusqu'au 2026-08-05 —
    # les bras exploratoires de l'apres-midi les invoquaient via boucle.py en direct,
    # ce qui les rendait inmesurables par le banc.
    # PORTE DE FALSIFIABILITE : refuse l'arret tant qu'aucun test n'a ete AJOUTE.
    # Specifiee dans harnais-nu/pipelines/contrat.py, jamais faite avant le
    # 2026-08-06. Vise le goulot MESURE : sur pronote le modele resout 2 fois sur 5,
    # donc trois essais donneraient 78 % — mais il faut un selecteur, et la suite
    # visible passe deja au commit de depart.
    if os.environ.get("HARNAIS_NU_PORTE_TESTS"):
        verify += ["--porte-tests"]
        if os.environ.get("HARNAIS_NU_COLLECTE_CMD"):
            verify += ["--collecte-cmd", os.environ["HARNAIS_NU_COLLECTE_CMD"]]
    if not os.environ.get("HARNAIS_NU_RECHERCHE"):
        verify += ["--sans-recherche"]
    if not os.environ.get("HARNAIS_NU_GRAPHE"):
        verify += ["--sans-graphe"]
    if os.environ.get("HARNAIS_NU_DEDUPE_RELECTURES"):
        verify += ["--dedupe-relectures"]
    # ECHANTILLONNAGE. Jusqu'au 2026-08-05 le harnais n'en envoyait AUCUN et le serveur
    # appliquait ses defauts : temp 1.0, min_p 0.05. Or la doc Qwen3.6 distingue deux
    # regimes en mode pensee — temp 1.0 pour les taches GENERALES, temp 0.6 pour le
    # CODE PRECIS — et ce banc ne fait que du code precis. Toutes les campagnes
    # anterieures ont donc tourne au mauvais regime, ce qui est le premier suspect pour
    # la variance qui a rendu chaque verdict penible (ecart 29, tours de 9 a 45 sur
    # reglage identique). Chaque variable absente = champ non envoye, donc temoin
    # inchange et historique toujours comparable.
    for var, drapeau in (
        ("HARNAIS_NU_SEED", "--seed"),
        ("HARNAIS_NU_MESSAGE_RAISONNEMENT", "--message-raisonnement"),
        # Restreint le jeu d'outils du temoin. `bash` seul reproduit la forme de
        # mini-SWE-agent (>74 % sur SWE-bench verified, ~100 lignes, un seul outil).
        # Le banc l'avait suggere sans qu'on le voie : deux tirages a 109/109 avec
        # `write: 0`, le modele ecrivant par heredoc shell.
        ("HARNAIS_NU_OUTILS", "--outils"),
        ("HARNAIS_NU_TEMPERATURE", "--temperature"),
        ("HARNAIS_NU_MIN_P", "--min-p"),
        ("HARNAIS_NU_TOP_P", "--top-p"),
        ("HARNAIS_NU_TOP_K", "--top-k"),
        ("HARNAIS_NU_PRESENCE_PENALTY", "--presence-penalty"),
        # Renomme la SURFACE des outils (Read/Write/Edit/Bash + file_path,
        # old_string, new_string). Mesure du 2026-08-06 : KAT-Coder n'a emis AUCUN
        # write ni edit sur les 8 tirages `pronote` (165 tours en `bash`), alors
        # qu'il en emet sur `columns-web` ou la tache est de CREER des fichiers.
        # a3b, meme scenario, appelle `edit` 3 fois par tirage.
        ("HARNAIS_NU_CONVENTION_OUTILS", "--convention-outils"),
        # A remonter pour tout scenario qui COMPILE : `flutter build apk` prend 73 s
        # au mieux, or le defaut de `bash` est 60 s. Sans ca, le harnais tuerait
        # chaque tentative et le banc mesurerait sa propre limite.
        ("HARNAIS_NU_DELAI_BASH", "--delai-bash"),
    ):
        if os.environ.get(var):
            verify += [drapeau, os.environ[var]]
    # Drapeau BOOLEEN, donc hors de la boucle ci-dessus qui passe des valeurs.
    # Supprime le canal de pensee a la source (chat_template_kwargs), la ou
    # --budget-raisonnement se contente de le borner. Mesure du 2026-08-06 sur
    # KAT-Coder : meme appel d'outil atteint en 27 tokens generes contre 65.
    # Le venv DU SUJET, derive du pytest declare par le scenario. Regle posee le
    # 2026-08-06 : le harnais s'execute avec son venv, le sujet avec le sien.
    #
    # Sans ce passage, `uv run --project harnais-nu` exportait VIRTUAL_ENV et PATH
    # vers le venv DU HARNAIS : l'agent voyait un python sans `homeassistant`, en
    # deduisait qu'il devait simuler les imports, et brulait 53 a 121 appels `bash`
    # a fabriquer des `MockHA`. Les 8 tirages `pronote` de KAT ne mesuraient donc
    # pas le modele mais cette fuite -- et ses `pip install` ont pollue le venv du
    # harnais de 11 paquets non declares, cassant ses 394 tests.
    #
    # Derive plutot que declare en double : un second champ divergerait du premier.
    scen = SCENARIOS.get(SCENARIO_COURANT) or {}
    # Chaine d'outils du sujet : declaree explicitement (`venv`, cas d'un SDK non
    # Python) ou DERIVEE du `pytest` du scenario. Derivee plutot que dupliquee : un
    # second champ finirait par diverger du premier.
    pytest_sujet = scen.get("pytest")
    venv = scen.get("venv") or (
        os.path.dirname(os.path.dirname(pytest_sujet)) if pytest_sujet else None
    )
    if venv and os.path.isdir(os.path.join(venv, "bin")):
        verify += ["--venv", venv]
    if os.environ.get("HARNAIS_NU_SANS_PENSEE"):
        verify += ["--sans-pensee"]
    if os.environ.get("HARNAIS_NU_BUDGET_RAISONNEMENT"):
        verify += [
            "--budget-raisonnement",
            os.environ["HARNAIS_NU_BUDGET_RAISONNEMENT"],
        ]
    return [
        "uv",
        "run",
        "--project",
        str(HARNAIS_NU),
        str(HARNAIS_NU / "boucle.py"),
        "--task",
        prompt,
        "--workdir",
        str(workdir),
        "--base-url",
        base_url,
        "--model",
        model.split("/", 1)[-1],
        "--max-turns",
        os.environ.get("HARNAIS_NU_MAX_TURNS", "30"),
        "--max-tokens-per-turn",
        os.environ.get("HARNAIS_NU_MAX_TOKENS_PER_TURN", "4096"),
        "--max-total-tokens",
        os.environ.get("HARNAIS_NU_MAX_TOTAL_TOKENS", "100000"),
    ] + verify, {}


def nu_metrics(transcript):
    """boucle.py imprime ses métriques en une ligne JSON sur stdout, et RIEN d'autre.

    Position dans le transcript : en tête, pas en queue — `run_once` concatene
    stdout PUIS stderr, et tout le journal de la boucle est sur stderr. Le
    balayage à l'envers traverse donc les lignes de log (aucune ne commence par
    `{`) avant d'atteindre la ligne de métriques.

    `appels_outils` est ici un dict {outil: compte} là où pi/little-coder rendent
    un entier : ne pas agréger cette clé entre harnais sans normaliser.
    """
    for line in reversed(transcript.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and '"turns"' in line):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {
            "tours": m.get("turns"),
            "appels_outils": m.get("tool_calls"),
            "format_appels": m.get("call_format"),
            "pic_input": m.get("peak_input_tokens"),
            "total_input": m.get("total_input_tokens"),
            "total_output": m.get("output_tokens_total"),
            "stop_reason": m.get("stop_reason"),
            # `stop_reason: error` + ce message = panne HTTP (contexte dépassé, 500,
            # backend évincé), PAS une contre-performance du modèle. Sans les lire on
            # noterait une panne d'instrument comme un score.
            "erreur": m.get("erreur"),
            # P2 : nombre de confrontations à la commande de vérification, et son
            # verdict. `verifications` est le prédicteur du score identifié dans
            # harnais-nu/MESURES.md — sans lui, la règle n'est pas mesurable.
            "verifications": m.get("verifications"),
            "verif_ok": m.get("verif_ok"),
            # Les DEUX compteurs de troncature, pas seulement les reprises. Omettre
            # `tours_tronques` a rendu l'inventaire du 2026-08-06 muet sur 290
            # tirages : il lisait « 0 tour tronqué » là où le champ était absent.
            # `tours_tronques` = coupé par `max_tokens` ; `retries_troncature` = les
            # reprises effectivement lancées. L'écart entre les deux est le levier.
            "tours_tronques": m.get("tours_tronques"),
            "retries_troncature": m.get("retries_troncature"),
            "hygiene": m.get("hygiene"),
            "caracteres_economises": m.get("caracteres_economises"),
            "writes_rattrapes": m.get("writes_rattrapes"),
            # `modes_compaction` distingue un resume reussi d'un repli mecanique :
            # sans lui, une campagne ou le modele echoue a resumer se lirait comme
            # une campagne de compaction par resume.
            "compactions": m.get("compactions"),
            "modes_compaction": m.get("modes_compaction"),
            # Deduplication : le COMPTE de relectures elaguees separe « le levier n a
            # pas mordu » de « il n y avait aucun doublon ». Sans lui, un bras sans
            # gain serait illisible — c est l erreur faite sur compactions=0.
            "dedups": m.get("dedups"),
            "dedup_economises": m.get("dedup_economises"),
            # `tests_auto` doit rester COMPARABLE au nombre de `bash pytest` qu il
            # remplace : s il le depasse largement, le levier gagne des tours et
            # paie du temps sur un paquet incomplet (risque predit, cf. MESURES.md).
            "tests_auto": m.get("tests_auto"),
            "tests_auto_ok": m.get("tests_auto_ok"),
        }
    return no_metrics(transcript)


# Artefacts de build a NE PAS archiver : 1,2 Go contre 2,6 Mo de source sur le
# tirage du 2026-08-07. Les exclure change l'archive d'inutilisable a triviale.
EXCLUS_PROJET = (
    "build",
    ".dart_tool",
    ".pub-cache-agent",
    ".paquets-agent",
    "__pycache__",
    ".git",
    "node_modules",
)


def archive_projet(workdir, etiquette):
    """Met le CODE PRODUIT a l'abri, hors de /tmp. Ne leve jamais.

    Motif (2026-08-07) : sur `crepuscule-amorce` le code EST le livrable -- un tirage
    a 3/3 produit une amorce de projet qui vaut d'etre gardee, voire promue dans le
    depot du jeu. Or le workdir est detruit par `shutil.rmtree` au prochain tirage de
    meme nom, et rien n'archivait le code : ni `results/` (metriques et log), ni
    `trajectoires/` (messages et raisonnement), ni la capture.

    La trajectoire contient bien les arguments des `write`, donc une PARTIE du code,
    mais pas ce que `flutter create` a genere -- reconstituer un projet depuis des
    appels d'outils est illusoire.
    """
    if not workdir:
        return
    source = Path(workdir)
    if not source.is_dir():
        return
    try:
        PROJETS.mkdir(exist_ok=True)
        with tarfile.open(PROJETS / ("%s.tgz" % etiquette), "w:gz") as archive:
            archive.add(
                source,
                arcname=etiquette,
                filter=lambda info: (
                    None
                    if any(part in EXCLUS_PROJET for part in Path(info.name).parts)
                    else info
                ),
            )
    except (OSError, tarfile.TarError):
        return


def archive_trajectoire(workdir, etiquette):
    """Met le transcript de l'essai a l'abri, hors de /tmp.

    Ne leve JAMAIS : perdre une trace est sans gravite, perdre la campagne qui la
    produisait ne l'est pas. Meme discipline que le journal par tour.

    Seuls `nu` et `nu-contrat` ecrivent ce fichier ; les autres harnais (pi,
    aider) produisent des logs texte, inexploitables comme paires — on sort donc
    en silence plutot que de signaler une absence normale.

    ⚠️ L'etiquette porte le nom du SCENARIO : c'est ce qui permettra d'exclure
    `columns` du jeu d'entrainement. 62 % des traces en viennent, et c'est aussi
    l'instrument de mesure — s'entrainer dessus puis y mesurer ne mesurerait rien.
    """
    if not workdir:
        return
    source = Path(workdir) / ".harnais-nu-transcript.json"
    try:
        if not source.is_file():
            return
        TRAJECTOIRES.mkdir(exist_ok=True)
        shutil.copy2(source, TRAJECTOIRES / ("%s.json" % etiquette))
    except OSError:
        pass


def _nu_pipeline_command(model, workdir, prompt, graphe):
    """Pipeline à phases isolées (harnais-nu, sous-projet 1).

    Même serveur, même modèle et mêmes budgets que `nu` : la seule variable est
    le GRAPHE. C'est ce qui rend la comparaison au plancher (médiane 44/44, pic
    médian 34 515) interprétable.

    `graphe` est passé par le HARNAIS et non par variable d'environnement : le
    slug d'un essai vient du nom du harnais (`slug_de`), donc deux graphes sous
    un même nom se recouvriraient dans `results/` et rien dans les fichiers ne
    dirait lequel a produit quoi.
    """
    base_url = os.environ.get("HARNAIS_NU_BASE_URL", "http://127.0.0.1:8080/v1")
    commande = [
        "uv",
        "run",
        "--project",
        str(HARNAIS_NU),
        str(HARNAIS_NU / "pipeline.py"),
        "--task",
        prompt,
        "--workdir",
        str(workdir),
        "--base-url",
        base_url,
        "--model",
        model.split("/", 1)[-1],
        "--pipeline",
        graphe,
        "--verify-cmd",
        os.environ.get("HARNAIS_NU_VERIFY_CMD", PYTEST + " -q"),
        "--max-cycles",
        os.environ.get("HARNAIS_NU_MAX_CYCLES", "10"),
        # Le seul plafond qui morde sur `contrat` : son graphe ne repasse jamais
        # par sa phase de départ, donc --max-cycles y est inerte.
        "--max-etapes",
        os.environ.get("HARNAIS_NU_MAX_ETAPES", "24"),
    ]
    if graphe == "contrat":
        # Défaut VIDE, donc phase lint absente du graphe : le linter du harnais
        # n'est pas celui de la fixture mesurée, et l'ajouter changerait deux
        # variables au lieu d'une.
        commande += ["--lint-cmd", os.environ.get("HARNAIS_NU_LINT_CMD", "")]
    return commande, {}


def nu_pipeline_command(model, workdir, prompt):
    return _nu_pipeline_command(model, workdir, prompt, "neuf")


def nu_contrat_command(model, workdir, prompt):
    """Graphe `contrat` : comprendre → porte → implementer → (lint) → verifier.

    Une phase Agent de plus que le plancher, censée absorber l'exploration (les
    sorties d'outils font 35,8 % du contexte mesuré) et ne transmettre que ses
    notes. C'est cette hypothèse-là que l'essai tranche.
    """
    return _nu_pipeline_command(model, workdir, prompt, "contrat")


def nu_pipeline_metrics(transcript):
    """Le pipeline imprime son bilan en une ligne JSON sur stdout.

    On discrimine sur `"cycles"` et non sur `"turns"` : les deux harnais nu
    impriment `turns`, mais seul le pipeline compte des cycles et des étapes.

    `contradictions` compte les fois où le modèle a annoncé un succès démenti par
    l'oracle — l'auto-déclaration est le signal le moins fiable mesuré (cf.
    harnais-nu/MESURES.md), et cette clé le chiffre au lieu de le supposer.
    """
    for line in reversed(transcript.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and '"cycles"' in line):
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {
            "tours": m.get("turns"),
            # Les appels d'outils sont comptés par phase, donc dans `journal`.
            "appels_outils": None,
            "format_appels": "phases isolées",
            "pic_input": m.get("peak_input_tokens"),
            "total_output": m.get("output_tokens_total"),
            "cycles": m.get("cycles"),
            "etapes": m.get("etapes"),
            "contradictions": m.get("contradictions"),
            "fin": m.get("fin"),
            "journal": m.get("journal"),
        }
    return no_metrics(transcript)


def no_metrics(transcript):
    """Repli : verdict objectif seulement, pas de comptage de tokens."""
    return {"tours": None, "appels_outils": None, "format_appels": "non instrumente"}


# Scenario en cours, pose par `run()`. Variable de module plutot qu'un parametre :
# la signature des builders (model, workdir, prompt) est commune aux huit harnais,
# et la changer pour un seul serait disproportionne.
SCENARIO_COURANT = None

OPENCODE = os.environ.get("BENCH_OPENCODE", str(Path.home() / ".opencode/bin/opencode"))


def opencode_command(model, workdir, prompt):
    """opencode en mode non interactif, AVEC ses MCP (dont context7).

    Motif (2026-09-14). Tous les harnais du banc etaient jusqu'ici prives de
    documentation : `pi` passe `--no-extensions`, qui coupe aussi les MCP, et le
    plancher `nu` n'expose que read/write/edit/bash. Or le premier scenario a
    contrat NON fourni -- `crepuscule-amorce` -- echoue precisement sur une API
    mal connue (`Vector3`/`Matrix4` non definis, import `vector_math` absent).
    On avait donc exclu par construction le seul outil qui repare ce defaut.

    opencode est retenu plutot que `pi` parce que son MCP est NATIF : `pi` n'en a
    pas et exigerait `pi-mcp-extension`. Sa configuration (`~/.config/opencode`)
    porte deja context7.

    Cout mesure du sur-outillage : 36 489 tokens d'entree au PREMIER tour sur une
    tache triviale, contre 18 857 pour le preambule de `pi`. C'est une variable a
    surveiller, pas un detail -- elle se paie a chaque tour.

    `--auto` approuve les permissions : sans lui la campagne attend une reponse
    humaine et le banc expire sans rien dire.
    """
    cle = Path.home() / ".config" / "brain" / "localai-key"
    env = {"LOCALAI_API_KEY": cle.read_text().strip()} if cle.exists() else {}
    # NEUTRALISER `instructions` de la config globale, et RIEN D'AUTRE.
    #
    # `~/.config/opencode/opencode.json` pointe `instructions` sur
    # AGENTS.caveman.md, qui demande au modele de repondre par fragments et de
    # supprimer les articles. Mesurer un agent de code sous cette consigne
    # mesurerait le style, pas la competence -- c'est le motif exact du
    # `--no-context-files` de `pi`.
    #
    # OPENCODE_CONFIG ne conviendrait pas : il FUSIONNE au lieu de remplacer.
    # OPENCODE_CONFIG_CONTENT s'applique en dernier, donc il ecrase la cle.
    #
    # `~/.config/opencode/AGENTS.md` reste charge (opencode le charge toujours,
    # aucun drapeau ne le retire) et c'est VOULU : il ne contient que la consigne
    # d'usage de context7, c'est-a-dire precisement le levier mesure.
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"instructions": []})
    return [
        OPENCODE,
        "run",
        "--dir",
        str(workdir),
        "-m",
        model,
        "--format",
        "json",
        "--auto",
        prompt,
    ], env


def opencode_metrics(transcript):
    """Metriques depuis le flux d'evenements JSON d'opencode (--format json).

    Un tour = un `step_finish`. Les compteurs de tokens y sont CUMULES sur la
    session (input croit a chaque pas), donc `total_input` se lit sur le DERNIER
    evenement et non par somme -- sommer donnerait un total quadratique.
    """
    turns = 0
    calls = []
    peak_input = 0
    dernier_in = dernier_out = 0
    lignes_illisibles = 0
    stop = None
    for line in transcript.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        except RecursionError:
            lignes_illisibles += 1
            continue
        part = ev.get("part") or {}
        if ev.get("type") == "tool_use":
            calls.append(part.get("tool"))
        if ev.get("type") == "step_finish":
            turns += 1
            stop = part.get("reason") or stop
            toks = part.get("tokens") or {}
            entree = toks.get("input") or 0
            peak_input = max(peak_input, entree)
            dernier_in = max(dernier_in, entree)
            dernier_out = max(dernier_out, toks.get("output") or 0)
    return {
        "tours": turns,
        "appels_outils": len(calls),
        "outils_utilises": sorted(set(c for c in calls if c)),
        "format_appels": "json" if calls else "aucun",
        "pic_input": peak_input,
        "total_input": dernier_in,
        "total_output": dernier_out,
        "lignes_illisibles": lignes_illisibles,
        "erreur_modele": None,
        "stop_reason": stop,
    }


OMP = os.environ.get("BENCH_OMP", str(Path.home() / ".local/bin/omp"))


def omp_command(model, workdir, prompt):
    """omp (oh-my-pi), configuration GLOBALE de `~/.omp/agent/`.

    Fork de pi, donc meme flux JSONL : `pi_metrics` s'applique tel quel.

    On ne passe AUCUN reglage en ligne de commande : le prompt de methode
    (APPEND_SYSTEM.md), les regles a interruption de flux (rules/) et la
    declaration du serveur Dart (lsp.json) vivent dans `~/.omp/agent/` et
    doivent s'appliquer d'eux-memes. Mesurer autre chose que la configuration
    reellement installee n'aurait pas d'interet.

    Piege (2026-09-15) : la detection des serveurs de langage est cwd-only, au
    demarrage, sans recursion. Quand CREER le projet est la tache, `pubspec.yaml`
    n'existe pas encore et `dartls` ne demarre jamais -- en silence. D'ou le
    marqueur `.git` dans le lsp.json global.
    """
    cle = Path.home() / ".config" / "brain" / "localai-key"
    env = {"LOCALAI_API_KEY": cle.read_text().strip()} if cle.exists() else {}
    return [
        OMP,
        "-p",
        "--model",
        model,
        "--mode",
        "json",
        "--no-session",
        "--auto-approve",
        prompt,
    ], env


HARNESSES = {
    "pi": (pi_command, pi_metrics),
    "pi-abspath": (pi_abspath_command, pi_metrics),
    "pi-act": (pi_act_command, pi_metrics),
    "pi-sysmin": (pi_sysmin_command, pi_metrics),
    "pi-verif": (pi_verif_command, pi_metrics),
    "little-coder": (little_coder_command, pi_metrics),
    "little-coder-lens": (little_coder_lens_command, pi_metrics),
    "aider": (aider_command, aider_metrics),
    "nu": (nu_command, nu_metrics),
    "nu-pipeline": (nu_pipeline_command, nu_pipeline_metrics),
    "nu-contrat": (nu_contrat_command, nu_pipeline_metrics),
    "opencode": (opencode_command, opencode_metrics),
    "omp": (omp_command, pi_metrics),
}


# --- orchestration -------------------------------------------------------


def url_client_de(harness, model_prefixe=None):
    """URL a sonder pour ce harnais.

    Motif (2026-09-14, deux fois dans la meme session) : la sonde lisait
    HARNAIS_NU_BASE_URL quel que soit le harnais. Pour `opencode`, l'endpoint vit
    dans SA configuration, donc la sonde interrogeait 127.0.0.1:8080 et refusait
    la campagne avec « le modele demande n'est PAS servi ». Une URL qu'il faut
    penser a passer est une URL qu'on oublie ; on la deduit.
    """
    if harness == "opencode":
        cfg = Path.home() / ".config" / "opencode" / "opencode.json"
        try:
            fournisseurs = json.loads(cfg.read_text()).get("provider") or {}
        except (OSError, json.JSONDecodeError):
            fournisseurs = {}
        # Un seul fournisseur local declare aujourd'hui. S'il en apparait
        # plusieurs, le prefixe du modele (`localai/...`) les departage.
        for nom, conf in fournisseurs.items():
            base = (conf.get("options") or {}).get("baseURL")
            if base:
                return base
    if harness in ("little-coder", "little-coder-lens"):
        cfg = HERE / "config-little-coder" / "models.json"
        try:
            fournisseurs = json.loads(cfg.read_text()).get("providers") or {}
        except (OSError, json.JSONDecodeError):
            fournisseurs = {}
        prefixe = model_prefixe or ""
        for nom, conf in fournisseurs.items():
            base = conf.get("baseUrl")
            if base and (not prefixe or nom == prefixe):
                return base
    if harness == "omp":
        # Meme motif : l'endpoint vit dans la configuration GLOBALE du harnais,
        # pas dans une variable d'environnement du banc.
        cfg = Path.home() / ".omp" / "agent" / "models.yml"
        try:
            import yaml

            fournisseurs = (yaml.safe_load(cfg.read_text()) or {}).get("providers") or {}
        except (OSError, ImportError, ValueError):
            fournisseurs = {}
        prefixe = model_prefixe or ""
        for nom, conf in fournisseurs.items():
            base = conf.get("baseUrl")
            if base and (not prefixe or nom == prefixe):
                return base
    return os.environ.get("HARNAIS_NU_BASE_URL", "http://127.0.0.1:8080/v1")


def preambule(harness, model, scenario_name, client_url=None):
    """Refuse de lancer une campagne dont les leviers ne mordent pas.

    Motif (2026-08-06). Bilan des pannes de la semaine : une vingtaine de defauts
    de plomberie, dont UN SEUL relevait de l'isolation. La classe dominante est
    « l'instrument n'enregistre pas ce qu'il pretend enregistrer », et son cas le
    plus couteux est le BRAS DOUBLON SILENCIEUX -- une variable posee qui ne change
    rien, donc un bras qui mesure le temoin en croyant mesurer un levier.

    C'est arrive deux fois :
      - `HARNAIS_NU_RECHERCHE` n'existait pas dans bench.py ; le bras lance etait
        un duplicata du temoin, rattrape par hasard en 3 s grace a un `grep -c` ;
      - `HARNAIS_NU_CONVENTION_OUTILS` n'etait pas passe a boucle.py, et n'a ete vu
        qu'en inspectant l'argv du processus a la main.

    Depuis, je verifie a la main au `pgrep` avant chaque bras. Ceci est ce
    verificateur, en code.
    """
    problemes = []
    posees = {c for c in os.environ if c.startswith("HARNAIS_NU_")}

    # 1. Toute variable posee doit etre CONNUE du banc. Le jeu des connues est
    #    DERIVE de la source (une liste tenue a la main divergerait -- c'est
    #    exactement la classe de defaut qu'on traque). Faible seule : une variable
    #    citee en commentaire passerait. D'ou le controle 2.
    connues = set(re.findall(r"HARNAIS_NU_[A-Z_]+", Path(__file__).read_text()))
    # Variables transmises par l'ENVIRONNEMENT et non par un drapeau : boucle.py
    # les lit directement (l'environnement est herite par le Popen). Elles sont
    # donc legitimes ET invisibles au controle 2, qui compare des argv.
    #   HARNAIS_NU_API_KEY : boucle.py:1464, en-tete Authorization vers LocalAI.
    PAR_ENVIRONNEMENT = {"HARNAIS_NU_API_KEY"}
    connues |= PAR_ENVIRONNEMENT
    for var in sorted(posees - connues):
        problemes.append("%s : inconnue du banc, donc sans effet" % var)

    # 2. Le controle qui tranche vraiment : chaque variable posee doit CHANGER la
    #    commande construite. On la retire, on rebatit, on compare. Une variable
    #    qui ne change rien est un bras doublon.
    if harness.startswith("nu"):
        builder = HARNESSES[harness][0]
        global SCENARIO_COURANT
        precedent, SCENARIO_COURANT = SCENARIO_COURANT, scenario_name
        try:
            reference = builder(model, "/tmp/preambule", "tache")[0]
            for var in sorted((posees & connues) - PAR_ENVIRONNEMENT):
                garde = os.environ.pop(var)
                try:
                    sans = builder(model, "/tmp/preambule", "tache")[0]
                finally:
                    os.environ[var] = garde
                if sans == reference:
                    problemes.append(
                        "%s = %r : ne change PAS la commande -> bras doublon du temoin"
                        % (var, garde[:40])
                    )
        finally:
            SCENARIO_COURANT = precedent

    # 3. Le modele SERVI, jamais suppose. Le 2026-08-04, gemma a ete mesure a
    #    74,6 tok/s et le chiffre attribue a l'A3B, dont le vrai debit est 28,8 :
    #    le port etait occupe par le serveur precedent.
    if client_url:
        servi = _modele_servi(client_url, model)
        if servi:
            print("  modele servi : %s (present dans /v1/models)" % servi)
        else:
            problemes.append(
                "%s : le modele demande (%s) n'est PAS servi, ou /v1/models est "
                "illisible" % (client_url, model)
            )

    if problemes:
        sys.exit(
            "PREAMBULE REFUSE -- la campagne mesurerait autre chose que prevu :\n  "
            + "\n  ".join(problemes)
        )


def _modele_servi(url, attendu=None):
    """Nom du modele que le serveur repond. None si illisible. Ne leve jamais.

    S'AUTHENTIFIE si une cle LocalAI est disponible. Sans ca, la sonde recevait un
    401 sur toute instance LocalAI -- l'authentification est dans l'APPLICATION, pas
    seulement dans l'ingress, donc un port-forward ne la contourne pas. Consequence
    mesuree le 2026-09-09 : le preambule (ajoute le 2026-08-06) refusait TOUTE
    campagne sur un modele `localai/...`, et le dernier releve tetris datait du
    29 juillet. Le maillon tetris exige par promote.sh n'etait donc pas « oublie »,
    il etait INATTEIGNABLE. On reutilise le meme fichier de cle que le harnais aider
    plus bas dans ce fichier, pour ne pas avoir deux sources de verite.
    """
    try:
        import urllib.request

        req = urllib.request.Request(url.rstrip("/") + "/models")
        key_file = Path.home() / ".config" / "brain" / "localai-key"
        if key_file.exists():
            req.add_header("Authorization", "Bearer " + key_file.read_text().strip())
        with urllib.request.urlopen(req, timeout=10) as rep:
            data = json.loads(rep.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - sonde d'environnement, aucune raison de tuer le banc
        return None
    # Deux formes de reponse, et deux semantiques.
    #   llama-server : un SEUL modele par serveur, champ `model` -> le premier suffit.
    #   LocalAI      : PLUSIEURS modeles servis, champ `id` -> prendre le premier ne
    #                  veut rien dire (c'etait `trellis2-4b` le 2026-09-09). Ce qu'il
    #                  faut verifier, c'est que le modele DEMANDE est bien la.
    entrees = data.get("models") or data.get("data") or []
    noms = [
        os.path.basename(str(e.get("model") or e.get("id") or ""))
        for e in entrees
        if isinstance(e, dict)
    ]
    noms = [n for n in noms if n]
    if attendu:
        cible = os.path.basename(str(attendu))
        return cible if cible in noms else None
    return noms[0] if noms else None


def slug_de(scenario_name, harness, model):
    return "%s-%s-%s" % (
        scenario_name,
        harness,
        re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-"),
    )


def run_once(harness, model, scenario_name, timeout, essai=1, total=1):
    """Une seule exécution. Retourne (resultat, transcript), n'écrit rien."""
    global SCENARIO_COURANT
    SCENARIO_COURANT = scenario_name
    scenario = SCENARIOS[scenario_name]
    prompt = scenario["prompt"].read_text()
    fixture = scenario["fixture"]
    build_command, parse_metrics = HARNESSES[harness]

    slug = slug_de(scenario_name, harness, model)
    # Un workdir par essai : chaque exécution part d'une copie fraîche, sinon le
    # second essai hériterait du code produit par le premier.
    suffixe = "" if total == 1 else "-r%d" % essai
    workdir = Path("/tmp") / ("harness-bench-" + slug + suffixe)
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(fixture, workdir)
    for cache in workdir.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    if scenario.get("depot_git"):
        _init_depot(workdir)
    # PREPARATION : ce que le sujet est cense trouver DEJA FAIT. Sur
    # `diagnostic-import`, `dart pub get` doit avoir tourne avant l'agent, sinon
    # le serveur de langage declare inexistant tout ce qui vient d'un paquet et
    # la sonde mesure un faux positif au lieu du vrai mur (mesure du 2026-09-17).
    # Un echec ici est FATAL : un tirage sur une fixture mal preparee ne mesure
    # rien, et se taire le ferait passer pour un resultat.
    for commande in scenario.get("preparation") or ():
        argv = list(commande)
        if scenario.get("sdk_bin"):
            argv[0] = str(Path(scenario["sdk_bin"]) / argv[0])
        pret = subprocess.run(
            argv, cwd=str(workdir), capture_output=True, text=True, timeout=300
        )
        if pret.returncode != 0:
            sys.exit(
                "preparation echouee (%s) : %s"
                % (" ".join(commande), (pret.stderr or pret.stdout).strip()[-400:])
            )

    # Par ETAGE quand le scenario en a : sur une fixture deja partiellement verte
    # (`columns-web` demarre a 80/109), un seul appel pytest annonce 0 passed, parce
    # que l'import manquant de l'etage a ecrire interrompt la collecte de TOUTE la
    # suite. Le verdict n'en dependait pas, mais la ligne se lisait « part de zero ».
    if scenario.get("oracle"):
        shutil.copy(scenario["oracle"], workdir / Path(scenario["oracle"]).name)
    if scenario.get("verifieur"):
        # Rien a mesurer AVANT : `crepuscule-amorce` part d'un repertoire qui ne
        # contient qu'une spec, donc aucun test ne peut exister. Lancer pytest la
        # dessus a plante la premiere campagne (TypeError sur un `cibles=[None]`),
        # et meme sans planter la ligne « depart » n'aurait rien voulu dire.
        before = (0, 0, "", None)
    elif scenario.get("etages"):
        p = f = 0
        for _, fichier, _ in scenario["etages"]:
            pe, fe, _, _ = run_pytest(
                workdir, cibles=[fichier], binaire=scenario.get("pytest")
            )
            p += pe
            f += fe
        before = (p, f, "", None)
    else:
        before = run_pytest(workdir)
    print("depart : %s passed, %s failed" % (before[0], before[1]), flush=True)
    # ORACLE RETIRE apres avoir servi a mesurer le depart, AVANT que l'agent ne
    # demarre. Il etait depose ici et jamais retire : `verify()` promet « depose
    # au moment de NOTER seulement » et les notes de `pronote` disent « des tests
    # visibles donneraient la reponse au lieu de la faire trouver ». Les deux
    # etaient faux -- le fichier restait dans le workdir pendant tout le tirage.
    # Trouve le 2026-09-17 en branchant `sql-sessions`, qui aurait herite du trou.
    if scenario.get("oracle"):
        (workdir / Path(scenario["oracle"]).name).unlink(missing_ok=True)

    # APPARIEMENT : le tirage i de tout bras utilise GRAINES[i-1]. La graine varie
    # d'un tirage a l'autre (sinon les cinq seraient identiques) et reste la meme
    # d'un bras a l'autre — c'est ce qui transforme une comparaison 5 contre 5 noyee
    # dans la variance en 5 differences appariees. Voir GRAINES.
    #
    # Pose dans os.environ AVANT build_command, qui lit HARNAIS_NU_SEED comme les
    # autres reglages d'echantillonnage. Ne s'active que si GRAINES_ACTIVES : sans
    # ca le temoin garderait ses graines aleatoires et l'historique resterait
    # comparable.
    if GRAINES_ACTIVES and GRAINE_IMPOSEE is None:
        os.environ["HARNAIS_NU_SEED"] = str(GRAINES[(essai - 1) % len(GRAINES)])
    argv, env_extra = build_command(model, workdir, prompt)
    env = dict(os.environ)
    env.update(env_extra)

    started = time.time()
    timed_out = False

    # Malgre text=True, TimeoutExpired peut porter du bytes sur un flux et du
    # str sur l'autre : on decode chaque morceau AVANT de concatener, sinon on
    # perd le transcript sur un TypeError et le timeout devient invisible.
    def _texte(flux):
        if flux is None:
            return ""
        return flux.decode("utf-8", "replace") if isinstance(flux, bytes) else flux

    # start_new_session : le harnais devient chef d'un groupe de processus. Sans
    # ca, un timeout ne tue que le harnais lui-meme et les PETITS-FILS survivent
    # (l'agent teste lance `bash -c "... && pytest -q"` ; du code genere qui boucle
    # a l'infini laisse alors un pytest orphelin a 100% CPU, indefiniment).
    # stdin FERME : pi (et ses derives omp, little-coder) lit un stdin qui est
    # un tube comme un prompt a venir et attend l'EOF indefiniment -- « Reading
    # prompt from piped stdin ». Sous nohup le banc heritait de /dev/null par
    # hasard ; lance depuis un terminal ou un outil, il pendrait au timeout.
    proc = subprocess.Popen(
        argv,
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        transcript = _texte(out) + _texte(err)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        _tuer_groupe(proc)
        out, err = proc.communicate()  # reap : le groupe est mort
        transcript = _texte(out) + _texte(err)
        returncode = -1
        timed_out = True
    elapsed = round(time.time() - started, 1)

    result = {
        "essai": essai,
        # Horodatages ABSOLUS, poses a la source. Avant le 2026-08-06, la seule date
        # d'une campagne etait dans son NOM DE FICHIER : un resultat deplace ou
        # renomme perdait sa date, et aucun essai n'en portait. Or on veut lire les
        # progres DANS LE TEMPS, ce qui exige que chaque mesure se date elle-meme.
        "horodatage_debut": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
        "horodatage_fin": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duree_s": elapsed,
        "timeout": timed_out,
        "returncode": returncode,
        "depart": {"passed": before[0], "failed": before[1]},
        "workdir": str(workdir),
    }
    # Le transcript est posé sur le disque AVANT toute analyse. Il l'était après,
    # si bien qu'une exception du parseur détruisait l'unique trace de l'essai —
    # exactement ce qui s'est produit le 2026-09-11.
    try:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / ("%s-r%d.transcript" % (slug, essai))).write_text(transcript)
    except OSError:
        pass
    result.update(parse_metrics(transcript))
    result.update(verify(workdir, scenario))
    return result, transcript


def mediane(valeurs):
    """Mediane ARRONDIE a l'entier : on compte des tests, pas des fractions.

    L'algorithme vient de `statistics.median` (stdlib) plutot que d'une selection
    ecrite a la main — cette derniere avait fini par exister en DEUX exemplaires
    (`mediane` et `mediane_ratio`), et son arrondi code en dur avait failli
    ecraser un ratio (0,34 et 0,68 donnaient 1). Une seule implementation, deux
    politiques d'arrondi explicites."""
    propres = [v for v in valeurs if v is not None]
    return round(statistics.median(propres)) if propres else None


def mediane_ratio(valeurs, decimales=3):
    """Mediane d'un RATIO : meme calcul, mais l'arrondi garde des decimales.
    `mediane` ecraserait la valeur (0,34 et 0,68 donneraient 1)."""
    propres = [v for v in valeurs if v is not None]
    return round(statistics.median(propres), decimales) if propres else None


def run(harness, model, scenario_name, timeout, runs=1):
    """Exécute `runs` fois et agrège.

    Pourquoi plusieurs essais : la température n'est pas nulle (0.6 dans nos
    configs), donc UNE exécution est un tirage, pas une mesure. Constaté le
    2026-07-29 : deux runs de la même paire modèle/harnais sur tetris ont donné
    38/44 puis 21/44 — un écart de 17 tests que rien ne permettait d'attribuer
    soit à un changement de prompt, soit au hasard. Le gate de promote.sh doit
    donc trancher sur la MÉDIANE, jamais sur un tirage.
    """
    if harness not in HARNESSES:
        sys.exit("harnais inconnu: %s (connus: %s)" % (harness, ", ".join(HARNESSES)))
    # UNE fois par campagne, avant le premier tirage : refuse une campagne dont les
    # leviers ne mordent pas. Un bras doublon coute 40 minutes de GPU et une
    # conclusion fausse. Place ici et non dans run_once, qui est appele par tirage.
    prefixe = model.split("/")[0] if "/" in model else None
    preambule(harness, model, scenario_name, url_client_de(harness, prefixe))
    scenario = SCENARIOS[scenario_name]
    slug = slug_de(scenario_name, harness, model)

    essais = []
    for i in range(1, runs + 1):
        if i == 1:
            # Imprimees AVANT le premier essai, pas enfouies dans le code : une
            # note d'oracle qu'on ne lit pas ne protege de rien. Le 2026-08-02
            # j'ai bati la fixture `attrs` puis DECOUVERT apres coup que la
            # boucle de verification la sauvait — le score ne discriminait rien.
            for ligne in SCENARIOS[scenario_name].get("notes_oracle", ()):
                print("  [oracle] %s" % ligne, flush=True)
        print("=== essai %d/%d ===" % (i, runs), flush=True)
        res, transcript = run_once(harness, model, scenario_name, timeout, i, runs)
        essais.append(res)
        print(
            "  %s  %s/%s tests  %s tours  pic %s  %ss"
            % (
                res["verdict"],
                res["tests_passed"],
                res["tests_attendus"],
                res.get("tours"),
                res.get("pic_input"),
                res["duree_s"],
            ),
            flush=True,
        )
        if res.get("etages"):
            # Les deux etages a l'ecran, pas seulement dans le JSON : « 44 en
            # regression, 0 en extension » et « 30 en regression » sont deux
            # defaillances tres differentes, et la seconde doit sauter aux yeux.
            print(
                "        %s"
                % "  ".join(
                    "%s %s/%s" % (nom, e["passed"], e["attendus"])
                    for nom, e in res["etages"].items()
                ),
                flush=True,
            )
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / ("%s-r%d.transcript" % (slug, i))).write_text(transcript)
        archive_trajectoire(res.get("workdir"), "%s-r%d" % (slug, i))
        # Le CODE, pour les scenarios ou il est le livrable et non un moyen.
        if scenario.get("archiver_projet"):
            archive_projet(res.get("workdir"), "%s-r%d" % (slug, i))

    scores = [e["tests_passed"] for e in essais]
    attendus = scenario["expected_tests"]

    # La médiane ne porte QUE sur les essais dont le code compile : mélanger un 0/44
    # de collecte avec un 41/44 ne compare pas deux performances, ça compare une
    # performance à une panne de l'instrument. Les deux autres classes sont rapportées
    # comme des TAUX — « 1 essai sur 3 ne compile pas » informe sur le modèle, mais
    # ce n'est pas un score de zéro.
    # Un essai balaye porte un score REEL (mesure test par test), il entre donc dans
    # la mediane au meme titre qu'un essai propre.
    COMPARABLES = (ISSUE_OK, ISSUE_PARTIEL)
    notables = [e["tests_passed"] for e in essais if e.get("issue") in COMPARABLES]
    med = mediane(notables) if notables else None
    n_collecte = sum(1 for e in essais if e.get("issue") == ISSUE_COLLECTE)
    n_pend = sum(1 for e in essais if e.get("issue") == ISSUE_PEND)
    n_balaye = sum(1 for e in essais if e.get("issue") == ISSUE_PARTIEL)
    result = {
        "scenario": scenario_name,
        # La campagne se DATE ELLE-MEME : deduits des essais, donc coherents avec eux
        # et sans dependre du nom de fichier. C'est ce qui permet de lire une serie
        # chronologique (cf. `inventaire.py --chronologie`).
        "horodatage_debut": min(
            (e.get("horodatage_debut") for e in essais if e.get("horodatage_debut")),
            default=None,
        ),
        "horodatage_fin": max(
            (e.get("horodatage_fin") for e in essais if e.get("horodatage_fin")),
            default=None,
        ),
        "harnais": harness,
        "modele": model,
        "runs": runs,
        # `tests_passed` reste présent et vaut la MÉDIANE : les consommateurs
        # existants (promote.sh) continuent de fonctionner et lisent d'emblée la
        # valeur agrégée plutôt qu'un tirage.
        "tests_passed": med,
        "tests_passed_median": med,
        "tests_passed_min": min(notables) if notables else None,
        "tests_passed_max": max(notables) if notables else None,
        "tests_passed_ecart": (max(notables) - min(notables)) if notables else None,
        # `_tous` garde TOUS les tirages, y compris les 0 de collecte, pour rester
        # relisible ; `_notables` est ce sur quoi la médiane est calculée.
        "tests_passed_tous": scores,
        "tests_passed_notables": notables,
        "essais_comparables": len(notables),
        "essais_erreur_collecte": n_collecte,
        "essais_pytest_pend": n_pend,
        "essais_balayes": n_balaye,
        "tests_attendus": attendus,
        # Un PASS exige AUSSI une MAJORITE d'essais comparables.
        #
        # Motif (2026-09-14) : campagne opencode sur crepuscule-amorce, essais
        # 3/3, 0/3, 0/3 -- les deux echecs ecartes comme « ne compile pas », donc
        # la mediane calculee sur UN seul essai, donc verdict PASS. Le banc a
        # declare reussie une campagne ou rien n'a fonctionne deux fois sur trois.
        #
        # Ecarter un essai qui ne compile pas reste juste : une coquille ne doit
        # pas tirer la mediane vers le bas. Mais quand la MAJORITE des essais ne
        # compile pas, ce n'est plus du bruit, c'est le resultat -- et c'est
        # exactement le motif qui avait fait ecarter ornith-1.5 (44/44 une fois
        # sur six).
        "verdict": (
            "PASS"
            if med == attendus and len(notables) * 2 > runs
            else "FAIL"
        ),
        "tours_median": mediane([e.get("tours") for e in essais]),
        "pic_input_median": mediane([e.get("pic_input") for e in essais]),
        "duree_s_median": mediane([e.get("duree_s") for e in essais]),
        # Metriques de COUT (regle ThinkingCap) : ce qui departage des scores
        # satures. Calculees sur les seuls essais COMPARABLES et a score non nul —
        # diviser par 0 test reussi n'a pas de sens, et un 0/44 de collecte
        # gonflerait artificiellement le ratio.
        #
        # ⚠️ Ne JAMAIS lire ces ratios sans le score absolu a cote : biais
        # d'abandon mesure (bonsai 3,8 tests/tour a 19/44 contre gemma 2,9 a
        # 41/44 — le plus « efficace » est celui qui a abandonne le plus tot).
        "sortie_par_test_median": mediane_ratio(
            [
                e["total_output"] / e["tests_passed"]
                for e in essais
                if e.get("issue") in COMPARABLES
                and e.get("tests_passed")
                and e.get("total_output")
            ]
        ),
        "tours_par_test_median": mediane_ratio(
            [
                e["tours"] / e["tests_passed"]
                for e in essais
                if e.get("issue") in COMPARABLES
                and e.get("tests_passed")
                and e.get("tours")
            ]
        ),
        # Piege 21 : les defauts de nu_command ne sont PAS la config de reference,
        # et un resultat qui ne porte pas sa config a produit une campagne
        # invalide sans que rien ne le signale (2026-07-31 : quatre reglages
        # differaient, diagnostique seulement apres coup). Chaque fichier de
        # resultat se decrit desormais lui-meme.
        "config_env": {
            cle: valeur
            for cle, valeur in sorted(os.environ.items())
            if cle.startswith("HARNAIS_")
        },
        "commande": " ".join(sys.argv),
        # Config SERVEUR active, publiee par serveur.sh. Sans elle, un drapeau
        # comme `-n 16384` plafonne le rejeu de troncature en silence : trois
        # campagnes d'Ornith ont ete invalidees ainsi le 2026-08-04, et l'argv
        # n'existait que dans l'historique du shell. Il voyage desormais avec
        # les scores.
        "serveur_actif": _serveur_actif(),
        # Hash de l'ENONCE tel qu'il etait AU MOMENT du run. `columns` et
        # `columns-global` ne different que par lui, et l'ecart mesure entre eux
        # (tours/test 0,470 -> 0,312) serait invisible sans ce champ.
        "prompt_sha256": _sha_prompt(scenario_name),
        # Le CONTRAT (docstrings + assertions des tests proteges). Distinct de
        # l'enonce : on peut resserrer l'un sans toucher l'autre, et l'empreinte doit
        # bouger dans les deux cas.
        "contrat_sha256": _sha_contrat(scenario_name),
        "format_appels": essais[-1].get("format_appels"),
        "essais": essais,
    }

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS / ("%s-%s.json" % (slug, stamp))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    print("\n=== agrégat sur %d essai(s) ===" % runs)
    for i, e in enumerate(essais, 1):
        etiquette = {
            ISSUE_OK: "",
            ISSUE_COLLECTE: "  <- NE COMPILE PAS",
            ISSUE_PEND: "  <- pytest pend",
            ISSUE_PARTIEL: "  <- un test boucle, note test par test",
        }.get(e.get("issue"), "")
        print(
            "  essai %d : %2s/%s  %s lignes ecrites%s"
            % (i, e["tests_passed"], attendus, e.get("lignes_ecrites"), etiquette)
        )
    if notables:
        print(
            "  médiane sur %d essai(s) comparable(s) : %s/%s   (min %s, max %s, écart %s)"
            % (
                len(notables),
                med,
                attendus,
                result["tests_passed_min"],
                result["tests_passed_max"],
                result["tests_passed_ecart"],
            )
        )
    else:
        print("  ⚠️  AUCUN essai comparable : rien à médianiser")
    if n_balaye:
        print(
            "  %d/%d essai(s) ont pendu en bloc et ont été notés test par test :"
            " leur score est réel et compte dans la médiane." % (n_balaye, runs)
        )
    if n_collecte or n_pend:
        print(
            "  hors médiane : %d/%d ne compile(nt) pas, %d pend(ent)"
            % (n_collecte, runs, n_pend)
        )
        print(
            "     ⚠️  un 0/44 de collecte n'est PAS une page blanche (cf. lignes"
            " écrites) : c'est souvent une coquille qui annule tout le paquet."
        )
    print("  tours méd.  : %s" % result["tours_median"])
    print("  pic méd.    : %s" % result["pic_input_median"])
    # DURÉE et DÉBIT EFFECTIF. Signalé manquant le 2026-09-10 : sans eux, deux
    # candidats à score voisin sont indépartageables alors que l'un peut être sept
    # fois plus lent. Le débit effectif (tokens émis / seconde de campagne) n'est PAS
    # le tok/s du chargement : sur qwen3-coder-30b à ctx 131072 avec 34 couches
    # d'experts sur le CPU, il tombe à 6,7 alors que le balayage mesure 25,7 — les
    # trois quarts du temps partent en préremplissage et en exécution d'outils.
    #
    # ⚠️ SATURATION : si tous les essais sont `timeout`, la durée vaut le plafond et
    # ne départage RIEN. On le dit au lieu d'afficher un chiffre trompeur.
    duree = result.get("duree_s_median")
    tous_coupes = (
        all(e.get("timeout") for e in result["essais"]) if result["essais"] else False
    )
    sorties = [e.get("total_output") or 0 for e in result["essais"]]
    durees = [e.get("duree_s") or 0 for e in result["essais"]]
    debit = (sum(sorties) / sum(durees)) if sum(durees) else 0
    print(
        "  durée méd.  : %s s%s"
        % (
            duree,
            "   ⚠️ TOUS les essais coupés au plafond :"
            " la durée est saturée et ne départage rien"
            if tous_coupes
            else "",
        )
    )
    print(
        "  débit eff.  : %.1f tok/s émis sur la campagne (≠ tok/s du chargement)"
        % debit
    )
    # Cout par test reussi : ce qui departage des scores satures. Imprime SOUS la
    # mediane du score, jamais seul — un ratio sans le score absolu se lit a
    # l'envers (biais d'abandon : le plus « efficace » est souvent celui qui a
    # abandonne le plus tot).
    if result["tours_par_test_median"] is not None:
        print(
            "  cout méd.   : %s tours/test  %s tokens sortie/test  (a lire AVEC le score)"
            % (result["tours_par_test_median"], result["sortie_par_test_median"])
        )
    illisibles = sum(e.get("lignes_illisibles") or 0 for e in result["essais"])
    if illisibles:
        print("  ⚠️  %d ligne(s) de transcript illisibles : des tours ont pu "
              "échapper au comptage" % illisibles)
    invalides = [e for e in result["essais"] if e.get("erreur_modele")]
    if invalides:
        print("  ⚠️  %d essai(s) INVALIDES : le modèle n'a pas chargé, ils ne "
              "mesurent rien" % len(invalides))
        for e in invalides:
            print("      essai %s : %s" % (e.get("essai"), e["erreur_modele"][:110]))
    print("  verdict     : %s" % result["verdict"])
    if runs == 1:
        print("  ⚠️  UN SEUL ESSAI : c'est un tirage, pas une mesure. --runs 3 minimum")
    print("-> %s" % out)
    return 0 if result["verdict"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", default="pi")
    parser.add_argument("--scenario", default="repair", choices=sorted(SCENARIOS))
    parser.add_argument("--model", required=False)
    # TIMEOUT PAR ESSAI : 2400 -> 500 s le 2026-09-09, -> 745 s le 2026-09-14.
    #
    # La regle : « meilleur du jour + 25 % ». Elle se recalcule quand l'incumbent
    # change, et c'est arrive sans que le plafond suive.
    #
    # 500 s etait cale sur qwen3-coder-30b-a3b-instruct (395, 401, 430 s pour
    # 32/44). Depuis le 2026-09-11 l'incumbent est gemma-4-12b-it-qat, qui fait
    # 44/44 en 596 s. Le plafond etait donc passe SOUS le temps du modele de
    # reference : il aurait coupe gemma lui-meme. Constate le 2026-09-14 sur
    # mellum2-12b-a2.5b, dont deux essais se sont arretes a 500,2 et 500,1 s en
    # plein travail -- leurs 33/44 et 28/44 sont des planchers, pas des scores.
    #
    # 596 x 1,25 = 745.
    #
    # Motif. Ornith-1.5-9B-MTP-IQ4_XS a fait 44/44 -- mais en 2312 s, avec 84 tours,
    # un pic de contexte de 76 210 tokens et 3,92 MILLIONS de tokens d'entree au
    # total, contre 223 851 pour l'incumbent. Soit 17,5x le cout pour 12 tests de
    # plus, et 250 tokens generes par ligne de code conservee. Ces 38 minutes ont
    # sature le swap (15/15 Go) et gele le bureau. Un tel candidat n'est pas
    # deployable, et le laisser courir 40 minutes ne fait que le confirmer plus tard.
    #
    # Le plafond ENCODE donc l'exigence au lieu de la decouvrir apres coup. Un essai
    # coupe est compte a part (« pend »), il ne se confond pas avec un echec.
    # A REVOIR A CHAQUE CHANGEMENT D'INCUMBENT. Le defaut ci-dessous n'est pas une
    # constante du banc, c'est une mesure qui se perime.
    parser.add_argument("--timeout", type=int, default=745)
    parser.add_argument(
        "--exclude-tools",
        default="",
        help="liste noire d'outils, separee par des virgules (famille pi "
        "uniquement ; ex. `dispatch`). Vide = inerte.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="nombre d'exécutions ; la MÉDIANE fait foi (défaut 3)",
    )
    parser.add_argument("--list-harnesses", action="store_true")
    args = parser.parse_args()
    if args.list_harnesses:
        print("\n".join(sorted(HARNESSES)))
        return 0
    if not args.model:
        parser.error("--model requis")
    global EXCLURE_OUTILS
    EXCLURE_OUTILS = args.exclude_tools
    return run(args.harness, args.model, args.scenario, args.timeout, args.runs)


if __name__ == "__main__":
    sys.exit(main())

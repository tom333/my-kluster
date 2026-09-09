# Spec de base — RTS type Command & Conquer, transposé en Terre du Milieu (Flutter)

Statut : **proposition de départ**, 2026-08-06. Rien n'est implémenté.
Juge du résultat : l'utilisateur. Oracle automatique proposé au § 2, à accepter ou refuser.

---

## 1. Décision d'architecture, et c'est la seule qui soit difficile à changer plus tard

**Une simulation déterministe en Dart pur, séparée du rendu Flame.**

La doc Flame (`doc/flame/game.md`) expose `update(double dt)` avec un `dt` **variable** —
il dépend de la fréquence d'affichage réelle. Une logique de jeu qui multiplie par `dt`
donne donc un résultat différent à chaque exécution. Le déterminisme ne peut pas venir
du moteur : il doit être construit au-dessus.

```
paquet  sim/     Dart pur, AUCUN import Flutter. Pas à pas FIXE (20 tics/s).
                 Ne connaît ni écran, ni sprite, ni entrée utilisateur.
paquet  jeu/     Flame. Lit l'état de `sim`, dessine, traduit les clics en ordres.
```

Règles du paquet `sim`, non négociables sinon le déterminisme est perdu en silence :

- **aucun `dt`** dans la logique : un tic vaut un tic
- **PRNG à graine explicite**, jamais `Random()` sans graine, jamais `DateTime.now()`
- **collections ordonnées** : itérer une `HashMap` donne un ordre non spécifié, ce qui
  suffit à faire diverger deux exécutions identiques
- arithmétique en **entiers** pour tout ce qui s'accumule (ressources, points de vie,
  progression de construction) — les flottants ne s'additionnent pas associativement

Ce que cette séparation achète, et pourquoi elle vaut sa contrainte :

1. la logique se teste avec `dart test`, sans écran, sans appareil, en millisecondes ;
2. une partie se **rejoue** depuis `(graine, journal d'ordres)` — voir § 2 ;
3. le multijoueur en pas verrouillé reste possible plus tard sans réécriture, parce
   qu'il exige exactement la même propriété ;
4. c'est ce qui en fait un scénario de banc exploitable (§ 6).

Rendu : `SpriteBatch` pour les unités (la doc le donne comme le chemin des atlas de
sprites), et la page `performance.md` de Flame insiste sur un point à respecter dès le
début — **ne pas allouer dans `update`/`render`** (pas de `Vector2` ni de `Paint`
construits par image).

---

## 2. Oracle proposé — hybride, parce que « c'est amusant » ne se teste pas

L'utilisateur juge : le ressenti, la lisibilité, l'esthétique, l'équilibre en tant que
plaisir de jeu. Rien de tout ça ne se met dans un test, et prétendre le contraire
produirait des tests qui mesurent autre chose que ce qui compte.

Mais **les règles, elles, sont vérifiables**, et ce sont elles qui cassent en silence :

| vérifiable par test | jugé par l'utilisateur |
|---|---|
| accumulation de ressources par tic | est-ce que le rythme est agréable |
| durées de construction, file d'attente | est-ce que l'attente est frustrante |
| résolution d'un combat (dégâts, portée, cadence) | est-ce que les combats sont lisibles |
| accessibilité d'une destination (pathfinding) | est-ce que les unités ont l'air bêtes |
| champ de vision, brouillard | est-ce que l'exploration est intéressante |
| conditions de victoire et de défaite | est-ce que la partie a un bon final |

**Et un oracle qui se paie presque rien : le rejeu.** Une partie est
`(graine, liste d'ordres horodatés en tics)`. Rejouer doit rendre **exactement** le
même état final. Un rejeu qui diverge est un défaut de déterminisme, détecté sans que
personne ait à décrire le comportement attendu.

C'est la meilleure affaire de cette spec : le rejeu sert à la fois de test de
non-régression global, de fonction « revoir la partie » pour le joueur, et de base
d'équilibrage (rejouer 200 parties avec des paramètres modifiés).

Proposition concrète : **les tests couvrent la colonne de gauche et le rejeu ; tout le
reste est ton jugement.** Si tu préfères zéro test, dis-le — mais alors le premier bug
de déterminisme sera trouvé par toi, en jouant, et il sera pénible à reproduire.

---

## 3. Transposition — ce qui change, ce qui reste

C&C repose sur cinq mécaniques imbriquées. La transposition garde la structure et
change le décor, sans inventer de mécanique nouvelle sauf une (§ 3.5).

### 3.1 La ressource

**Mithril** remplace le Tiberium. Filons affleurants sur la carte, épuisables. Extraits
par des **convois** (l'équivalent du Harvester) qui font l'aller-retour entre le filon
et une **forge**. Même boucle que C&C : l'économie est une chaîne logistique visible et
attaquable, pas un compteur qui monte.

Conséquence de conception à garder : couper les convois doit être une stratégie viable.
C'est ce qui rend la carte importante.

### 3.2 Les deux camps, asymétriques

| | **Peuples Libres** | **l'Ombre** |
|---|---|---|
| unités | peu, chères, robustes | nombreuses, bon marché, fragiles |
| production | lente, un bâtiment par type | rapide, files parallèles |
| vision | large (éclaireurs, hauteurs) | courte mais nombreuse |
| accès | infanterie lourde, archers, cavalerie | hordes, machines de siège, loups |

Cette asymétrie est celle de GDI contre Nod, et elle tombe juste thématiquement — ce
n'est pas une coïncidence à exploiter mollement, c'est le cœur de l'intérêt : deux
façons de jouer, pas deux jeux de couleurs différentes.

### 3.3 Base et construction

Reprise directe de C&C : un bâtiment central, construction **adjacente à l'existant**,
barre latérale de production, dépendances technologiques (pas de cavalerie sans écurie).
La contrainte d'adjacence est ce qui fait qu'une base a une forme, donc une géographie,
donc des points faibles.

### 3.4 Brouillard de guerre

Deux niveaux comme dans C&C : le **non exploré** (noir) et le **hors vue** (terrain
connu, unités invisibles). Thématiquement gratuit — l'Ombre s'étend, la vision recule.

### 3.5 La seule mécanique ajoutée : le cycle jour/nuit

Une seule, et elle est asymétrique :

- **de nuit** : l'Ombre gagne en vision et en cadence, les Peuples Libres perdent en
  vision ;
- **de jour** : l'inverse, plus fortement.

Pourquoi celle-là et pas d'autres : elle est thématique sans être décorative, elle
impose un **rythme** à la partie (attaquer ou se retrancher selon l'heure), elle est
entièrement déterministe donc testable, et elle coûte peu à implémenter. Une seule
mécanique originale bien intégrée vaut mieux que cinq empilées.

---

## 4. Tranche verticale 1 — ce qu'on construit d'abord

Un RTS complet est hors d'atteinte : C&C a la construction, l'économie, le brouillard,
le pathfinding de groupe, l'IA adverse, la campagne, le multijoueur. Le dire tout de
suite évite un projet qui s'arrête à 30 %.

**Tranche 1, jouable de bout en bout, sans IA adverse :**

1. carte à tuiles, une seule, dessinée à la main (pas d'éditeur)
2. un camp jouable (Peuples Libres), l'autre inerte (bâtiments à détruire)
3. **une** ressource, **un** convoi, **une** forge
4. **deux** types d'unité : un combattant au corps à corps, un archer
5. sélection à la boîte, ordre de déplacement, ordre d'attaque
6. pathfinding sur grille (A\*), sans évitement mutuel élaboré
7. brouillard, deux niveaux
8. condition de victoire : tous les bâtiments adverses détruits
9. rejeu par graine + journal d'ordres

Ce qui est **exclu** de la tranche 1, à dire pour ne pas le redécouvrir en route :
IA adverse, multijoueur, son, animations autres que déplacement, campagne, sauvegarde
en cours de partie, superarmes, plusieurs cartes, équilibrage.

Critère d'arrêt de la tranche : **tu joues une partie complète et tu la gagnes**.

---

## 5. Note de propriété intellectuelle, une fois

Les œuvres de Tolkien sont sous droits et la succession est connue pour les défendre.
Un projet personnel non distribué ne pose pas de question. En revanche, si ça sort un
jour, les **noms propres** sont le risque, pas les mécaniques.

Couverture qui ne coûte rien maintenant : **tous les noms propres dans un seul
fichier** (`sim/lib/noms.dart`). Renommer devient un changement d'un fichier au lieu
d'un ratissage. Rien d'autre à faire aujourd'hui.

---

## 6. Ce que ça apporte au banc `harness-bench`

Le paquet `sim/` est un sujet de mesure presque idéal, et pour une raison précise :
c'est de la **logique pure avec des règles vérifiables et aucun affichage**. `dart test`
sans appareil, en millisecondes.

Ça force par ailleurs les généralisations déjà identifiées (cf. mémoire
`project-banc-second-langage`) :

- analyse de sortie de tests : `flutter test` rend `00:03 +12: All tests passed!`, pas
  `12 tests collected` — le banc doit généraliser, pas s'adapter au cas Dart
- `PUB_CACHE` à rediriger dans le workdir, exactement comme `PIP_TARGET` (cf. la fuite
  d'environnement du 2026-08-06)
- `outils.remplacer` utilise le module `ast` **de Python** → inerte sur Dart
- CBM n'indexe pas Dart → `ou_defini`/`qui_utilise` probablement inertes

Et un bénéfice de mesure : Dart étant compilé, une faute de syntaxe casse la
construction immédiatement au lieu d'attendre un import. Retour d'erreur plus rapide et
plus franc qu'en Python.

---

## 7. Questions ouvertes, à trancher avant de coder

1. **Où vit le dépôt ?** Ce fichier est provisoirement dans `my-kluster/docs/` ; le jeu
   mérite son propre dépôt (comme `harnais-nu`).
2. **L'oracle du § 2 : accepté, réduit au rejeu seul, ou aucun test ?**
3. **Vue** : 2D vue de dessus, ou 2D isométrique ? L'isométrique double le coût du
   rendu et des assets pour un gain purement esthétique — je proposerais vue de dessus
   pour la tranche 1.
4. **Assets** : formes géométriques colorées pour la tranche 1 (et le jeu reste
   lisible), ou sprites dès le début ?

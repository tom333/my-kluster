# Crépuscule — RTS type Command & Conquer, en Terre du Milieu, Flutter 3D isométrique

Statut : **spec de départ**, 2026-08-06. Rien n'est implémenté.
Juge du résultat : l'utilisateur. Oracle automatique proposé au § 3.

`Crépuscule` est un **nom de code** : il évoque le cycle jour/nuit (§ 5.5) et ne porte
aucun nom propre issu de l'œuvre de Tolkien. Renommable sans conséquence (§ 7).

**Cible : Android.** Azimut de caméra **fixe** à 45°.
Outils présents sur la machine : Flutter 3.44.8 (stable), Dart 3.12.2.

---

## 1. Rendu : 3D isométrique — et ce que ça décide

Décision de l'utilisateur : **vraie 3D vue par une caméra isométrique**, pas des sprites
2D dessinés en projection isométrique à la Red Alert 2.

Conséquence immédiate, à dire avant tout le reste : **Flame sort du projet.** Flame est
un moteur 2D ; sa valeur (atlas de sprites, `SpriteBatch`) n'a pas d'objet en 3D. La
pile devient :

```
flutter_scene   rendu 3D reel (Flutter GPU / Impeller), import glTF, materiaux PBR
widgets Flutter interface : barre laterale de production, minicarte, ressources
```

### 1.1 Le point à ne pas découvrir en route : la projection orthographique n'existe pas

La doc de `flutter_scene` fournit `PerspectiveCamera`. Pour l'isométrique il faut une
projection **orthographique**, et elle n'est pas livrée : `CameraProjection` est une
classe **abstraite**, et la doc indique explicitement que les projections orthographiques
sont à obtenir en la sous-classant, en rendant sa propre `Matrix4` depuis
`getProjectionMatrix(aspectRatio)`.

Ce n'est pas difficile — une matrice ortho est standard — mais c'est la première chose à
écrire, et c'est une pièce dont l'absence surprendrait si on la découvrait au moment de
cadrer la caméra.

Isométrique = projection orthographique + caméra à 45° en azimut et ~30 à 35° en
élévation. Ces angles sont un choix esthétique à régler à l'œil, pas une constante.

### 1.2 Le rendu ne cadence pas la simulation

`SceneView` conduit sa propre boucle par image via `onTick(elapsed, deltaSeconds)`, et
`deltaSeconds` est **variable** — il dépend de la fréquence d'affichage réelle. Comme
avec Flame, le déterminisme ne peut donc pas venir du moteur de rendu (§ 2).

### 1.3 Android : ce que la doc garantit, et la réserve qui reste

Bonne nouvelle : Android est le cas le **mieux** servi. La doc de `flutter_scene` donne
iOS/Android/Web en support « complet », et sur Android **Impeller est le rendu par
défaut**, donc rien à activer de ce côté (Linux, macOS et Windows sont en aperçu et
exigent `--enable-impeller`).

Mise en route documentée :

```sh
flutter config --enable-native-assets        # une fois
flutter config --enable-dart-data-assets     # une fois, pour les materiaux .fmat
flutter create . --platforms=android
flutter run --enable-flutter-gpu --enable-impeller -d <appareil>
```

`Scene.initializeStaticResources()` doit être **attendu** avant tout rendu : le paquet
charge un bundle de shaders et une LUT BRDF de façon asynchrone.

**La réserve, à ne pas balayer** : la doc du paquet exige le canal **master** (Flutter
3.44+, Dart 3.10+) et qualifie l'API Flutter GPU d'**expérimentale**. La machine est sur
**stable 3.44.8** — la version convient, le canal non. Ça peut passer, ou pas. C'est
précisément ce que l'étape 0 tranche.

**Et un piège propre à Android** : l'émulateur est l'environnement où Vulkan et Impeller
sont les **moins** fiables. Un échec sur émulateur ne prouve donc pas que la pile est
inutilisable — il faut essayer un appareil réel avant de conclure. Inversement, un succès
sur appareil ne garantit pas l'émulateur, ce qui compte pour l'oracle (§ 3).

**Étape 0, avant toute logique de jeu : un cube en projection orthographique à l'écran.**

### 1.3bis Verdict de l'étape 0 (2026-08-06) — mesuré, pas suppose

**`flutter_scene` ne compile PAS sur Flutter stable 3.44.8.** Ni le `git HEAD`, ni la
version publiée 0.20.0 :

```
flutter_scene-0.20.0/lib/src/texture/texture2d.dart : le getter 'mipLevelCount' n'est
                                                      pas defini pour le type 'Texture'
flutter_scene-0.20.0/lib/src/geometry/geometry.dart : type 'gpu.VertexFormat' introuvable
flutter_scene-0.20.0/lib/src/scene_encoder.dart     : pas de parametre nomme 'vertexLayout'
flutter_scene-0.20.0/lib/src/widget_texture.dart    : membre introuvable 'Texture.fromImage'
```

Ce n'est donc pas un ecart HEAD-contre-release : `flutter_scene 0.20.0` cible un
`flutter_gpu` **plus recent** que celui livre avec stable. Et `flutter_gpu` est **fourni
avec le SDK** (`bin/cache/pkg/flutter_gpu`), donc sa version est imposee par le CANAL. La
doc annoncait « canal master » ; c'est confirme.

**L'emulateur n'est pas en cause** : AVD `telephone35`, API 35, Vulkan **1.2** expose
(`vulkan.level=1`, `vulkan.version=4206592`). Le mur est en amont de lui.

**Decision : un second SDK Flutter sur canal master, isole**
(`/home/moi/develop/flutter-master`), qui ne touche pas au SDK stable faisant tourner
`jeux_zoe`. Le projet vise ce SDK par chemin explicite. La revision master utilisee doit
etre **epinglee et notee**, sinon le projet cassera sous nous — master bouge tous les jours.

### 1.3ter Etape 0 FRANCHIE avec le SDK master (2026-08-06)

SDK isole : `/home/moi/develop/flutter-master`, **Flutter 3.47.0-1.0.pre-418**, revision
**`e26b384689`**, Dart 3.14.0. Revision a considerer comme **epinglee** : master bouge
tous les jours, et un projet qui suit master sans reference casse sans qu'on sache quand.

Resultats :

- `flutter build apk --debug` **reussit** (contre les 12 erreurs de compilation sous stable) ;
- l'application demarre, `Scene.initializeStaticResources()` aboutit, et la sonde affiche
  **`FLUTTER GPU OK`** a l'ecran ;
- `SceneView` rend une scene vide sans planter.

**Ce que ca ne prouve PAS**, et il faut le dire pour que personne ne surinterprete ce
texte vert :

1. **le backend etait OpenGLES, pas Vulkan** : le journal donne
   `Using the Impeller rendering backend (OpenGLES)` alors meme que l'emulateur expose
   Vulkan 1.2. Le chemin Vulkan -- celui qu'un Redmi Note 13 Pro prendra
   vraisemblablement -- reste **non teste** ;
2. **aucune performance mesuree** : scene VIDE, zero modele, zero unite. L'emulateur ne
   dit rien du debit d'images sur du vrai materiel ;
3. **la projection orthographique n'est pas ecrite** : la sonde utilise la
   `PerspectiveCamera` fournie. Le sous-classement de `CameraProjection` (§ 1.1) reste a
   faire -- et c'est volontaire, cf. § 6.1.

Prochain jalon de faisabilite, quand le telephone sera branche : le meme APK sur le Redmi,
pour voir si Impeller y choisit Vulkan et ce que ca donne en images par seconde.

**Ce que cet episode a coute et rapporte** : la porte de l'etape 0 a rendu son verdict
avant qu'une seule ligne de jeu soit ecrite, et sans brancher le telephone. Le temoin
utilise etait l'exemple AMONT, pas notre code : c'est ce qui permet de dire « la pile est
en cause » au lieu de « notre matrice orthographique est fausse ».

### 1.4 Ce que la 3D coûte, et ce qu'elle rend

**Coûte** : des modèles glTF/GLB. Il n'y a plus de « dessiner un rectangle coloré » :
même une unité de test est un fichier. Pour la tranche 1, une poignée de formes très
simples (un pavé, un cône, une dalle) suffit et reste lisible.

**Rend** : la rotation et le zoom de caméra deviennent gratuits, et une unité n'a plus
besoin de huit orientations dessinées à la main. En sprites isométriques, chaque unité
coûte 8 directions × N animations. En 3D, elle coûte un modèle.

### 1.5 Sélection et ordres — le vrai coût d'Android

En projection orthographique, convertir un point de l'écran en position sur le terrain
est simple : un rayon depuis le point, intersecté avec le plan du sol. L'azimut étant
**fixe**, la matrice ne change jamais et ce calcul se réduit à une transformation
constante. C'est l'intérêt principal de l'azimut fixe, avant même la simplification des
modèles.

**Mais les commandes de C&C ne survivent pas au tactile, et c'est la contrainte la plus
lourde du projet — plus lourde que la 3D.** C&C suppose : clic gauche pour sélectionner,
glisser pour la boîte de sélection, clic **droit** pour ordonner, molette pour zoomer,
bord d'écran pour défiler, survol pour les infobulles. Sur Android il n'y a **ni clic
droit, ni molette, ni survol**, et un seul geste de glissement — que la boîte de
sélection et le défilement de caméra se disputent.

Attribution proposée, choisie pour coller à ce qu'un utilisateur mobile attend déjà des
applications de cartographie :

| geste | effet |
|---|---|
| glisser à un doigt | **déplacer la caméra** |
| pincer à deux doigts | zoomer |
| toucher une unité | la sélectionner |
| **appui long puis glisser** | boîte de sélection |
| toucher le terrain, sélection active | ordre de déplacement |
| toucher un ennemi, sélection active | ordre d'attaque |
| double-toucher une unité | sélectionner toutes celles du même type à l'écran |

Le clic droit disparaît donc au profit d'un **ordre contextuel au toucher** : la nature
de l'ordre découle de ce qu'on touche, pas du bouton utilisé. C'est la seule façon de
garder une seule action pointée.

Deux conséquences à assumer :

- **pas de survol, donc pas d'infobulle.** Les informations d'unité doivent vivre dans un
  panneau permanent, jamais dans un état transitoire ;
- **la barre latérale de C&C est inabordable** sur un écran de téléphone. Barre **basse
  et repliable**, et conception **tablette d'abord, en paysage**. À trancher : téléphone
  visé ou tablette visée (§ 8).

Enfin, budget mobile : le nombre d'unités simultanées est borné par le GPU du téléphone,
pas par la simulation. Un matériau par camp et un minimum d'appels de dessin, dès le
début — c'est plus facile à tenir qu'à rattraper.

---

## 2. Décision d'architecture, et c'est la seule difficile à défaire

**Une simulation déterministe en Dart pur, séparée du rendu.**

```
paquet  sim/     Dart pur, AUCUN import Flutter. Pas à pas FIXE (20 tics/s).
                 Ne connaît ni écran, ni modèle 3D, ni entrée utilisateur.
paquet  jeu/     Flutter + flutter_scene. Lit l'état de `sim`, dessine, traduit les
                 clics en ordres. Interpole entre deux tics pour l'affichage.
```

Règles du paquet `sim`, non négociables sinon le déterminisme est perdu en silence :

- **aucun `deltaSeconds`** dans la logique : un tic vaut un tic
- **PRNG à graine explicite**, jamais `Random()` sans graine, jamais `DateTime.now()`
- **collections ordonnées** : itérer une `HashMap` donne un ordre non spécifié, ce qui
  suffit à faire diverger deux exécutions identiques
- arithmétique en **entiers** pour tout ce qui s'accumule (ressources, points de vie,
  progression de construction) — les flottants ne s'additionnent pas associativement

L'affichage tourne à la fréquence de l'écran et **interpole** entre le tic précédent et
le tic courant. La simulation reste à 20 tics/s quoi qu'il arrive.

Ce que cette séparation achète :

1. la logique se teste avec `dart test`, sans écran, sans appareil, en millisecondes ;
2. une partie se **rejoue** depuis `(graine, journal d'ordres)` — voir § 3 ;
3. le multijoueur en pas verrouillé reste possible plus tard sans réécriture ;
4. c'est ce qui en fait un scénario de banc exploitable (§ 6).

---

## 3. Oracle proposé — hybride, parce que « c'est amusant » ne se teste pas

L'utilisateur juge : le ressenti, la lisibilité, l'esthétique, l'équilibre en tant que
plaisir de jeu. Rien de tout ça ne se met dans un test, et prétendre le contraire
produirait des tests qui mesurent autre chose que ce qui compte.

Mais **les règles sont vérifiables**, et ce sont elles qui cassent en silence :

| vérifiable par test | jugé par l'utilisateur |
|---|---|
| accumulation de ressources par tic | est-ce que le rythme est agréable |
| durées de construction, file d'attente | est-ce que l'attente est frustrante |
| résolution d'un combat (dégâts, portée, cadence) | est-ce que les combats sont lisibles |
| accessibilité d'une destination (A\*) | est-ce que les unités ont l'air bêtes |
| champ de vision, brouillard | est-ce que l'exploration est intéressante |
| conditions de victoire et de défaite | est-ce que la partie a un bon final |
| cycle jour/nuit : les modificateurs s'appliquent | est-ce que le rythme imposé plaît |

### 3.1 Quatre niveaux, et ce que chacun peut seul établir

**Niveau 1 — `dart test` sur `sim/`.** Les règles et le rejeu. Rapide, déterministe, sans
écran ni appareil, sans Flutter du tout. C'est le cœur.

**Niveau 2 — la caméra testée comme de l'ARITHMÉTIQUE**, toujours dans `dart test`.
« L'unité en (12, 7) tombe-t-elle au bon endroit de l'écran ? » est une multiplication par
la matrice de caméra. L'azimut étant fixe, cette matrice est constante, donc ces tests sont
triviaux — et ils couvrent la sélection au toucher, qui est le morceau d'entrée le plus
facile à casser. **Aucun pixel, aucun émulateur.**

**Niveau 3 — aperçus visuels** (§ 3.2) : des images produites pour être regardées, pas
comparées.

**Niveau 4 — ton jugement.** Le ressenti, l'esthétique, l'équilibre-plaisir.

### 3.2 Conventions reprises de `jeux_zoe`, plutôt qu'inventées

Le projet Flutter existant (`/data/projets/perso/jeux_zoe`, « Lumi ») donne trois
conventions à reprendre telles quelles :

- **identifiant** : `ovh.tgu.lumi` → le nôtre sera `ovh.tgu.crepuscule`
- **versions du SDK** : `flutter.minSdkVersion` / `targetSdkVersion` / `compileSdkVersion`,
  jamais de valeur codée en dur. **Réserve** : Impeller-Vulkan demande API 29+, donc si le
  défaut de Flutter est plus bas il faudra remonter `minSdk` — à vérifier, pas à supposer
- **déploiement** : APK release puis
  `~/Android/Sdk/platform-tools/adb install -r build/app/outputs/flutter-apk/app-release.apk`

Et surtout un **motif d'aperçu visuel** déjà éprouvé : `test/apercu_visuel.dart` rend des
écrans et **écrit des PNG** dans `test/apercus/`, pour que l'humain les regarde. Ce n'est
pas une comparaison au pixel près — c'est de la production d'artefacts pour jugement. Bien
meilleur que ce que j'avais proposé, et sans émulateur.

**Réserve importante** : ce motif tourne dans `flutter_test`, qui rend sans GPU réel.
Flutter GPU / Impeller n'y fonctionnera vraisemblablement pas, donc **une scène 3D ne peut
pas être capturée ainsi**. Les aperçus du monde 3D doivent venir d'une capture d'appareil
ou d'émulateur (`adb exec-out screencap`). Le motif reste valable tel quel pour tout ce qui
est **interface en widgets** : barre de production, panneau d'unité, minicarte.

C'est là que l'émulateur gagne vraiment sa place : il est le seul à pouvoir montrer le 3D.

### 3.3 Ce que je conseille de NE PAS mettre sur l'émulateur

Deux pièges, et ils sont connus :

1. **L'émulateur est l'environnement où Impeller et Vulkan sont les moins fiables**
   (§ 1.3). Un test qui y échoue ne prouve donc rien sur le code. Règle : **tout échec
   d'un test d'émulateur est rejoué sur appareil réel avant d'être cru.** Sinon on
   passera des heures à corriger un pilote.

2. **Les tests par image de référence sur du 3D accéléré sont notoirement instables** :
   un pilote, une version, un anticrénelage suffisent à faire diverger les pixels. Une
   comparaison au pixel près produirait des échecs qui n'apprennent rien.

Donc sur émulateur, des assertions **robustes** plutôt que précises : l'image rendue
n'est pas uniforme (pas d'écran noir), l'application ne plante pas, un appui long suivi
d'un glissement produit bien N unités sélectionnées.

**Et le point qui économise le plus** : une grande partie de ce qu'on croit devoir
vérifier à l'écran se vérifie en **arithmétique sur le processeur**. « L'unité en (12, 7)
apparaît-elle au bon endroit de l'écran ? » est une multiplication par la matrice de
caméra — testable au niveau 1, sans émulateur, sans pixel, et de façon déterministe.
L'azimut étant fixe, cette matrice est constante, donc ces tests sont triviaux à écrire.

Ne mettre sur l'émulateur que ce qui **ne peut pas** être calculé.

**Et un oracle qui ne coûte presque rien : le rejeu.** Une partie est
`(graine, liste d'ordres horodatés en tics)`. Rejouer doit rendre **exactement** le même
état final. Un rejeu qui diverge est un défaut de déterminisme, détecté sans que
personne ait eu à décrire le comportement attendu.

C'est la meilleure affaire de cette spec, parce qu'elle sert trois fois : test de
non-régression global, fonction « revoir la partie » pour le joueur, et base
d'équilibrage (rejouer 200 parties avec des paramètres modifiés).

Proposition : **les tests couvrent la colonne de gauche et le rejeu ; tout le reste est
ton jugement.** Si tu préfères zéro test, le premier bug de déterminisme sera trouvé en
jouant, et il sera pénible à reproduire.

---

## 4. Transposition — ce qui change, ce qui reste

C&C repose sur cinq mécaniques imbriquées. On garde la structure, on change le décor, et
on n'ajoute qu'une mécanique (§ 4.5).

### 4.1 La ressource

**Mithril** remplace le Tiberium. Filons affleurants, épuisables. Extraits par des
**convois** faisant l'aller-retour entre le filon et une **forge**. Même boucle que C&C :
l'économie est une chaîne logistique **visible et attaquable**, pas un compteur qui monte.

Conséquence à préserver : couper les convois doit rester une stratégie viable. C'est ce
qui donne son importance à la carte.

### 4.2 Deux camps asymétriques

| | **Peuples Libres** | **l'Ombre** |
|---|---|---|
| unités | peu, chères, robustes | nombreuses, bon marché, fragiles |
| production | lente, un bâtiment par type | rapide, files parallèles |
| vision | large (éclaireurs, hauteurs) | courte mais nombreuse |
| accès | infanterie lourde, archers, cavalerie | hordes, machines de siège, loups |

C'est l'asymétrie GDI/Nod, et elle tombe juste thématiquement. Ce n'est pas une
coïncidence à exploiter mollement : c'est le cœur de l'intérêt, deux façons de jouer.

### 4.3 Base et construction

Reprise directe de C&C : bâtiment central, construction **adjacente à l'existant**,
barre latérale de production, dépendances technologiques. L'adjacence est ce qui donne
une **forme** à une base, donc une géographie, donc des points faibles.

### 4.4 Brouillard de guerre

Deux niveaux : **non exploré** (noir) et **hors vue** (terrain connu, unités invisibles).
En 3D, le hors-vue se rend par assombrissement du terrain plutôt que par un calque de
tuiles.

### 4.5 La seule mécanique ajoutée : le cycle jour/nuit

- **de nuit** : l'Ombre gagne en vision et en cadence, les Peuples Libres perdent en vision
- **de jour** : l'inverse, plus fortement

Pourquoi celle-là et pas d'autres : thématique sans être décorative, elle impose un
**rythme** à la partie (attaquer ou se retrancher selon l'heure), elle est entièrement
déterministe donc testable, et elle coûte peu. Une mécanique originale bien intégrée vaut
mieux que cinq empilées.

Bénéfice inattendu en 3D : le cycle se lit directement dans l'éclairage de la scène, donc
la mécanique est **visible sans interface**.

---

## 5. Tranche verticale 1 — ce qu'on construit d'abord

Un RTS complet est hors d'atteinte : C&C a la construction, l'économie, le brouillard, le
pathfinding de groupe, l'IA adverse, la campagne, le multijoueur. Le dire tout de suite
évite un projet qui s'arrête à 30 %.

**Étape 0 — la seule qui puisse invalider la spec** : un cube en projection
orthographique à l'écran, sur la plateforme cible (§ 1.3).

**Tranche 1, jouable de bout en bout, sans IA adverse :**

1. une carte à grille, dessinée à la main (pas d'éditeur), terrain plat
2. un camp jouable (Peuples Libres), l'autre inerte (bâtiments à détruire)
3. **une** ressource, **un** convoi, **une** forge
4. **deux** types d'unité : un combattant au corps à corps, un archer
5. modèles GLB minimaux (pavé, cône, dalle) — la lisibilité avant l'esthétique
6. caméra isométrique à **azimut fixe** : glisser pour déplacer, pincer pour zoomer
   (pas de rotation — elle est exclue, pas reportée)
7. commandes tactiles du § 1.5 : toucher pour sélectionner, appui long + glisser pour la
   boîte, ordre contextuel au toucher
8. A\* sur grille, sans évitement mutuel élaboré
9. brouillard, deux niveaux
10. cycle jour/nuit visible dans l'éclairage
11. victoire : tous les bâtiments adverses détruits
12. rejeu par graine + journal d'ordres

**Exclu** de la tranche 1, pour ne pas le redécouvrir en route : IA adverse, multijoueur,
son, animations autres que déplacement, campagne, sauvegarde en cours de partie,
superarmes, terrain accidenté, plusieurs cartes, équilibrage, **rotation de caméra**.

Critère d'arrêt : **tu joues une partie complète et tu la gagnes.**

---

## 6. Ce que ça apporte au banc `harness-bench`

### 6.1 DEUX scénarios, et le second est le plus intéressant

Remarque de l'utilisateur, 2026-08-06 : *« tu crées beaucoup de choses, donc on saura
seulement si [le modèle] peut produire du code, pas s'il peut créer un projet »*.

Elle est juste, et le verdict de l'étape 0 en est la démonstration : **la partie difficile
était de résoudre un conflit de version entre `flutter_scene` et le `flutter_gpu` du SDK**,
pas d'écrire une matrice orthographique. Livrer un squelette qui compile ferait donc
disparaître de la mesure la capacité qui compte le plus ici.

| scénario | départ | ce qu'il mesure | oracle |
|---|---|---|---|
| `crepuscule-logique` | paquet `sim/` vide + spec | écrire du code | tests cachés sur les règles |
| `crepuscule-amorce` | **répertoire vide** + spec | **créer un projet** | l'APK se construit, s'installe, la capture n'est pas uniforme |

Le second est rare dans les bancs existants, et il est **mécaniquement notable** :
« `flutter build apk` réussit » et « la capture n'est pas noire » ne demandent aucun
jugement humain.

**Règle de travail qui en découle** : les sondes de faisabilité restent jetables et hors
du dépôt (`/tmp`). Rien n'entre dans `crepuscule/` que la spec, tant que la question
« un agent sait-il amorcer ce projet ? » n'a pas été posée au banc.

### 6.2 Ce que le sujet exige du banc

Le paquet `sim/` est par ailleurs un sujet de mesure presque idéal : logique pure, règles
vérifiables, aucun affichage. `dart test` sans appareil, en millisecondes.

**Et le scénario devra épingler son SDK par l'environnement**, exactement comme les venvs
Python le 2026-08-06 : `PATH` vers le Flutter **master** isolé, et `PUB_CACHE` redirigé
dans le workdir pour que les paquets installés par l'agent ne polluent pas le cache global.
C'est le même mécanisme que `env_pour` / `PIP_TARGET` — et la même raison : sans lui,
l'agent hérite de l'environnement de l'outil qui le mesure.

Ça force les généralisations déjà identifiées :

- analyse de sortie de tests : `flutter test` rend `00:03 +12: All tests passed!`, pas
  `12 tests collected` — le banc doit **généraliser**, pas s'adapter au cas Dart
- `PUB_CACHE` à rediriger dans le workdir, exactement comme `PIP_TARGET` — même motif que
  la fuite d'environnement corrigée le 2026-08-06, qui doublait le taux d'échec du banc
- `outils.remplacer` utilise le module `ast` **de Python** → inerte sur Dart
- CBM n'indexe pas Dart → `ou_defini` / `qui_utilise` probablement inertes

Bénéfice de mesure : Dart est compilé, donc une faute de syntaxe casse la construction
immédiatement au lieu d'attendre un import. Retour d'erreur plus rapide et plus franc
qu'en Python.

Et un bénéfice de scénario : `pronote` a perdu son pouvoir discriminant (les deux modèles
y font 4/5 une fois la fuite bouchée). Il faut une tâche plus dure — celle-ci l'est, dans
un langage que les modèles ont moins vu.

---

## 7. Propriété intellectuelle, une fois

Les œuvres de Tolkien sont sous droits et la succession est connue pour les défendre. Un
projet personnel non distribué ne pose pas de question. Si ça sort un jour, ce sont les
**noms propres** qui sont le risque, pas les mécaniques.

Couverture qui ne coûte rien maintenant : **tous les noms propres dans un seul fichier**
(`sim/lib/noms.dart`). Renommer devient un changement d'un fichier au lieu d'un
ratissage. Rien d'autre à faire aujourd'hui.

---

## 8. Tranché, et ce qui reste ouvert

**Tranché** : cible Android ; rendu 3D isométrique ; azimut de caméra fixe ; oracle
hybride accepté, avec l'émulateur pour le niveau 2 (§ 3.1).

**Reste ouvert :**

1. **Téléphone ou tablette ?** Ça décide la place de l'interface, et donc la lisibilité
   d'un RTS. La barre latérale de C&C ne tient pas sur un téléphone (§ 1.5).
2. **Un appareil Android réel est-il disponible** pour l'étape 0 ? L'émulateur est le
   pire environnement pour Flutter GPU, donc un échec là-bas ne conclurait rien.
3. **Nom définitif** — `Crépuscule` est un nom de code.

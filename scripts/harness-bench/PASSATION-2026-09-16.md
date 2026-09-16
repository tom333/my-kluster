# Passation — banc `crepuscule-amorce`, sessions du 14 au 16/09/2026

Pour la session qui reprend les tests de harnais. Tout ce qui suit est mesuré ;
les chiffres viennent des JSON de `results/` et des transcripts à côté.

## 1. La question, et la réponse partielle

Peut-on compenser un petit modèle (**gemma-4-12b-it-qat**, RTX 3060 12 Go, LocalAI
`https://localai.tgu.ovh/v1`) par une surcouche agentique, sur une tâche réelle :
créer depuis une **seule spec** (`fixture-crepuscule-amorce/SPEC.md`, seul point
d'entrée) une application Flutter/Android affichant un cube en projection
isométrique avec `flutter_scene` ?

Une règle tient depuis le début et se confirme à chaque campagne :

> **Ce qui est poussé vers le modèle marche ; ce qu'il doit aller chercher ne marche pas.**
> Et depuis le 15/09 : poussé **sans casser le fil** — l'interruption de flux coûte le contexte.

Le mur est le même partout : un chemin d'import deviné dans `flutter_scene`
(`flutter_scene/flutter_scene.dart` n'existe pas ; le point d'entrée public est
`scene.dart`), puis un modèle qui ne lit pas `Target of URI doesn't exist` quand la
ligne est noyée dans 3 900 caractères de gradle. Seuls les harnais qui **isolent et
collent** le diagnostic au résultat de l'écriture le franchissent.

## 2. Tableau des bras (même fixture, même modèle)

| bras | résultat | ce qui l'a arrêté |
|---|---|---|
| **opencode + `lsp: true` + oh-my-openagent** (14/09) | **3/3 vérifié**, cube isométrique à l'écran | — (référence à battre, mais notée sur **3 étages**, avant les étages de méthode) |
| omp + règles TTSR *ajustées à la fixture* (15/09) | APK en 11 min, import juste | règles qui soufflaient la réponse → bras témoin seulement |
| omp + règles génériques (15/09, 2 campagnes) | 0·2·0 /6 puis 0·0·0 /6 | pas d'outil `lsp` dans le schéma ; LSP intermittent (mux mort) ; `repeatMode: once` ; boucles de raisonnement (2/3) |
| little-coder v1.19 seul (16/09) | 0·0·0 /6 (essai 1 invalide : OOM LocalAI) | même import faux, erreur enfouie dans gradle, 4× la même commande |
| **little-coder + pi-lens** (16/09) | 0·2·0 /6 — essais 1 et 2 **invalides** (503, redéploiements LocalAI) ; essai 3 intact 0/6 | **le mur des imports est tombé** : import juste, convergence 22 → 2 erreurs de type ; puis 4 `dispatch` (~12 min/28), `flutter build` jamais lancé, couperet 1800 s |

Le seul essai intact de little-coder+pi-lens a la meilleure trajectoire de la
semaine : c'est le bras à poursuivre.

## 3. Ce que le banc mesure maintenant (six étages)

`bench.py --scenario crepuscule-amorce --harness <h> --model localai/gemma-4-12b-it-qat --runs 3 --timeout 1800`

Étages (source unique `ETAGES_AMORCE`) : `build` · `lancement` · `rendu` (refuse le
gabarit `flutter create`, refuse l'absence de `flutter_scene`) · `tests` (`flutter
test` vert + un test non gabarit) · `test_dabord` (commit `test/` sans `lib/`, puis
commit `lib/`) · `historique` (≥ 3 commits Conventional Commits). Majorité de 3
essais, médiane. Les seuils sont dans la SPEC §3bis, **pas dans le prompt**.

Le banc pose le dépôt git **avant** l'agent (`_init_depot` : `.git` = marqueur
racine des LSP, GPG coupé localement). Chemins de `git log` relativisés au projet
(l'agent crée souvent un sous-dossier). `stdin=DEVNULL` sur le Popen (pi et ses
dérivés attendent l'EOF d'un stdin-tube — 4 sondes ont pendu pour ça).

**Aucun essai, aucun harnais, n'a encore fait un seul commit.** Les trois étages
de méthode n'ont jamais été approchés.

## 4. Dérives à corriger AVANT toute relance

1. **Contexte serveur = 65 536 depuis le 16/09 11:05** (`0631575a`, ctx gemma
   150000→65536) ; les trois catalogues déclarent encore **131 072** :
   `~/.pi/agent/models.json`, `~/.omp/agent/models.yml`,
   `config-little-coder/models.json` (+ `~/.config/little-coder/models.json`).
   Les pics à 112 k (omp r3, little-coder r3) seront tronqués côté serveur.
2. **Plafond 1800 s saturé** sur les 3 derniers essais (« la durée ne départage
   rien »). Proposé : `--timeout 3600` une fois, pour recalibrer la règle
   « meilleur du jour + 25 % ».
3. **`dispatch`** (sous-codeurs little-coder) : 12 min/28 sur l'essai 3, second
   flux concurrent sur le GPU (suspecté dans l'OOM du matin). Proposé :
   `--exclude-tools dispatch` — réglage, pas transformation.
4. **Pas de déploiement LocalAI pendant une campagne** : deux redéploiements
   ArgoCD (11:24, 11:50) ont invalidé 2 essais sur 3 aujourd'hui.
5. Le banc lit « Thinking loop detected » (détecteur d'omp) comme « le modèle n'a
   pas chargé, essai invalide » — faux, omp ré-échantillonne et l'essai continue.
   À corriger si omp est rejoué.

## 5. Configurations vérifiées, et leurs pièges

- **`config-omp/`** (README détaillé) : pas d'outil `lsp` dans le schéma du
  modèle (11 outils, capturés) ; LSP = diagnostics collés à `write`/`edit`
  uniquement ; `lsp.shared: false` (mux `exited(137)`) ; `ttsr.repeatMode:
  after-gap` ; règles génériques (testées sur 6 langages) ; omp n'envoie **aucun**
  paramètre d'échantillonnage. Conçu pour Grok/Gemini/MiniMax (README amont),
  aucune donnée petit modèle ; #10910 ouvert (TTSR manque des matches selon le
  découpage réseau).
- **`config-little-coder/`** (README détaillé) : registre de modèles **à part**
  (`~/.config/little-coder/models.json`, jamais `~/.pi/agent`) ; `apiKey` nom de
  variable **non résolu** → le banc génère `/tmp/harness-bench-little-coder-models.json`
  (0600) avec la valeur ; 26 outils (34 avec pi-lens), ~6 300 tokens/requête
  (~8 950 avec pi-lens) ; température 0.3 du profil **non** injectée pour
  `localai` ; `LITTLE_CODER_PERMISSION_MODE=accept-all` (a permis un `rm -rf`
  sur `~/.pub-cache/.../flutter_scene-0.20.0`, re-téléchargé depuis) ;
  `--no-update-check`. pi-lens par `LITTLE_CODER_EXTRA_EXTENSIONS=~/.pi/agent/npm/node_modules/pi-lens/dist/index.js`.
- Ne jamais lancer deux patchs en parallèle sur le même fichier (course, vécu).
  Vérifier `git show HEAD:<fichier> | grep` avant toute campagne.

## 6. Candidats non testés, par ordre

1. **little-coder + pi-lens** avec les 4 corrections du §4 — à faire d'abord.
2. **mini-swe-agent** (bash seul, sans schéma d'outil ; Qwen3-Coder-30B 18,8 %
   SWE-bench Verified contre 21,2 % GPT-4o même réglage). Ne pousse rien : mesure
   « supprimer le format d'outil suffit-il ? ».
3. **Cline CLI 2.0 headless + compact prompt** (~10 % du prompt) — sa doc dit
   8B = mono-fichier seulement, 27B fiable ; 12B entre les deux.
4. **Rejouer opencode+omo sur les six étages** pour comparer à armes égales.

## 7. Où sont les choses

- Code : `scripts/harness-bench/bench.py`, tests `test_lanceurs.py` (52 verts),
  fixture `fixture-crepuscule-amorce/SPEC.md`, prompt `PROMPT-crepuscule-amorce.txt`
  (inchangé, 3 exigences).
- Résultats : `results/crepuscule-amorce-*-2026091{5,6}-*.json` + `.transcript`
  par essai (`-r1/-r2/-r3`) + captures `harness-bench-*-r2.png`. Projets archivés
  dans `projets/*.tgz`. Workdirs vivants : `/tmp/harness-bench-crepuscule-amorce-*`.
- Commits de la période : `63aad11d` → `b51e612a` (voir `git log -- scripts/harness-bench`).
- Journaux omp : `~/.omp/logs/omp.2026-09-15.*.log` (TTSR `matched=2 injected=1`
  dans chaque session = une seule interruption par défaut).
- Émulateur : `~/Android/Sdk/emulator/emulator -avd telephone35 -no-snapshot-save
  -no-boot-anim -gpu swiftshader_indirect` ; adb `~/Android/Sdk/platform-tools/adb`.
  **Arrêté** au moment de la passation.
- Mémoire Claude corrigée : `reference_suroutillage_gemma_mesure.md` (« 14 outils
  LSP » et « 10 interruptions » étaient faux), `feedback_pas_de_patchs_paralleles_meme_fichier.md`.

---

## 8. Session du 16/09 après-midi — corrections faites, campagne interrompue

### Corrections du §4, faites

1. **Contexte** : les quatre catalogues déclaraient 131 072 quand le serveur
   servait 65 536. Mais la baisse à 65 536 (11:05) était elle-même un
   **pansement** : la vraie cause du RSS de 24 GB a été trouvée 33 min plus tard
   (`cache_ram:0`, prompt cache hôte de LocalAI 4.3). Le pansement est levé —
   serveur ET catalogues sont à **131 072** (commits `f160c09c`, `17a0b24e`).
   Mesuré après déploiement : **VRAM 10 926 MiB / 12 288, RSS 1,67 GB**.
2. **`--exclude-tools`** : le drapeau n'existait pas, il était seulement
   *proposé*. Implémenté comme drapeau de banc (donc tracé dans `commande`),
   inerte par défaut, 4 tests (commit `3da283de`). Total 56 tests verts.
3. **Timeout** : `--timeout 3600` passé en ligne de commande.
4. **Redéploiement LocalAI** : aucun pendant la campagne (surveillé).

### Vérifié au passage, et qui n'était pas dans la passation

- **`parallel: 4` ne divise PAS le contexte utilisable** : une requête unique a
  consommé **64 914 des 65 536 tokens**. Vérifié, pas déduit.
- **256k (la cible) ne tient pas** : backend seul à 9 187 MiB à 65 536 et
  9 913 MiB à 131 072, soit 11,1 MiB par millier de tokens → 11 365 + 1 013
  (affichage) = **12 378 MiB pour une carte de 12 288**. Il manque ~90 MiB. Les
  deux seules voies : `cache_type_k/v` en `q4_0` (non mesuré), ou retirer
  `mmproj` (645 MiB — mais gemma est le modèle vision de Hermes/OpenWebUI).
- **Entrée fantôme dans `adb`** (`emulator-5568 offline` sans processus qemu) :
  aurait fait échouer `lancement` et `rendu` en donnant l'apparence d'un défaut
  du modèle. Purger `adb kill-server` avant toute campagne.
- **L'étage `build` est SAIN** : il relance lui-même `flutter build apk --debug`
  et exige `code == 0`. Un APK périmé ne peut pas le faire passer — soupçon levé.

### Le mur, confirmé à la source

Aucune des **trois** versions en cache n'expose le point d'entrée deviné :

| version | `lib/*.dart` |
|---|---|
| 0.19.0 | `build_hooks` `fscene` `gpu` `noise` **`scene`** |
| 0.20.0 | + `audio` `physics` |
| 0.23.0 | + `annotations` `kit` |

L'agent écrit `package:flutter_scene/flutter_scene.dart` — inexistant partout.

### Ce que l'essai 1 a montré avant l'arrêt

Campagne interrompue à la demande, en cours de notation de l'essai 1. L'agent
avait produit un APK (14:28) puis réécrit `main.dart` (14:41) **avec l'import
faux**. Donc, avec pi-lens ET le contexte à 131 072, **le mur n'est pas tombé** —
contrairement au seul essai intact du 16/09 matin.

⚠️ **Facteur confondant introduit par cette session** : le contexte est passé de
65 536 à 131 072 juste avant. Or le banc a déjà mesuré 34-41/44 à 49 152 contre
**19/44 à 131 072** (« plus de place lui permet de tourner en rond plus
longtemps »). Avant d'accuser pi-lens ou le harnais, **rejouer à 49 152**.
C'est le premier suspect, et il est de mon fait.

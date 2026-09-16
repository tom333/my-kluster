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

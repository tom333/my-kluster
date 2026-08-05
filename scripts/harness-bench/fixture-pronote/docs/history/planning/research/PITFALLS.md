# Pitfalls Research

**Domain:** Home Assistant custom_component scraping Pronote (French school management) via pronotepy, distributed via HACS — context Nouvelle-Calédonie (UTC+11, calendrier austral, vice-rectorat ac-noumea.nc)
**Researched:** 2026-05-03
**Confidence:** HIGH (most pitfalls grounded in actual issues filed against `delphiki/hass-pronote` and `bain3/pronotepy`, plus official HA developer docs)

---

## Critical Pitfalls

### Pitfall 1: Bannissement IP du serveur école (vice-rectorat / rectorat)

**What goes wrong:**
Le serveur Pronote (côté établissement, pas côté Index Education) suspend l'IP publique de l'instance HA. Symptôme caractéristique : `pronotepy.exceptions.PronoteAPIError: Your IP address is suspended.`. Tant que le bannissement est actif, **toute la famille perd aussi l'accès via navigateur** depuis cette IP, pas seulement l'intégration. Vu en sept 2025 (académie Paris), oct 2025 (Nice, parent + 2 enfants), jan 2026 (Toulouse) sur `delphiki/hass-pronote#128`. Un cas a duré « plusieurs mois » avant déblocage (« j'attendais la nouvelle année »).

**Why it happens:**
- Polling trop fréquent (default `delphiki` était 15 min historiquement)
- Auth qui échoue en boucle (mauvais password ou cookie expiré) → chaque retry = nouvelle tentative loggée côté serveur
- Multi-comptes (1 parent + 2 enfants) = chaque enfant déclenche un login distinct, donc 3 hits par cycle de polling
- Pas de circuit breaker : pronotepy lève une exception, HA retry, ça boucle
- Pic de trafic 17h–20h corrélé avec d'autres familles → l'établissement met une protection anti-bot agressive

**How to avoid:**
- **Default polling 30 min minimum**, jamais en dessous de 15 min, et exposer l'avertissement dans l'UI Config Flow
- **Plage de surveillance 17h–20h limitée** : passer à 15 min uniquement dans cette fenêtre, pas en permanence
- **Pas de polling le week-end / la nuit / pendant les vacances scolaires** (calendrier NC, pas métropole — voir Pitfall 4) : descendre à un poll toutes les 4h ou pause complète
- **Circuit breaker** : si 3 erreurs auth consécutives → arrêter le polling, raise `ConfigEntryAuthFailed` (déclenche reauth UI) au lieu de retry à l'infini
- **Détecter explicitement le message « Your IP address is suspended »** dans l'erreur pronotepy → backoff exponentiel long (1h, 2h, 4h, 12h, 24h, plafond 24h) et notif HA persistante claire à l'utilisateur, pas un retry silencieux
- **Jitter** sur `update_interval` (±30s) pour éviter que toutes les installations HA tapent au même moment
- Documenter dans le README : « si vous avez plusieurs enfants, chacun ajoute une session de login → augmenter l'intervalle proportionnellement »

**Warning signs:**
- Hausse soudaine du nombre d'erreurs `UpdateFailed` dans les logs
- L'utilisateur ne peut plus se connecter à Pronote depuis son navigateur (test manuel) → confirmation IP bannie
- Plusieurs erreurs auth en quelques heures = signal de débordement avant ban complet

**Phase to address:**
Phase coordinator/polling (early). Incontournable au MVP — un ban en démo = projet mort-né.

---

### Pitfall 2: Cassures pronotepy à chaque mise à jour Pronote

**What goes wrong:**
Index Education livre régulièrement de nouvelles versions Pronote (typiquement 1× / an, plus patches en cours d'année). Chaque update peut changer le protocole interne (`Unknown error from pronote: 3`, `Protocol identification problem`, déchiffrement AES qui casse, `La page a expiré ! (1)`). pronotepy ne suit pas toujours immédiatement (`bain3/pronotepy` a des PR ouvertes pendant des semaines avant merge, exemple `#337` ENT IDF, `#341` EduConnect, `#338` CAS, tous open en cours). Pendant ce temps, **tous les utilisateurs HA sont cassés** avec des stack traces incompréhensibles (CryptoError "Padding is incorrect" est typique mais misleading — l'utilisateur croit avoir un mauvais mot de passe).

**Why it happens:**
- pronotepy n'est pas une API officielle, c'est de la rétro-ingénierie
- Pronote utilise du chiffrement AES + obfuscation custom → toute modif côté Index Education casse le client
- Le mainteneur de pronotepy n'est pas payé pour suivre Index Education en temps réel
- Beaucoup d'utilisateurs ne savent pas que `CryptoError "bad username/password"` peut en réalité signifier « pronotepy obsolète » (cf `delphiki#94`, `delphiki#141`)

**How to avoid:**
- **Version range, pas pin strict** dans `manifest.json requirements` : `pronotepy>=2.14.0,<3.0.0` (semver permissif sur les patches)
- **CI quotidienne contre la dernière `pronotepy`** : un workflow GitHub Actions qui réinstalle `pronotepy@latest` et relance les tests détecte les régressions tôt
- **Wrapper de toutes les exceptions pronotepy** dans une exception domaine custom (ex: `PronoteIntegrationError(reason=…)`) avec des reasons typées : `AUTH_FAILED`, `IP_SUSPENDED`, `PROTOCOL_BROKEN`, `SERVER_DOWN`, `SESSION_EXPIRED` → permet à l'utilisateur de comprendre + à HA de prendre la bonne action (reauth vs UpdateFailed vs notif)
- **Détecter les erreurs « protocole cassé »** (PronoteAPIError avec code numérique, ProtocolIdentificationError) et raise UpdateFailed avec un message clair : « Pronote a probablement été mis à jour, attendez la prochaine version de pronotepy » (pas une stack trace)
- **Issue template GitHub** dédié « Pronote update broke the integration » qui demande version Pronote + version pronotepy + log → tri rapide
- **Tests unitaires sur les conversions** Pronote→HA basés sur des fixtures JSON capturées (pas sur des appels réseau) → si pronotepy change le format d'objet retourné, les tests cassent en CI avant prod

**Warning signs:**
- Pic d'issues sur le repo après une release Pronote (typiquement août–septembre métropole, février NC)
- Erreurs `CryptoError`, `PronoteAPIError code N`, `ProtocolIdentificationError` dans les logs
- Les tests unitaires passent mais l'intégration plante en prod = c'est pronotepy ou Pronote, pas notre code

**Phase to address:**
Phase architecture (wrapper exceptions) puis CI (workflow quotidien). À traiter avant le ship public.

---

### Pitfall 3: Blocking calls dans l'event loop HA (pronotepy est synchrone)

**What goes wrong:**
pronotepy est entièrement synchrone (basé sur `requests`). Appeler `client.lessons(...)` directement dans le coordinator async bloque l'event loop HA pendant des secondes → tout HA freeze (lights, automatisations, UI). HA détecte et logge `Detected blocking call to open inside the event loop`. Cas réel sur `delphiki#85` : `pytz.timezone(self.hass.config.time_zone)` lit un fichier zoneinfo → blocking call. Aussi vu : `requests` lui-même fait des DNS sync, `cryptography` charge des fichiers de cert.

**Why it happens:**
- Confusion entre « DataUpdateCoordinator est async » et « tout ce qui est dedans peut être sync »
- Le dev importe `pronotepy` et l'appelle directement dans `_async_update_data` sans réflexion
- Même les libs « auxiliaires » (pytz, requests pour DNS) cachent du blocking I/O
- En dev local on ne voit pas le freeze (peu d'entités, peu d'automatisations) ; en prod chez l'utilisateur c'est visible

**How to avoid:**
- **TOUS les appels pronotepy** doivent passer par `await hass.async_add_executor_job(sync_func, *args)`
- Idem pour la création du client : `client = await hass.async_add_executor_job(_blocking_create_client, url, user, pwd)`
- **Préférer `zoneinfo` (stdlib Python 3.9+) à `pytz`** : `zoneinfo` est non-blocking depuis 3.11+ et c'est ce que recommande HA. `pytz` est déprécié et a explicitement le bug du `delphiki#85`
- **Utiliser `dt_util.now(hass.config.time_zone)` ou `dt_util.as_local()`** depuis `homeassistant.util.dt` au lieu de manipuler les timezones soi-même
- **Test CI avec `pytest-homeassistant-custom-component`** qui détecte les blocking calls comme HA le fait en prod (variable d'env `BLOCKING_CALL_LOG_LEVEL`)
- **Code review checklist** : « toute import de `requests`, `urllib`, `pronotepy`, `pytz`, `open()` doit être justifié dans un executor »

**Warning signs:**
- Logs HA `homeassistant.util.loop` : `Detected blocking call to ...`
- Utilisateurs qui rapportent « HA freeze pendant 5s toutes les 30 min »
- Latence variable des automatisations corrélée avec le polling Pronote

**Phase to address:**
Phase coordinator (foundational). Doit être correct au tout premier prototype, sinon refactor coûteux après.

---

### Pitfall 4: Timezone Nouvelle-Calédonie + calendrier scolaire austral

**What goes wrong:**
La Nouvelle-Calédonie est UTC+11 (sans DST), le serveur Pronote vice-rectorat retourne des dates en heure locale NC, mais l'instance HA peut tourner sur n'importe quel timezone (cloud, VPS Europe, voyage…). Pire : le **calendrier scolaire est inversé** — rentrée mi-février, fin décembre, vacances en pleine été métropole. Si on hardcode des heures « 17h–20h surveillance EDT lendemain » et qu'on utilise `datetime.now()` (naïf) ou `dt_util.utcnow()` sans conversion, on surveille au mauvais moment. Résultat : on rate les changements d'EDT (la valeur core du produit) ou on pète des notifs « EDT changé » à 3h du matin NC quand le serveur est en train de se réveiller en métropole.

**Why it happens:**
- HA stocke tout en UTC (volontairement) — `dt_util.utcnow()` ≠ `datetime.now()` (naïf, déprécié)
- Confusion entre `now()` (HA, tz-aware, locale HA) et `dt_util.now()` (HA, tz-aware, locale HA) et `datetime.now()` (Python, naïf)
- pronotepy retourne des `datetime` naïfs (heure locale Pronote serveur, donc heure NC pour `ac-noumea.nc`) → comparer à `dt_util.utcnow()` lève `TypeError: can't compare offset-naive and offset-aware`
- Hardcoder les vacances scolaires métropole (zones A/B/C) au lieu du calendrier vice-rectorat NC
- L'auteur dev en NC, l'utilisateur potentiel HACS aussi en NC → angle mort sur le test métropole et inversement

**How to avoid:**
- **Toujours `dt_util.now()` ou `dt_util.utcnow()`** depuis `homeassistant.util.dt`, jamais `datetime.now()` directement
- **Localiser explicitement les datetimes pronotepy** : `naive_dt.replace(tzinfo=ZoneInfo(school_tz))` où `school_tz` est **un paramètre de config** (default Pacific/Noumea pour ce projet, mais paramétrable pour préparer un futur usage métropole)
- **Pas de hardcode de la fenêtre 17h–20h** : exprimer comme `time(17,0)`–`time(20,0)` dans le timezone de l'école (config), pas du serveur HA
- **Calendrier vacances : récupérer dynamiquement** via le calendrier vice-rectorat NC (`https://denc.gouv.nc/calendrier-scolaire` ou `ac-noumea.nc`) ou hardcode initial v1 + plan de migration vers ICS si possible. NE PAS utiliser les zones métropole.
- **Test unitaire avec instance HA en `Europe/Paris` ET en `Pacific/Noumea`** : forcer `hass.config.time_zone` dans les fixtures pytest pour garantir que les calculs marchent sur les deux
- **Quiet hours par défaut** (pas de notif EDT changé entre 22h et 6h NC) : utile aussi pour cas Pitfall 9
- Sentinel test : si une date pronotepy retournée par le serveur a un offset > 24h vs `dt_util.now()`, c'est un bug de localisation → log warning au lieu de crash

**Warning signs:**
- Notif « EDT changé pour aujourd'hui » qui arrive à 23h ou 3h du matin
- Sensor `next_lesson` qui affiche « dans 14h » au lieu de « dans 1h »
- `TypeError: can't compare offset-naive and offset-aware datetimes` dans les logs
- Polling adaptatif qui s'enclenche au mauvais moment (par exemple : polling intensif pendant les vacances scolaires NC)

**Phase to address:**
Phase modèle de données + phase polling adaptatif. À traiter dès le tout premier sensor (sinon dette systémique).

---

### Pitfall 5: Sessions Pronote concurrentes — kill du parent qui consulte

**What goes wrong:**
Pronote (côté Index Education) limite le nombre de sessions simultanées par compte. Quand HA fait un nouveau login pendant que le parent regarde les notes sur son téléphone, **la session du parent saute** : il est éjecté de l'app Pronote. Inversement, si le parent se logue manuellement, la session HA peut être tuée → erreur d'auth → retry → boucle (cf Pitfall 1 = ban). Particulièrement vicieux avec les comptes parent qui ont plusieurs enfants : chaque ParentClient.set_child(...) peut ré-initialiser certaines parties de la session côté serveur.

**Why it happens:**
- pronotepy fait un `client_identifier` aléatoire ou par défaut → Pronote considère ça comme « nouveau device » à chaque login
- Le `device_name` n'est pas paramétrable / pas stable d'un redémarrage HA à l'autre dans certaines impls
- Pas d'utilisation cohérente de `client.export_credentials()` / `token_login` pour réutiliser un token au lieu de re-login systématique
- Bug `delphiki#155` : divergence `uuid` vs `qr_code_uuid` → token invalide après restart → re-login → kill session parent

**How to avoid:**
- **Toujours utiliser la persistance de session** : sauvegarder `client.export_credentials()` après chaque update réussi dans `config_entry.data`, et réutiliser au login suivant via `Client(..., uuid=stored_uuid)` — évite un fresh login à chaque redémarrage HA
- **`device_name` stable et identifiable** : `f"home-assistant-{config_entry.entry_id[:8]}"` → l'utilisateur voit dans l'app Pronote « device home-assistant-xxxx » dans la liste des appareils, peut le révoquer s'il veut
- **Synchroniser `qr_code_uuid` avec `uuid` rafraîchi** (fix `delphiki#155`) : un seul champ canonique pour l'UUID de session
- **Recommander dans la doc** d'utiliser un compte parent dédié à HA si possible (compte d'origine pour la consultation, compte secondaire pour HA), ou au minimum prévenir l'utilisateur qu'il sera occasionnellement éjecté
- **Backoff long sur les erreurs `Session expirée` / `La page a expiré !`** : ne pas tenter immédiatement un nouveau login (ça aggrave le kill mutuel), attendre le prochain cycle normal

**Warning signs:**
- Le parent rapporte « je suis souvent éjecté de l'app Pronote depuis que j'ai installé HA »
- Erreurs `PronoteAPIError: 8 | La page a expiré !` qui se multiplient (cf `bain3/pronotepy#309`)
- Pic d'erreurs auth sans changement de mot de passe

**Phase to address:**
Phase auth (session persistence) — peut attendre un premier prototype mais doit être en place avant tout ship public.

---

### Pitfall 6: Stockage credentials en clair dans `.storage/core.config_entries`

**What goes wrong:**
HA stocke les `config_entry.data` en JSON brut dans `~/.homeassistant/.storage/core.config_entries`. Si le user fait un backup non chiffré, partage ses logs avec un mainteneur HA pour debug, ou que son host est compromis, le mot de passe Pronote fuit en clair. C'est un sujet ouvert dans la communauté HA (cf WTH 2025 : « pourquoi les passwords sont en clair dans config_entries »). Pour Pronote c'est sensible : c'est le compte parent, qui donne accès à des données personnelles d'enfants mineurs.

**Why it happens:**
- HA n'a pas (encore) de secret store native pour les intégrations
- Les devs supposent que `.storage` est sûr (« c'est local ») et n'avertissent pas l'utilisateur
- Les credentials sont aussi loggés involontairement (URL Pronote contient parfois des tokens, debug logs verbeux)

**How to avoid:**
- **Préférer le QR code login** (token-based) à username/password quand possible : le token est révocable depuis l'app Pronote et n'expose pas le password. Faire du QR code la méthode recommandée et de username/password un fallback documenté
- **Ne jamais logger** le password, l'URL complète avec token, le `client_identifier`, le token de session. Utiliser un filtre logger personnalisé (regex) + redaction dans le module
- **Implémenter `async_get_config_entry_diagnostics`** (HA diagnostics platform) avec `async_redact_data(data, TO_REDACT)` où `TO_REDACT = {"password", "username", "uuid", "qr_code_uuid", "token", "url"}` → tout snapshot de diagnostic est PII-safe par défaut
- **Documenter explicitement** dans le README : « les credentials Pronote sont stockés en clair dans `.storage` ; sauvegardez de manière chiffrée, ne partagez pas ce dossier ». Pas de sécurité par obscurité, mais transparence
- **Validation au config_flow** : connexion réussie obligatoire avant d'enregistrer → si le user se trompe de mot de passe, on n'enregistre pas le mauvais password (réduit la surface)

**Warning signs:**
- Mot de passe ou token visible dans les logs HA en niveau DEBUG
- Issues GitHub où l'utilisateur copie-colle des logs et révèle son password
- Backup HA non chiffré contenant des `.storage/core.config_entries`

**Phase to address:**
Phase auth + phase diagnostics. Le redaction des logs doit être en place dès le premier login fonctionnel.

---

### Pitfall 7: Attributs sensor trop volumineux (>16 KB) ou state >255 chars

**What goes wrong:**
HA a deux limites strictes :
1. **`state` doit être < 255 caractères** sinon devient `unknown` avec warning. Bug réel `delphiki#157` : un dev a accidentellement assigné `self._attr_native_value = list_of_grade_objects` au lieu de `len(...)` → state = repr de 50 objets `<pronotepy.dataClasses.Grade object at 0x...>` → 4000+ chars → `falling back to unknown`.
2. **State attributes doivent être < 16384 bytes** sinon recorder skip le store et logge `State attributes ... exceed maximum size of 16384 bytes` (cf `delphiki#136` sur le sensor timetable qui contient toute la semaine).

L'EDT d'un trimestre + détails (matière, prof, salle, groupe, statut, EDT modifications) peut facilement exploser ces limites avec 50+ leçons par semaine × 5 attributs chacune.

**Why it happens:**
- Tentation de fournir « tout dans les attributs » pour que le user puisse construire ses cartes Lovelace
- Pronote retourne des objets riches → on les passe tels quels sans aplatir / filtrer
- Pas de tests sur des fixtures « grosse classe » (50 leçons / semaine) avant ship

**How to avoid:**
- **State sensor = nombre / scalaire / identifiant court**, jamais un objet ou une liste. `state = len(today_lessons)` ou `state = next_lesson.subject` (tronqué si nécessaire)
- **Attributs : split par jour ou par période**, pas tout en un
  - sensor `timetable_today` : attributs = leçons du jour seulement
  - sensor `timetable_tomorrow` : leçons J+1
  - sensor `next_lesson` : 1 leçon
  - **PAS** un sensor `timetable_week` avec 50 leçons en attributs
- **Aplatir et filtrer** : ne garder que les champs utiles à l'UI / aux automatisations (`subject`, `teacher`, `room`, `start`, `end`, `canceled`, `modified`), pas tout l'objet pronotepy
- **Tests avec fixture classe chargée** (50+ leçons/semaine) → si on dépasse 16KB, ça doit casser les tests
- **`@property` sur les attributs avec calcul à la demande**, pas matérialisation en mémoire systématique
- Pour les notes : un sensor par période (trimestre/semestre) avec **les N dernières notes** (ex: 20), pas toute l'année

**Warning signs:**
- Logs `State ... is longer than 255, falling back to unknown`
- Logs `State attributes for sensor.X exceed maximum size of 16384 bytes`
- Sensor qui passe en `unknown` après quelques mois (fin de trimestre = beaucoup de notes accumulées)
- DB recorder qui grossit anormalement vite

**Phase to address:**
Phase entities/sensors design. Doit être testé dès la première implémentation de sensor.

---

### Pitfall 8: `unique_id` instable → entités dupliquées après update

**What goes wrong:**
Si le `unique_id` d'une entité change entre deux versions de l'intégration (par exemple : on inclut le nom de l'enfant dans l'ID, et le user corrige une faute de frappe ; ou on change le format `f"{entry_id}_{kid}_grades"` → `f"pronote_{kid_id}_grades"`), HA crée de nouvelles entités au lieu de réutiliser les anciennes. Résultat : `sensor.pronote_marie_grades` orphan + `sensor.pronote_marie_grades_2` actif. Toutes les automatisations / cartes Lovelace cassent silencieusement.

**Why it happens:**
- Refactor sans réflexion sur les unique_id existants
- Inclusion d'éléments mutables dans l'unique_id (nom utilisateur, URL serveur qui peut changer si l'établissement migre)
- Comptes parent : ID de l'enfant (`pronotepy.Child.identifier`) peut sembler stable mais en pratique change avec certaines mises à jour Pronote
- Pas de tests sur le scénario « j'avais la v1 installée, je passe à la v2 »

**How to avoid:**
- **`unique_id = f"{config_entry.entry_id}_{stable_child_key}_{sensor_kind}"`** : `entry_id` est garanti unique et stable par HA, `stable_child_key` doit être l'`identifier` Pronote (numérique côté serveur, pas le nom)
- **Documenter le format unique_id** dans le code en commentaire : « si tu changes ce format, tu dois écrire une migration `async_migrate_entry` »
- **Implémenter `async_migrate_entry`** dès qu'on change le format : énumérer les anciennes entités, les renommer via `entity_registry.async_update_entity(entity_id, new_unique_id=...)`
- **Test d'intégration upgrade** : un test pytest qui charge une `config_entry` au format v1, lance la migration, vérifie que les entités sont bien renommées
- **Utiliser `DeviceInfo` avec `identifiers={(DOMAIN, child.identifier)}`** pour grouper les sensors par enfant → si on doit re-créer les entities, au moins le device reste

**Warning signs:**
- Après update HACS : entités `_2`, `_3` qui apparaissent
- Cartes Lovelace qui affichent « Entity not available »
- Issues GitHub « mes automatisations ne marchent plus depuis la v2 »

**Phase to address:**
Phase entities (foundational). Le format unique_id doit être figé et réfléchi avant le premier release HACS.

---

### Pitfall 9: Notifications EDT changé à 3h du matin

**What goes wrong:**
La détection de changement d'EDT déclenche un événement HA `pronote_schedule_changed`. Si l'utilisateur l'a câblé à une notif mobile, et que le serveur Pronote re-render le layout pour une raison technique (faux positif Pitfall 10), ou qu'on poll en pleine nuit pendant les vacances, **toute la maison reçoit une notif à 3h du matin** « cours de maths annulé » alors que c'est juste un re-render et qu'on n'est même pas en période scolaire.

**Why it happens:**
- Pas de quiet hours sur le polling ni sur les events
- Le polling continue 24/7 même quand il n'y a pas d'enjeu
- Pas de filtrage : tout changement détecté → event émis → notif tirée
- Pendant les vacances, le serveur Pronote met parfois à jour des trucs (paramètres, profs, salles assignées au prochain trimestre) → faux positifs

**How to avoid:**
- **Quiet hours configurables, default 22h–6h** (timezone école NC) : pas de polling actif (passage à 4h d'intervalle minimum), pas d'émission d'event de type « EDT changé »
- **Pas de polling le week-end** (samedi 18h → lundi 6h) : les modifs d'EDT du lundi sont publiées le dimanche soir au plus tôt → un poll dimanche 18h suffit
- **Pas de polling pendant les vacances scolaires NC** : pause complète ou un poll par jour seulement
- **Détection d'EDT pertinente uniquement pour J et J+1** (pas J+7) → ne pas notifier sur des changements lointains
- **Filter d'événements** : si la notif a déjà été émise pour ce changement (basé sur un hash du payload), ne pas re-émettre
- **Recommander dans la doc une `automation` HA exemple** avec `trigger: pronote_schedule_changed` ET `condition: time` ET `condition: not in vacation` → l'utilisateur copie-colle, pas de mauvaise surprise

**Warning signs:**
- Issue GitHub « j'ai été réveillé à 3h du matin »
- Logs montrant des events émis à des heures aberrantes
- Famille qui désactive l'intégration parce que c'est devenu invivable

**Phase to address:**
Phase polling adaptatif + phase events. Doit être réfléchi avant ship public — le risque réputationnel d'une notif à 3h est élevé.

---

### Pitfall 10: Détection changements EDT — faux positifs / faux négatifs

**What goes wrong:**
Comparer naïvement deux snapshots EDT (poll N vs poll N+1) génère des faux positifs (la salle a un espace en moins, l'objet pronotepy a un champ interne différent, l'ordre des leçons a changé) ET des faux négatifs (un cours annulé peut générer DEUX leçons côté pronotepy : l'ancienne `canceled=True` + la nouvelle `Changement de salle` `canceled=False` — cf `bain3/pronotepy#311`). Le user reçoit soit du spam, soit rate l'info importante.

**Why it happens:**
- Diff naïf via `==` sur des objets pronotepy (qui peuvent avoir un repr instable, des memory addresses)
- Pronote distingue mal « cours annulé » (G=0) de « cours annulé pour cause de changement de salle » (G=3) — il faut le champ `G` brut
- Mêmes leçons retournées dans un ordre différent d'un poll à l'autre → diff dit « tout a changé »
- Re-render Pronote (côté serveur) modifie des champs internes (timestamp updated_at, ID interne) sans changement réel pour l'utilisateur

**How to avoid:**
- **Définir une « clé d'identité » stable d'une leçon** : `(date, start_time, end_time, subject, teacher_initial)` → permet de matcher la même leçon entre deux polls même si l'ordre change
- **Définir une « clé de contenu » sémantique** : `(canceled, status, classroom, modified)` (pas l'objet entier) → diff porte uniquement sur ce qui intéresse l'utilisateur
- **Gérer le cas room change** explicitement : si on a une leçon canceled=True ET une autre leçon `Changement de salle` au même créneau (même date/heure/matière), c'est un room change, pas une annulation. Émettre un event `room_changed` distinct, pas `cancelled`.
- **Tests unitaires sur fixtures de transition** :
  - poll1 = leçon normale, poll2 = leçon canceled → event `cancelled` émis 1×
  - poll1 = leçon normale, poll2 = leçon avec nouvelle salle → event `room_changed` émis 1×
  - poll1 = leçon normale, poll2 = même leçon (random reorder) → AUCUN event
  - poll1 vide, poll2 vide → AUCUN event (vacances)
- **Hash le payload de l'event** et garder en mémoire les N derniers hash → ne pas ré-émettre le même event en boucle

**Warning signs:**
- Notifs « EDT changé » qui arrivent en rafale à chaque poll
- Tests unitaires absents sur les transitions EDT
- Aucune issue rapportée mais user désactive silencieusement la feature

**Phase to address:**
Phase « EDT change detection » (cœur de la valeur produit). Doit avoir une couverture de tests forte avant ship.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Pin pronotepy à une version exacte (`pronotepy==2.14.2`) | Reproductibilité, pas de surprise | Quand pronotepy update pour fixer une cassure Pronote, l'user reste cassé jusqu'à ta release. Couplage fort. | Jamais — préférer range `>=2.14,<3.0` + CI quotidienne contre `latest` |
| Logger les payloads pronotepy en DEBUG sans redaction | Debug rapide | Credentials et données enfant fuient dans les issues GitHub copiées-collées | Jamais — toujours redacter, même en DEBUG |
| Mocker pronotepy à 100% sans tester les conversions de format | Tests rapides | Quand pronotepy change de format de retour, tests passent mais prod casse | Jamais — capturer des fixtures JSON réelles et tester le round-trip Pronote→HA |
| Polling fixe 5–15 min par défaut | Fraîcheur des données | Risque ban IP, kill session parent, drainage CPU | Jamais en default — laisser min 30 min, opt-in pour 15 min via UI avec warning |
| Stocker password en clair sans warning utilisateur | Implementation simple | Fuite via backups non chiffrés / logs partagés | Acceptable v1 si README documente clairement + diagnostics redact correctement |
| Hardcoder timezone Pacific/Noumea | Pas de bug pour mon cas perso | Personne d'autre que NC peut utiliser → barrière à l'adoption HACS | Acceptable v1 si exposé en config flow plus tard. NE jamais retirer le paramètre une fois introduit. |
| Polling 24/7 sans logique vacances/week-end en MVP | Code plus simple | Ban IP probable, notifs nuit, drainage | Acceptable seulement avec polling >= 60 min en MVP, à corriger v1.1 |
| Pas de `async_migrate_entry` au début | Pas de surcharge MVP | Premier refactor d'unique_id casse toutes les automations users → réputation HACS | Acceptable v0.x (alpha) avec disclaimer breaking changes ; jamais à partir du premier ship public stable |
| Pas de support reauth flow | Implementation Config Flow plus simple | User doit supprimer + recréer l'entry → entités neuves → automations cassées (cf `delphiki#133`) | Jamais — reauth flow est table stake HA depuis 2022 |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| pronotepy auth | Re-login à chaque cycle de polling (auth coûteuse + risque kill session) | `client.export_credentials()` après login OK, persister dans `config_entry.data`, réutiliser avec `Client(uuid=stored_uuid)`. Re-login uniquement sur erreur explicite. |
| pronotepy ParentClient | Itérer sur `client.children` à chaque poll en faisant `set_child` séquentiel | Utiliser un coordinator HA séparé par enfant si possible, ou batcher les `set_child` avec un seul login parent. Surtout : ne pas faire de fresh login parent par enfant. |
| pronotepy lessons | Récupérer `client.lessons(start, end)` avec une période trop large (mois entier) | Périodes courtes : J et J+1 séparés, J+7 max pour la vue semaine. Réduit la charge serveur, réduit le risque ban. |
| pronotepy notes | Polling notes à 30 min (les notes changent rarement) | Découpler : polling EDT à 30 min, polling notes à 6h ou 12h. Économise massivement les requêtes. |
| HA DataUpdateCoordinator | `update_interval` fixe sans `update_method` async | `update_method` doit être `async def` qui appelle `await hass.async_add_executor_job(sync_pronotepy_call)`. Jamais bloquant. |
| HA Config Flow | Validation du password via un `validate_input` qui appelle `pronotepy` sync | `validate_input` async + executor_job pour pronotepy. Sinon le formulaire UI freeze HA. |
| HA entity_registry | Ne pas implémenter `available` property → entités toujours « disponibles » même quand l'API est down | `@property def available` qui retourne `self.coordinator.last_update_success` |
| HA recorder | Mettre des timestamps tz-naive ou des objets non-sérialisables en attributs → pollution DB ou crash recorder | Toujours retourner des `datetime` tz-aware ou ISO 8601 strings. Tester avec recorder enabled. |
| HACS hacs.json | Oublier `name` (seul champ vraiment requis), confondre avec manifest.json | `hacs.json` minimal : `{"name": "Pronote", "country": "FR", "homeassistant": "2024.4.0"}`. Pas de `domains` (c'est une intégration unique). |
| HACS manifest.json | Clés non triées → hassfest fail | Ordre exigé : `domain`, `name`, puis tout en alphabétique. Linter `hassfest` en CI. |
| HACS manifest.json | `requirements` avec espaces, formats git non-standard | Format strict : `pronotepy>=2.14.0,<3.0.0`. Pour une dep git : `package@git+https://github.com/x/y.git@branch` sans espace |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling intervalle trop court | Logs `Your IP address is suspended`, kill sessions parents | Default >= 30 min, jitter ±30s, polling adaptatif (Pitfall 1) | Souvent dès le 2e jour si polling < 15 min, surtout 17h–20h |
| Attributs sensor trop gros | `state attributes exceed 16384 bytes`, recorder DB qui gonfle | Split par jour/période, aplatir les objets, garder <50 items par liste | Au fil des trimestres : à T1 OK, à T3 sensor explose (plus de notes accumulées) |
| Memory leak sur client pronotepy | RAM HA qui grimpe d'1 GB par semaine, OOM kills | Forcer `client = None` après chaque cycle, ou réutiliser un client persistant cohérent (cf `delphiki#151`). Tests longue durée. | À partir de quelques jours/semaines de uptime continu |
| `pytz` dans le coordinator | Blocking calls, freeze HA | Migrer vers `zoneinfo` (stdlib) | Dès le premier appel, mais le warning est silencieux pour beaucoup de users |
| Pas de `always_update=False` | Recorder écrit à chaque poll même quand rien n'a changé → gonflement DB | Définir `__eq__` sur les structures de données et passer `always_update=False` au coordinator | Après quelques mois : DB de plusieurs GB juste pour Pronote |
| Mock test rapide vs prod réel | Tests passent en CI, casse en prod | Fixtures JSON capturées d'un vrai serveur Pronote (anonymisées), tester le parsing / la conversion | À chaque release Pronote |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logger le password Pronote ou l'URL avec token | Fuite credentials via logs partagés en issue GitHub | Filtre logger custom (regex sur `password=`, `token=`, `uuid=`) ; tests unitaires qui capturent stdout et asserent absence des secrets |
| Stocker password en clair dans `.storage/core.config_entries` sans avertissement | Backup non chiffré → fuite | Documenter dans README, redacter dans diagnostics, recommander QR code |
| Diagnostics platform sans redaction | Snapshot de debug → tout fuit | `async_redact_data(data, TO_REDACT={"password","username","uuid","qr_code_uuid","token","url","ent_url","client_identifier"})` |
| Token QR code persistant sans rotation | Si le token fuit, accès permanent au compte | Documenter la révocation possible via app Pronote ; warning si le token a >12 mois |
| URL Pronote contient le nom de l'établissement (ac-noumea.nc) → identifie l'enfant | Issue GitHub publique avec URL → identification possible | Redacter aussi l'URL dans diagnostics, recommander de masquer dans les issues |
| Pas de validation du certificat TLS de Pronote | MITM possible sur réseau hostile (école wifi) | pronotepy utilise `requests` qui valide TLS par défaut → ne pas désactiver `verify=False`, jamais |
| Aucune limite sur les tentatives de login (au config_flow) | Brute force ou auto-bannissement | Limite implicite via UI (l'utilisateur tape à la main), mais détecter `IP suspended` et arrêter immédiatement le flow avec message clair |
| Exposition d'attributs personnels mineurs (notes, absences) à toute la UI HA | Concierge / invité voit les données de l'enfant | Documenter le RBAC HA, recommander une catégorie d'utilisateurs limitée pour la dashboard scolaire |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Stack trace `CryptoError: Padding is incorrect` quand pronotepy est obsolète | User croit que son mot de passe est faux, change de password partout, finit par s'auto-bannir | Wrapper l'exception avec un message clair : « Pronote a probablement été mis à jour côté serveur. Attendez la prochaine version de pronotepy avant de réessayer. » |
| Erreur d'auth → Config Entry en état failed permanent → l'utilisateur ne sait pas quoi faire | Frustration, désinstallation | Implémenter `ConfigEntryAuthFailed` → HA déclenche automatiquement le reauth flow UI |
| Reauth flow qui demande de tout re-saisir (URL, type compte, etc.) | UX cassée si seul le password a changé | Reauth flow demande UNIQUEMENT le nouveau password (le reste est déjà en config_entry.data) |
| Notif EDT changé sans contexte | « Votre EDT a changé » → quoi ? quand ? quel cours ? | Payload event riche : `{date, lesson_subject, change_type: cancelled|moved|teacher_changed, before, after}` → automation peut composer un message lisible |
| Sensor `next_lesson` qui montre un cours dans 14h pendant le week-end | User pense que HA est cassé | Quand pas de cours dans les prochaines 24h, state = `unknown` ou `none` (pas un cours du lundi affiché le samedi soir) |
| Polling visible côté UI de Pronote (l'utilisateur voit l'app HA dans la liste des appareils) | Confusion, sentiment d'intrusion | `device_name` clair et reconnaissable : `home-assistant-<short-id>` |
| Pas de message clair quand IP suspended | User panique, pense que le serveur école est down, contacte la vie scolaire | Message explicite : « IP suspendue par le serveur Pronote. Cela arrive si trop de requêtes en peu de temps. Patientez 24h avant de réessayer. Augmentez votre intervalle de polling. » |
| Multi-comptes dans un seul config_entry vs un par enfant | Si un enfant casse, tous cassent (cf `delphiki#133`) | Préférer un config_entry par enfant si compte parent → isolation des pannes |
| Trop de sensors par défaut | Dashboard scolaire surchargée | Sensors essentiels actifs par défaut (next_lesson, today_count, average), avancés (toutes les notes) opt-in via options flow |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auth & login :** Souvent oublié — gestion `ConfigEntryAuthFailed` qui déclenche reauth flow, persistance du UUID, détection explicite « IP suspended »
- [ ] **Polling :** Souvent manquant — quiet hours nuit, pause week-end, pause vacances scolaires NC, jitter, circuit breaker après N échecs
- [ ] **Sensor state :** Souvent un objet/liste au lieu d'un scalaire — vérifier `len(state) <= 255` et `len(json.dumps(attributes)) <= 16384` dans les tests
- [ ] **unique_id :** Souvent inclut des champs mutables — vérifier que `entry_id + child.identifier` est utilisé, pas le nom
- [ ] **Timezone :** Souvent oublié pour NC — vérifier que les tests tournent avec `hass.config.time_zone="Europe/Paris"` ET `"Pacific/Noumea"`
- [ ] **Diagnostics :** Souvent absent — `async_get_config_entry_diagnostics` avec redaction est nécessaire pour debug propre
- [ ] **Reauth flow :** Souvent absent — sans ça, changement de password = supprimer + recréer + perdre toutes les automations
- [ ] **Migration entry :** Souvent absent — `async_migrate_entry` doit être implémenté dès le premier changement de schéma
- [ ] **Tests upgrade :** Souvent absent — fixture v1 + migration + assert entités préservées
- [ ] **Logger redaction :** Souvent absent — vérifier que `password`, `token`, `uuid` ne sortent jamais dans les logs même en DEBUG
- [ ] **EDT change detection :** Souvent naïf (==) — fixture poll1/poll2 avec room change, cancellation, no-op, reorder ; assert events corrects
- [ ] **Vacances scolaires :** Souvent métropole hardcodé — vérifier que c'est calendrier NC qui est utilisé
- [ ] **Hassfest CI :** Souvent absent — workflow `home-assistant/actions/hassfest@master` doit passer, idem `hacs/action`
- [ ] **CI sur pronotepy@latest :** Souvent absent — workflow quotidien qui réinstalle `pronotepy` from main, prévient les régressions
- [ ] **Memory leak test :** Souvent absent — test long-running 24h en CI ou local, mesurer la RAM
- [ ] **README politesse polling :** Souvent absent — section explicite « pourquoi 30 min minimum, risque de bannissement, conseils multi-enfants »

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| IP bannie par Pronote serveur | HIGH (24h–plusieurs mois) | 1) Désactiver l'intégration immédiatement. 2) Tester depuis un navigateur — si ban confirmé, attendre 24h. 3) Si ban persiste, contacter vie scolaire de l'établissement. 4) Augmenter `update_interval` à 60 min et désactiver enfants secondaires temporairement. |
| pronotepy cassé après update Pronote | MEDIUM (jours–semaines) | 1) Pas de fix possible côté intégration : attendre PR/release `bain3/pronotepy`. 2) Communiquer dans une issue épinglée du repo. 3) Si urgent, fork pronotepy + patch + override `requirements`. |
| Entités dupliquées après update HACS | MEDIUM (manuel par user) | 1) Implémenter `async_migrate_entry` pour les entités future-proof. 2) Pour les users déjà cassés : doc step-by-step pour delete + recreate, accepter perte d'automations. |
| State attributes >16KB → recorder warning | LOW | 1) Restructurer le sensor pour split par jour/période. 2) Release patch. 3) Pas de migration nécessaire (les anciens warnings disparaissent). |
| Memory leak | MEDIUM (redémarrer HA en attendant fix) | 1) Workaround : recommander redémarrage HA hebdomadaire. 2) Identifier la fuite (snapshot tracemalloc). 3) Forcer `client = None` + GC explicite (cf `delphiki#151`). |
| Faux positifs « EDT changé » → spam notifs | LOW–MEDIUM (réputationnel) | 1) Désactiver les events temporairement (option flow). 2) Améliorer la logique de diff. 3) Ajouter quiet hours et déduplication par hash. |
| Password en clair fuité via logs | HIGH (sécurité) | 1) Demander immédiatement au user de changer son password Pronote. 2) Patcher le logger pour redacter. 3) Audit de tout le code pour autres fuites. |
| Session parent constamment kickée | LOW–MEDIUM | 1) Persister UUID + token entre redémarrages. 2) `device_name` stable. 3) Recommander compte HA dédié. |
| Notif à 3h du matin | LOW (single user) | 1) Quiet hours par défaut. 2) Communication / patch rapide. |
| `IP suspended` non détecté → boucle de retry → ban prolongé | HIGH | 1) Détecter le message d'erreur explicite. 2) Backoff exponentiel long (1h–24h). 3) Notif persistante claire à l'utilisateur. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| #1 Bannissement IP | Phase polling/coordinator (early, MVP) | Test : forcer `IP suspended` exception → assert backoff long + notif user. Valider default 30 min en config flow. |
| #2 Cassures pronotepy | Phase architecture (wrapper exceptions) + CI workflow quotidien | Test : injection `PronoteAPIError(code=N)` → assert wrapped en `PronoteIntegrationError(reason=PROTOCOL_BROKEN)`. CI : workflow `pronotepy@main` qui tourne quotidiennement. |
| #3 Blocking calls event loop | Phase coordinator (foundational) | CI : `pytest-homeassistant-custom-component` avec `BLOCKING_CALL_LOG_LEVEL=ERROR` ; tout pronotepy call wrapped dans `async_add_executor_job`. |
| #4 Timezone NC + calendrier | Phase modèle de données + phase polling adaptatif | Tests pytest paramétrés sur `Europe/Paris` ET `Pacific/Noumea` ; calendrier vacances NC (pas zones métropole). |
| #5 Sessions concurrentes | Phase auth (avant ship public) | Persistance UUID via `export_credentials()` ; `device_name` stable ; test redémarrage HA = 1 seul login total, pas N. |
| #6 Credentials en clair | Phase auth + phase diagnostics | Diagnostics platform avec `async_redact_data` ; logger filter ; tests asserent absence credentials dans stdout/diagnostics. |
| #7 State trop gros | Phase entities/sensors (foundational) | Test fixture « grosse classe » (50 leçons, 100 notes) ; assert `len(state) <= 255` et `len(attrs json) <= 16384`. |
| #8 unique_id instable | Phase entities (foundational) | Format `entry_id + child.identifier + sensor_kind` figé ; tests `async_migrate_entry` avec fixture v1. |
| #9 Notifs nuit / vacances | Phase polling adaptatif + phase events | Quiet hours 22h–6h NC default ; tests : poll en pleine nuit/vacances → assert pas d'event émis. |
| #10 Détection EDT faux ±/− | Phase event detection (cœur valeur) | Tests sur transitions : cancellation, room change, no-op (reorder), vacances vide. Couverture > 90% sur le module diff. |

---

## Sources

### Primary (HIGH confidence — issues réels documentés)
- [delphiki/hass-pronote#128 — IP address suspended (real bans, multiple academies)](https://github.com/delphiki/hass-pronote/issues/128)
- [delphiki/hass-pronote#85 — Detected blocking call to open (pytz)](https://github.com/delphiki/hass-pronote/issues/85)
- [delphiki/hass-pronote#94 — CryptoError "Padding is incorrect" (pronotepy obsolète, message trompeur)](https://github.com/delphiki/hass-pronote/issues/94)
- [delphiki/hass-pronote#133 — Unrecoverable broken entry when authentication starts failing](https://github.com/delphiki/hass-pronote/issues/133)
- [delphiki/hass-pronote#136 — State attributes exceed 16384 bytes (timetable sensor)](https://github.com/delphiki/hass-pronote/issues/136)
- [delphiki/hass-pronote#141 — Auth fails after several days (CryptoError trompeur)](https://github.com/delphiki/hass-pronote/issues/141)
- [delphiki/hass-pronote#151 — Memory leaks (force closing client refs)](https://github.com/delphiki/hass-pronote/pull/151)
- [delphiki/hass-pronote#155 — QR code uuid divergence after restart (auth break)](https://github.com/delphiki/hass-pronote/issues/155)
- [delphiki/hass-pronote#157 — sensor state >255 chars (raw Grade objects in state)](https://github.com/delphiki/hass-pronote/issues/157)
- [bain3/pronotepy#309 — Session expires after few hours, La page a expiré !](https://github.com/bain3/pronotepy/issues/309)
- [bain3/pronotepy#311 — Inability to distinguish canceled lessons from room changes](https://github.com/bain3/pronotepy/issues/311)
- [bain3/pronotepy#274 — Protocol identification problem (Pronote update broke library)](https://github.com/bain3/pronotepy/issues/274)
- [bain3/pronotepy#294 — PronoteAPIError code 3 Accès refusé](https://github.com/bain3/pronotepy/issues/294)

### Secondary (HIGH confidence — official docs)
- [Home Assistant Developer Docs — Fetching data / DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Home Assistant Developer Docs — Reauthentication flow rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/)
- [Home Assistant Developer Docs — Entity unique ID rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id/)
- [Home Assistant Developer Docs — Async blocking operations](https://developers.home-assistant.io/docs/asyncio_blocking_operations/)
- [Home Assistant blog — UTC & Time zone awareness](https://www.home-assistant.io/blog/2015/05/09/utc-time-zone-awareness/)
- [Home Assistant Developer Docs — DataUpdateCoordinator retry_after / UpdateFailed](https://developers.home-assistant.io/blog/2025/11/17/retry-after-update-failed/)
- [Home Assistant Diagnostics platform](https://www.home-assistant.io/integrations/diagnostics/)
- [HACS — Publish your integration](https://www.hacs.xyz/docs/publish/integration/)
- [HACS — General hacs.json fields](https://www.hacs.xyz/docs/publish/start/)

### Tertiary (MEDIUM confidence — community wisdom)
- [Home Assistant Community — DataUpdateCoordinator integrations become unavailable after few hours](https://community.home-assistant.io/t/dataupdatecoordinator-based-integrations-become-unavailable-after-a-few-hours/986502)
- [Home Assistant Community — WTH passwords plain text in config_entries](https://community.home-assistant.io/t/wth-2025-a-secret-is-secret-why-are-passwords-in-plain-text-in-the-config-entries-file/809838)
- [Home Assistant FAQ — This entity does not have a unique ID?](https://www.home-assistant.io/faq/unique_id/)
- [Vice-rectorat Nouvelle-Calédonie — calendrier scolaire (austral)](https://www.ac-noumea.nc/spip.php?article24=)
- [Direction Enseignement NC — calendrier scolaire](https://denc.gouv.nc/calendrier-scolaire)
- [pronotepy documentation — Quickstart & Clients](https://pronotepy.readthedocs.io/en/stable/quickstart.html)
- [pronotepy/PRONOTE protocol.md](https://github.com/bain3/pronotepy/blob/master/PRONOTE%20protocol.md)
- [tolwi/hassio-ecoflow-cloud#684 — Excessive retry & polling causes blacklist (pattern similaire)](https://github.com/tolwi/hassio-ecoflow-cloud/issues/684)

---

*Pitfalls research for: HA custom_component Pronote (NC) via pronotepy*
*Researched: 2026-05-03*
*Méthodologie : analyse systématique des issues open + closed du repo de référence `delphiki/hass-pronote` (157 issues parcourues), de la lib upstream `bain3/pronotepy` (sélection des issues protocol/session), et croisement avec la doc officielle HA developer + retours communautaires.*

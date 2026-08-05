# HA-Pronote

Intégration Home Assistant **non officielle** pour [Pronote](https://www.index-education.com/fr/logiciel-gestion-vie-scolaire.php), le logiciel de vie scolaire des établissements français.

> **Valeur principale :** recevoir une notification fiable dès qu'un cours est **annulé ou modifié** pour aujourd'hui ou demain — notes et informations en découlent.

[![Test](https://github.com/tom333/ha_pronote/actions/workflows/test.yml/badge.svg)](https://github.com/tom333/ha_pronote/actions/workflows/test.yml)
[![HACS](https://github.com/tom333/ha_pronote/actions/workflows/validate.yml/badge.svg)](https://github.com/tom333/ha_pronote/actions/workflows/validate.yml)

## Fonctionnalités

- **Capteurs** par enfant : cours du jour, notes, notifications (informations & sondages).
- **Calendrier** : emploi du temps exposé comme entité `calendar`.
- **Événements** sur le bus HA : changement d'emploi du temps, nouvelle note, nouvelle information — pour vos automatisations.
- **Polling poli** : intervalle réglable, surveillance renforcée 17h–20h les soirs d'école, heures calmes la nuit — pour éviter le bannissement IP du serveur de l'école.
- **Lecture seule** : aucune écriture vers Pronote.

## Installation (HACS — dépôt personnalisé)

1. Ouvrez HACS dans Home Assistant.
2. **Intégrations** → menu en haut à droite → **Dépôts personnalisés**.
3. Ajoutez `https://github.com/tom333/ha_pronote` avec la catégorie **Integration**.
4. Installez **HA-Pronote** depuis le catalogue HACS.
5. Redémarrez Home Assistant.

## Configuration (via l'interface)

1. **Paramètres → Appareils et services → Ajouter une intégration → HA-Pronote**.
2. Saisissez :
   - **URL de votre espace Pronote** — l'URL complète, par ex. `https://0123456a.index-education.net/pronote/eleve.html`.
   - **Type de compte** — `eleve` (compte élève) ou `parent` (portail parent).
   - **Identifiant** et **Mot de passe** Pronote.
3. **Compte parent multi-enfants** : un écran de sélection s'affiche. Choisissez l'enfant à ajouter. Pour en suivre un second, relancez l'ajout d'intégration et choisissez l'autre enfant.

Deux opérations de maintenance sont disponibles depuis la fiche de l'intégration :
- **Ré-authentification** — si Pronote rejette vos identifiants (mot de passe changé), un bouton « Reconfigurer » relance la saisie du mot de passe.
- **Reconfiguration** — modifier l'URL ou le type de compte sans perdre l'historique des entités (l'identifiant interne reste figé).

## Entités exposées

Pour un enfant nommé « Jean Dupont », les entités sont préfixées `jean_dupont` :

| Entité | État | Attributs principaux |
|--------|------|----------------------|
| `sensor.jean_dupont_cours_du_jour` | nombre de cours aujourd'hui | `lessons_today`, `lessons_tomorrow` |
| `sensor.jean_dupont_notes` | moyenne générale de la période | `period_name`, `grades` |
| `sensor.jean_dupont_notifications` | nombre d'informations non lues | `unread_count`, `informations` |
| `calendar.jean_dupont_emploi_du_temps` | cours en cours / à venir | (entité calendrier standard) |

### Schéma des attributs (pour ApexCharts / Mushroom)

`lessons_today` / `lessons_tomorrow` — liste de cours :

```json
{
  "date": "2026-06-15",
  "start": "2026-06-15T08:00:00+02:00",
  "end": "2026-06-15T09:00:00+02:00",
  "subject": "Mathématiques",
  "teacher": "Mme A",
  "classroom": "101",
  "canceled": false,
  "status": ""
}
```

`grades` — liste de notes (9 champs) :

```json
{
  "date": "2026-05-10",
  "subject": "Mathématiques",
  "grade": 15.0,
  "out_of": 20.0,
  "coefficient": 2.0,
  "class_average": 13.0,
  "class_min": 8.0,
  "class_max": 18.0,
  "comment": ""
}
```

`informations` — liste d'informations :

```json
{
  "info_id": "abc123",
  "title": "Réunion parents-professeurs",
  "sender": "Direction",
  "date": "2026-05-12T10:00:00+02:00",
  "excerpt": "…",
  "read": false
}
```

## Événements et automatisations

Trois événements sont émis sur le bus Home Assistant. Chacun porte un contexte enfant (`child_id`, `child_name`, `config_entry_id`) plus des champs spécifiques.

| Événement | Émis quand | Champs spécifiques |
|-----------|-----------|--------------------|
| `pronote_schedule_changed` | un cours d'aujourd'hui ou demain est ajouté / annulé / modifié | `change_type`, `day`, `lesson_date`, `subject`, `before`, `after` |
| `pronote_new_grade` | une nouvelle note apparaît | `subject`, `value`, `out_of`, `coefficient`, `date` |
| `pronote_new_information` | une nouvelle information arrive | `info_id`, `title`, `sender`, `date`, `excerpt` |

### Exemple : notification mobile sur changement d'emploi du temps

```yaml
automation:
  - alias: "Pronote — cours modifié"
    trigger:
      - platform: event
        event_type: pronote_schedule_changed
    action:
      - service: notify.mobile_app_mon_telephone
        data:
          title: "Emploi du temps modifié — {{ trigger.event.data.child_name }}"
          message: >
            {{ trigger.event.data.subject }} ({{ trigger.event.data.day }},
            {{ trigger.event.data.lesson_date }}) :
            {{ trigger.event.data.change_type }}.
```

### Exemple : carte dashboard (Mushroom template)

```yaml
type: custom:mushroom-template-card
primary: Cours du jour — {{ state_attr('sensor.jean_dupont_cours_du_jour','friendly_name') }}
secondary: >
  {{ states('sensor.jean_dupont_cours_du_jour') }} cours aujourd'hui
icon: mdi:school
```

## Politesse du polling (anti-bannissement)

Le serveur Pronote de l'école peut bannir une IP qui l'interroge trop souvent. L'intégration limite donc ses requêtes :

- **Intervalle de rafraîchissement** réglable (15 / 30 / 60 min, défaut 30).
- **Surveillance renforcée 17h–20h** les soirs d'école — c'est là qu'arrivent les changements pour le lendemain.
- **Heures calmes** la nuit et **cadence réduite** les week-ends / vacances.

Tous ces réglages sont dans **Options** de l'intégration. L'intégration est en **lecture seule** : elle n'écrit jamais vers Pronote.

## Dépannage

- **« Pronote a suspendu votre adresse IP »** (carte de réparation HA) — augmentez l'intervalle de polling dans les Options, puis patientez.
- **« Pronote a rejeté vos identifiants »** (carte de réparation HA) — cliquez sur **Reconfigurer** pour ressaisir votre mot de passe.
- **Diagnostic** — depuis la fiche de l'intégration, **Télécharger les diagnostics** produit un export sans secret (mot de passe, identifiant, jeton et URL d'établissement sont expurgés).

## Licence

Voir [LICENSE](LICENSE).

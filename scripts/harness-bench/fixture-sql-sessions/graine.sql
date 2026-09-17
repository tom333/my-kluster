-- Données de départ, VISIBLES. Volontairement sages : deux utilisateurs, une
-- coupure franche chacun, aucun cas limite. Les cas limites (45 min pile,
-- horodatages en double, session à cheval sur minuit, utilisateur à un seul
-- événement) sont dans le correcteur caché, jamais ici — sinon le modèle lit la
-- réponse dans les données au lieu de lire le contrat.
CREATE TABLE evenements (
  utilisateur INTEGER NOT NULL,
  horodatage  TEXT    NOT NULL
);

INSERT INTO evenements (utilisateur, horodatage) VALUES
  (1, '2026-03-02 08:00:00'),
  (1, '2026-03-02 08:12:00'),
  (1, '2026-03-02 08:40:00'),
  (1, '2026-03-02 11:15:00'),
  (1, '2026-03-02 11:30:00'),
  (2, '2026-03-02 09:05:00'),
  (2, '2026-03-02 09:47:00'),
  (2, '2026-03-02 14:00:00');

# La méthode des dossiers

Une mémoire par sujet, lisible par un assistant d'IA avant de l'être par une personne : un fichier Markdown par sujet,
versionné dans git, synchronisé entre vos machines.

- Un fichier par sujet sous `topics/`.
- `MEMORY.md` est **généré** à partir des en-têtes (`scripts/gen-index.py`) : on ne l'édite jamais à la main. Il est
  chargé au début de chaque session de l'assistant, d'où sa taille limitée (l'outil prévient au-delà de 40 Ko).
- Les pièces lourdes (PDF, audio, scans) restent **hors dépôt**, citées par chemin dans `## Refs`.

## Les quatre registres d'un dossier

Un dossier ne mélange pas ce qu'il sait. Chaque section a un rôle, et s'en écarter rend le fichier illisible à la relecture :

| Section | Ce qu'elle porte | Temps |
|---|---|---|
| `## État actuel` | ce qui est vrai **maintenant** du sujet principal (15 lignes au plus) | présent |
| journal (`journal/<slug>-journal.md`, ou `## Log`) | l'histoire chronologique du fil principal, une ligne par événement | passé |
| `## Pending` / `## RDV` / `## Alarme` | ce qui doit arriver (projeté vers Tasks, Agenda, téléphone) | futur |
| `## Notes` | les **branches** : sujets autonomes rattachés au dossier | hors du fil |

## Notes = branches

Une **note** est une petite branche qui pousse à côté du fil principal : une étude chiffrée, la fiche d'un outil ou d'un
modèle, un comparatif, une enquête. Elle vit sous `## Notes`, dans un `###` daté et titré.

- **Elle se lit seule** : elle ouvre sur `**En un mot** : <la conclusion>`, puis le corps.
- **Elle ne touche pas `## État actuel`** : ce n'est pas un changement d'état du sujet, c'est du savoir accumulé à côté.
- **Ce n'est pas le journal** : le journal est chronologique et bref ; une note est un bloc qu'on relit pour lui-même.
- **Elle peut être promue en dossier** quand elle grossit ou acquiert ses propres actions : nouveau `topics/<slug>.md`,
  et un simple renvoi `→ [[slug]]` à sa place. Jamais de copie.
- **Elle nourrit les `aliases:` du parent** : sans cela, la branche est écrite mais introuvable.

Exemple : `examples/topics/reference_pain_au_levain.md`, section `## Notes`.

## Les projections

| Ligne écrite | Résultat | Marque écrite en retour |
|---|---|---|
| `- <action> (due 2026-06-05)` sous `## Pending` (dossier avec `tasklist:`) | une tâche Google Tasks | `[task:ID]` |
| `- ~~<action>~~ [task:ID]` | la tâche est terminée | (reste barrée) |
| `- 2026-06-10 18:30 <desc>` sous `## RDV` | un événement Google Agenda (avec rappels 24 h et 1 h avant) | `[cal:ID]` |
| `- ... \| visio: <URL>` | le lien va dans le champ « lieu » de l'événement | |
| `- ... @attendee=a@example.org` | **ignoré** : un invité externe se confirme à la main | |
| `- ~~2026-06-10 ...~~ [cal:ID]` | l'événement est supprimé | |
| `- 2026-06-20 09:00 <libellé>` sous `## Alarme` | une alarme (commande `DOSSIERS_ALARM_CMD`) le jour J | `[alarm-set:<date>]` |

Chaque projection est **idempotente** : la marque écrite en retour empêche de recréer la même chose.

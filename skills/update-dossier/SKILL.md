---
name: update-dossier
description: Enregistre un fait, une décision, un rendez-vous ou une action dans le fichier de dossier (topics/<slug>.md) du sujet concerné. À utiliser quand l'utilisateur dit « mets à jour le dossier », « crée un dossier », « note ça dans le dossier X », « rappelle-moi… », ou à la fin d'une discussion qui a produit quelque chose à garder. Les tâches, rendez-vous et alarmes écrits dans le fichier sont projetés automatiquement vers Google Tasks, Google Agenda et le téléphone.
---

# Mettre à jour un dossier

## Le modèle

Une seule source de vérité : **un fichier Markdown par sujet**, `topics/<slug>.md`, dans un dépôt git (`$DOSSIERS_DIR`).
Ce dépôt est la mémoire de l'assistant : l'index `MEMORY.md`, généré, est chargé au début de chaque session.
Google Tasks, Google Agenda et les alarmes du téléphone sont des **projections** : on écrit des lignes `Pending`,
`RDV` ou `Alarme` dans le fichier, le projecteur (`scripts/projector/project.py`) les crée et écrit les identifiants
en retour. On ne crée jamais une tâche ou un événement à la main : le projecteur est idempotent, la main fait des doublons.

Donc le travail est : **éditer un fichier**, puis le commiter et le pousser.

## Format d'un dossier

En-tête **à plat** (pas de bloc imbriqué) ; les liens de l'en-tête s'écrivent `'[[slug]]'`. `scripts/normaliser.py` remet
tout dossier à ce format à chaque synchro, mais écrivez-le juste du premier coup.

```markdown
---
slug: <identifiant unique = nom du fichier sans .md>
type: project | user | feedback | reference
status: active | parked | done
updated: YYYY-MM-DD
aliases: [nom courant, synonyme, personne, organisme, lieu, outil]   # project et reference seulement
links: ['[[autre-slug]]']
tasklist: <nom d'une liste Google Tasks>   # facultatif : seulement si les actions doivent aller dans Tasks
repos: [<chemin>@<machine>]                # facultatif : dépôts de code que ce dossier documente (étape 3)
description: <une ligne>
---

## État actuel
• <ce qui est vrai AUJOURD'HUI : 15 lignes au plus, réécrit à chaque mise à jour, jamais empilé ; le premier point résume le sujet (il devient le résumé de l'index)>
• Historique daté : [[<slug>-journal]]

## Pending
- <action> (due YYYY-MM-DD)            # le projecteur crée une tâche, ajoute [task:ID]
- ~~<action faite>~~ [task:ID]         # barrée : le projecteur la marque terminée

## RDV
- YYYY-MM-DD [HH:MM] <description>     # événement d'agenda, ajoute [cal:ID]
- YYYY-MM-DD HH:MM <desc> | visio: <URL>   # rendez-vous en ligne : le lien DOIT figurer sur la ligne
- ... @attendee=nom@example.org        # invité externe : le projecteur SAUTE la ligne (NEEDS_CONFIRM)
- ~~YYYY-MM-DD ...~~ [cal:ID]          # barré : l'événement est supprimé

## Alarme
- YYYY-MM-DD HH:MM <libellé> [silent] [novib]   # une fois ; posée le jour J, puis [alarm-set:<date>]
- weekly:JEU 07:15 <libellé>                     # récurrence hebdomadaire (LUN, MAR, MER, JEU, VEN, SAM, DIM ; ou « JEU,VEN »)

## Dépôts
- <nom> — `<chemin>` [machine] → <URL du remote, ou « aucun remote »> — <YYYY-MM-DD> `<sha court>`

## Refs
- <chemins vers les pièces lourdes (PDF, audio) restées hors dépôt, identifiants, pièges, [[liens]]>

## Notes
<!-- Branches du dossier : sujets autonomes qui poussent à côté du fil principal. -->
### YYYY-MM-DD — <titre qui se comprend seul>
**En un mot** : <la conclusion en une phrase>
<le corps : ce qui est établi, les chiffres, les sources>
```

**Journal à part** : `journal/<slug>-journal.md` (en-tête `slug: <slug>-journal`, `type: journal`, `links: ['[[<slug>]]']`)
garde l'histoire datée, **du plus récent au plus ancien**. À chaque mise à jour : (1) ajouter l'entrée datée EN TÊTE du
journal (`• YYYY-MM-DD — …`), (2) RÉÉCRIRE l'État actuel pour qu'il dise l'état du jour en 15 lignes au plus. Un fait
périmé quitte l'État actuel ; il reste dans le journal.

## Déroulé

### Étape 1 — Trouver la bonne maison
1. **Chercher activement, jamais sur le nom seul.** Un sujet est souvent nommé autrement que dans le dossier qui le
   porte. Cherchez par mots-clés (personnes, organismes, noms de projet, outils) dans `topics/` et dans `MEMORY.md`.
2. **Décider** : un seul dossier correspond (même sous un autre nom) → l'étendre, après l'avoir lu ; le sujet traverse
   plusieurs dossiers → les étendre et les relier (voir le pont) ; aucun ne correspond → créer `topics/<slug>.md` avec un
   slug clair ; vraiment ambigu (≈ 50/50) → poser UNE question avant de créer.
3. **Pont** (sujet à cheval sur 2 dossiers ou plus) : un seul **porteur**, le dossier le plus opérationnel, tient
   `## Pending`, `## RDV` et `tasklist:`. Les autres n'ont qu'une phrase de renvoi (« Volet X de ce sujet → suivi
   consigné dans [[porteur]]. »), sinon Agenda et Tasks projettent deux fois. **Les liens sont toujours bidirectionnels.**

### Étape 2 — Faire la modification, au plus juste
- Réécrire `## État actuel` ; l'entrée datée va en tête du journal.
- **Rafraîchir `aliases:`** (project et reference seulement) : les noms que vous prononcez vraiment, plus les entités
  saillantes (personnes, organismes, lieux, outils). `gen-index.py` les injecte dans `MEMORY.md`, ce qui permet de
  retrouver un dossier par son nom parlé, sans chercher. 4 à 10 termes ; pas de mots génériques.
- Ajouter les lignes `## Pending` (avec `(due YYYY-MM-DD)` s'il y a une échéance) et `## RDV`.
- **Rendez-vous en visio : toujours le lien de connexion** sur la ligne (`| visio: <URL>`). L'invitation d'origine ne
  l'a souvent pas : il est presque toujours dans un autre mail du fil. Cherchez-le avant de créer le rendez-vous.
- **Alarme** : pour ce qui ne doit ABSOLUMENT pas être oublié à une heure précise (≠ simple tâche, ≠ rendez-vous), une
  ligne `## Alarme`. Le projecteur la pose (commande `DOSSIERS_ALARM_CMD`, voir le README) ; vous n'exécutez rien.
- `tasklist:` seulement si les actions doivent apparaître dans une liste Google Tasks ; sans lui, `Pending` reste de la
  connaissance.
- **Une NOTE est une BRANCHE** : tout ce qui est appris sur un sujet rattaché au dossier mais hors du fil principal (étude
  chiffrée, fiche d'outil, comparatif, enquête) va sous `## Notes`, dans un `###` daté et titré. Elle **se lit seule**
  (ligne `**En un mot** :` d'abord), **ne touche pas** `## État actuel`, **n'est pas** le journal, et **peut être promue**
  en dossier (`topics/<nouveau>.md` + renvoi `→ [[nouveau]]`, jamais de copie) quand elle grossit. Ajoutez au parent les
  `aliases:` qui permettront de la retrouver. Plusieurs notes du jour sur le même sujet se fusionnent.
- Ne jamais perdre l'historique. Les pièces lourdes restent hors dépôt, citées par chemin dans `## Refs`.

### Étape 3 — Les dépôts de code liés : commiter, pousser, noter
Un dossier documente souvent du code qui vit ailleurs ; mettre le dossier à jour sans pousser ce code laisse la note en
avance sur la réalité.
1. **Trouver les dépôts** : le champ `repos:` ; les fichiers édités pendant la session, remontés à leur dépôt
   (`git -C <dir> rev-parse --show-toplevel`) ; les chemins cités dans `## Refs` ou `## État actuel`.
2. **Commiter et pousser** chacun (un commit = une intention, le message dit pourquoi), puis **vérifier le push** :
   `git rev-list --left-right --count @{u}...HEAD` doit donner `0 0`.
3. **Noter** une ligne par dépôt dans `## Dépôts` (chemin, machine, remote, sha poussé, date) et compléter `repos:`.
   Pas de remote : écrire « aucun remote » et le dire dans le compte rendu. Un push échoué n'annule pas l'écriture du
   dossier : la ligne dit « push échoué » avec la raison. Ne jamais écrire qu'un dépôt est poussé sans l'avoir vérifié.
Un dossier sans code n'a ni `repos:` ni `## Dépôts`.

### Étape 4 — Commiter et pousser le dossier maintenant
Après l'édition, commiter et pousser le dépôt de dossiers lui-même, tout de suite (`scripts/sync.sh` fait le tour complet :
normalisation, index, projecteur, push). Avant d'écrire, `git fetch` ; si le dépôt est en retard ou si `.sync_broken`
existe, fusionner les deux versions avec soin, jamais en écrasant aveuglément l'une par l'autre.
Ne régénérez pas `MEMORY.md` à la main (généré) ; ne créez pas de tâches ou d'événements à la main.

### Étape 5 — Invités externes (seule exception manuelle)
Un rendez-vous avec un invité externe (quelqu'un recevrait une invitation) est sauté par le projecteur. Montrez le
brouillon de l'invitation et obtenez un accord explicite avant d'ajouter l'invité ou d'envoyer quoi que ce soit.

## Compte rendu
Dire : quel dossier a été créé ou modifié ; quelles lignes `Pending`/`RDV`/`Alarme` ont été ajoutées (elles seront
projetées à la prochaine synchro) ; une ligne par dépôt lié (sha poussé et vérifié, push échoué avec la raison, ou
« aucun remote ») ; la date `updated:`.

## À ne pas faire
- Éditer `MEMORY.md` à la main (régénéré à la synchro).
- Créer tâches ou événements à la main (le projecteur le fait, sans doublon).
- Mettre des binaires dans le dépôt (texte seulement ; chemins en `## Refs`).
- Chercher un sujet par son slug seul (on crée alors un doublon sous un autre nom).
- Laisser un lien à sens unique ; laisser `aliases:` périmé ou sur plusieurs lignes ; en mettre sur un dossier `feedback`/`user`.
- Créer un rendez-vous en visio sans son lien.
- Laisser la note en avance sur le code, ou annoncer un push non vérifié.
- Verser une branche dans l'État actuel ou le journal ; la laisser grossir sans la promouvoir.
- Dupliquer `Pending`/`RDV` entre dossiers reliés (un seul porteur).

---
name: open-dossier
description: Charge le dossier d'un sujet et en fait un point de situation. À utiliser quand l'utilisateur dit « ouvre le dossier sur X », « où en est X », « fais le point sur X », « recharge le contexte sur X ». « Dossier » désigne ici le dossier conceptuel (fichier topics/<slug>.md, son journal, les tâches et rendez-vous projetés), PAS un dossier du disque ni une fenêtre de l'explorateur de fichiers. Face de lecture de update-dossier.
---

# Ouvrir un dossier

**« Ouvre le dossier » n'ouvre jamais un dossier du disque.** Si l'utilisateur veut vraiment un répertoire, il donne un
chemin ou dit « dans l'explorateur ».

## Déroulé

### Étape 1 — Résoudre le sujet
`MEMORY.md` est déjà dans votre contexte : chaque dossier de type project ou reference y porte ses alias entre `⟨ ⟩`
(`- project_fete_du_quartier ⟨fête du quartier; repas de rue; buvette⟩ — <résumé>`). **Rapprochez d'abord le nom prononcé de
ces alias**, sans toucher au shell : cela règle presque toujours la question. Seulement si l'index ne donne rien,
cherchez par mots-clés dans `topics/` (`grep -ril <mot> $DOSSIERS_DIR/topics`). Plusieurs candidats : UNE question.

### Étape 2 — Lire les couches (en parallèle si possible)
1. `topics/<slug>.md` : son `## État actuel` est l'état du jour ; suivez les `[[liens]]` utiles.
2. `journal/<slug>-journal.md` : seulement si la question porte sur le passé (« quand », « pourquoi avait-on… »).
3. **Tâches ouvertes** de la liste `tasklist:` du dossier (`gws tasks tasks list …` ou l'API Google Tasks).
4. **Prochains rendez-vous** liés (Agenda, 60 jours, mot-clé du sujet).
5. `## Dépôts` : si le dossier documente du code, l'état des dépôts (`git status`, dernier commit).
Sautez sans bruit une couche que le sujet n'a pas (pas de liste Tasks : dites-le dans le point).

### Étape 3 — Le point de situation
Court, en vraies puces :
```
Dossier <sujet> — ouvert
• État actuel : <2-3 lignes>
• Dernières évolutions : <ce qui a changé récemment>
• Actions ouvertes : <N tâches, les citer> (ou : aucune liste Tasks)
• Prochains rendez-vous : <événements> (ou : aucun)
• Incohérences : <si deux couches se contredisent> (omettre sinon)
```
C'est un résumé, pas un copier-coller. Si le dossier est long, résumez l'état et signalez que l'historique existe.

### Étape 4 — Signaler ce qui est périmé
Si le dossier et la réalité divergent (un dépôt en avance, une tâche faite mais non barrée), dites-le et proposez une
passe `update-dossier` à la fin de la session.

## Erreurs courantes
| Erreur | Correction |
|---|---|
| Ouvrir l'explorateur de fichiers | Dossier conceptuel : charger les couches |
| Recopier le fichier en entier | Résumé : état, évolutions, actions, rendez-vous |
| Chercher avant de regarder l'index | Les alias de `MEMORY.md` résolvent presque tout |
| Passer sous silence une couche absente | Le dire explicitement |

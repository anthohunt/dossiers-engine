# Dossiers d'exemple (fictifs)

Trois dossiers inventés pour essayer le moteur : un projet (`project_`), une fiche de référence (`reference_`) et une
préférence (`feedback_`), plus le journal du projet. Copiez-les dans votre propre dépôt de dossiers :

```bash
mkdir -p mes-dossiers/topics mes-dossiers/journal && git -C mes-dossiers init
cp examples/topics/*.md mes-dossiers/topics/ && cp examples/journal/*.md mes-dossiers/journal/
DOSSIERS_DIR=$PWD/mes-dossiers python3 scripts/gen-index.py     # écrit mes-dossiers/MEMORY.md
DOSSIERS_DIR=$PWD/mes-dossiers python3 scripts/projector/project.py --dry-run
```

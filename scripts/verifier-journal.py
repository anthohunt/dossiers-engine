#!/usr/bin/env python3
"""Verifie le decoupage d'un dossier en « etat present » + journal.

    verifier-journal.py <original.md> <slug>

- aucune ligne du corps original ne se perd : chacune se retrouve, telle quelle,
  dans topics/<slug>.md ou dans journal/<slug>-journal.md ;
- les lignes projetees ([task:ID] / [cal:ID]) restent dans topics/<slug>.md ;
- « ## État actuel » tient en 15 lignes au plus.
Sortie 0 = conforme ; sinon la liste des ecarts.
"""
import os, re, sys

ROOT = os.environ.get("DOSSIERS_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def corps(path):
    t = open(path, encoding="utf-8").read()
    if t.startswith("---"):
        t = t[3:].partition("\n---")[2]
    return t


def lignes(t):
    return {l.strip() for l in t.splitlines() if l.strip()}


def main():
    orig, slug = sys.argv[1], sys.argv[2]
    topic = os.path.join(ROOT, "topics", slug + ".md")
    journal = os.path.join(ROOT, "journal", slug + "-journal.md")
    ecarts = []
    if not os.path.exists(journal):
        ecarts.append("journal absent")
    nouveau_topic = corps(topic)
    nouveau = lignes(nouveau_topic) | (lignes(corps(journal)) if os.path.exists(journal) else set())
    perdues = [l for l in lignes(corps(orig)) if l not in nouveau]
    for l in perdues[:10]:
        ecarts.append("ligne perdue : " + l[:120])
    if len(perdues) > 10:
        ecarts.append(f"... {len(perdues)} lignes perdues au total")
    for l in lignes(corps(orig)):
        if re.search(r"\[(task|cal):[^\]]+\]", l) and l not in lignes(nouveau_topic):
            ecarts.append("ligne projetee sortie du dossier : " + l[:120])
    m = re.search(r"## État actuel\s*\n(.*?)(\n## |\Z)", nouveau_topic, re.S)
    if not m:
        ecarts.append("pas de « ## État actuel »")
    else:
        n = len([l for l in m.group(1).splitlines() if l.strip()])
        if n > 15:
            ecarts.append(f"État actuel trop long : {n} lignes")
    taille = os.path.getsize(topic)
    print(f"{slug}: dossier {taille // 1024} Ko, {'conforme' if not ecarts else str(len(ecarts)) + ' ecart(s)'}")
    for e in ecarts:
        print("  " + e)
    sys.exit(1 if ecarts else 0)


if __name__ == "__main__":
    main()

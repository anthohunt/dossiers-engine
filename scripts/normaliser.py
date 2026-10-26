#!/usr/bin/env python3
"""Normalise l'en-tete (front-matter) et les liens des dossiers topics/*.md.

Un seul format, lisible par Obsidian (proprietes a plat) et par les scripts
(gen-index.py, projector/project.py lisent ligne a ligne) :

    slug, type, status, updated, aliases, links, tasklist, calendar, repos, description

- Le bloc imbrique `metadata:` (ecrit par l'outil memoire de Claude Code) est
  remis a plat ; `name: ""`, `node_type`, `originSessionId`, `modified` sont retires.
- `links:` devient une liste de "[[slug]]" (Obsidian les compte comme liens).
- Les liens mal ecrits (tirets, `.md` en trop, prefixe oublie) sont corriges
  dans l'en-tete et dans le texte.

Idempotent : sans changement a faire, aucun fichier n'est reecrit.
Usage : normaliser.py [--dry] [--quiet]
"""
import glob, json, os, re, sys, datetime
import yaml

ROOT = os.environ.get("DOSSIERS_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS = os.path.join(ROOT, "topics")
ORDRE = ["slug", "type", "status", "updated", "aliases", "links",
         "tasklist", "calendar", "repos", "description"]
LISTES = {"aliases", "links", "repos"}
JETES = {"node_type", "originSessionId", "modified"}
# anciens noms de dossiers, renommes depuis : fichier facultatif scripts/renames.json {"ancien-nom": "nouveau-slug"}
_REN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renames.json")
RENOMMES = json.load(open(_REN, encoding="utf-8")) if os.path.exists(_REN) else {}
PLAIN = re.compile(r"^[\w\d][\w\d .,/@()'+-]*$")


def slugs_connus():
    s = set()
    for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
        if "/.git/" not in p:
            s.add(os.path.basename(p)[:-3])
    return s


def resoudre(cible, connus):
    c = cible.strip().strip("[]").strip()
    c = RENOMMES.get(c, c)
    if c in connus:
        return c
    essais = [c[:-3] if c.endswith(".md") else c]
    base = essais[0]
    essais += [base.replace("-", "_"), "project_" + base, "project_" + base.replace("-", "_"),
               "reference_" + base, "feedback_" + base]
    for e in essais:
        if e in connus:
            return e
    return None


def en_liste(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    if isinstance(v, str):
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = v[1:-1]
        return [x.strip().strip("'\"").strip("[]") for x in v.split(",") if x.strip()]
    return [v]


def unir(*listes):
    vu, out = set(), []
    for l in listes:
        for x in l:
            k = str(x).strip()
            if k and k not in vu:
                vu.add(k)
                out.append(k)
    return out


def scalaire(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:10]
    return v


def emettre(k, v):
    if k in LISTES:
        txt = yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=100000).strip()
        return f"{k}: {txt}"
    v = scalaire(v)
    if isinstance(v, str) and PLAIN.match(v) and v.strip() == v and ": " not in v:
        return f"{k}: {v}"
    if isinstance(v, str):
        txt = yaml.safe_dump(v, allow_unicode=True, width=100000).strip()
        if txt.endswith("\n..."):
            txt = txt[:-4].strip()
        txt = txt.removesuffix("...").strip()
        return f"{k}: {txt}"
    return f"{k}: {yaml.safe_dump(v, default_flow_style=True, allow_unicode=True).strip().removesuffix('...').strip()}"


LIEN = re.compile(r"\[\[([^\]\|#\n]+)((?:[#|][^\]\n]*)?)\]\]")


def normaliser(path, connus, rapport):
    texte = open(path, encoding="utf-8").read()
    if not texte.startswith("---"):
        return None
    brut, sep, corps = texte[3:].partition("\n---")
    if not sep:
        return None
    fm = yaml.safe_load(brut) or {}
    meta = fm.pop("metadata", None) or {}
    nom = os.path.basename(path)[:-3]
    if fm.get("name", None) in ("", None):
        fm.pop("name", None)
    plat = {}
    for k in set(fm) | set(meta):
        a, b = fm.get(k), meta.get(k)
        if k in JETES:
            continue
        if k in LISTES:
            plat[k] = unir(en_liste(a), en_liste(b))
        elif k == "updated":
            vals = [str(scalaire(x)) for x in (a, b) if x]
            plat[k] = max(vals) if vals else None
        else:
            plat[k] = a if a not in (None, "") else b
    plat["slug"] = plat.get("slug") or nom
    # liens de l'en-tete -> "[[slug]]" resolus
    liens = []
    for l in plat.get("links", []):
        c = l.strip()
        if c.startswith("[[") and c.endswith("]]"):
            c = c[2:-2]
        r = resoudre(c, connus)
        if r is None:
            rapport.append(f"{nom}: lien d'en-tete introuvable -> {c}")
            r = c
        if r != nom:
            liens.append(f"[[{r}]]")
    plat["links"] = unir(liens)
    lignes = []
    for k in ORDRE + sorted(k for k in plat if k not in ORDRE):
        v = plat.get(k)
        if v in (None, "", []):
            continue
        lignes.append(emettre(k, v))

    def corriger(m):
        cible, suite = m.group(1), m.group(2)
        r = resoudre(cible, connus)
        if r is None:
            rapport.append(f"{nom}: lien du texte introuvable -> {cible.strip()}")
            return m.group(0)
        return f"[[{r}{suite}]]"

    corps = LIEN.sub(corriger, corps)
    neuf = "---\n" + "\n".join(lignes) + "\n---" + corps
    return neuf if neuf != texte else None


def main():
    dry = "--dry" in sys.argv
    quiet = "--quiet" in sys.argv
    connus = slugs_connus()
    rapport, changes = [], 0
    for p in sorted(glob.glob(os.path.join(TOPICS, "*.md"))):
        try:
            neuf = normaliser(p, connus, rapport)
        except yaml.YAMLError as e:
            rapport.append(f"{os.path.basename(p)}: en-tete illisible ({e.__class__.__name__})")
            continue
        if neuf is not None:
            changes += 1
            if not dry:
                open(p, "w", encoding="utf-8", newline="\n").write(neuf)
    if not quiet or changes:
        print(f"{'a normaliser' if dry else 'normalises'}: {changes} dossiers")
    if not quiet:
        for r in rapport:
            print("  " + r)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Regenerate MEMORY.md from topics/*.md front-matter. Stdlib only.
import os, glob, re, sys
ROOT = os.environ.get("DOSSIERS_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS = os.path.join(ROOT, "topics")
MAX_ALIASES = 100  # caracteres d'alias gardes par entree (MEMORY.md est charge dans chaque session)
def parse(path):
    t = open(path, encoding="utf-8").read()
    if not t.startswith("---"):
        return None
    fm_raw, _, body = t[3:].partition("---")
    fm = {}
    # Une cle peut porter sa valeur en ligne (`aliases: [a, b]`) ou ouvrir une
    # liste YAML multi-ligne (`aliases:` puis des `- item`). Le normaliseur des
    # dossiers produit la seconde forme : sans ce recollage, l'index perdait les
    # alias de 61 topics, qui devenaient introuvables au recall.
    liste_en_cours = None
    for line in fm_raw.strip().splitlines():
        nu = line.strip()
        if liste_en_cours and nu.startswith("- "):
            item = nu[2:].strip().strip('"').strip("'")
            deja = fm[liste_en_cours]
            fm[liste_en_cours] = f"{deja}, {item}" if deja else item
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            fm[k] = v
            liste_en_cours = k if v == "" else None
        else:
            liste_en_cours = None
    hook = ""
    m = re.search(r"## État actuel\s*\n(.*?)(\n##|\Z)", body, re.S)
    if m:
        for ln in m.group(1).splitlines():
            ln = ln.strip()
            if ln[:1] in ("-", "•", "*"):
                hook = ln.lstrip("-•* ").strip()
                break
    return fm, hook
def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(TOPICS, "*.md"))):
        if os.path.basename(path).startswith("_"):
            continue
        parsed = parse(path)
        if not parsed:
            continue
        fm, hook = parsed
        slug = fm.get("slug", os.path.basename(path)[:-3])
        status = fm.get("status", "?")
        updated = fm.get("updated", "?")
        hook = (hook[:55] + "…") if len(hook) > 55 else hook
        # Aliases = semantic-matching surface for project/reference dossiers.
        # Single-line `aliases: [a, b, c]` in front-matter -> shown in-context
        # so the spoken name resolves without grep. feedback/user have none.
        aliases = fm.get("aliases", "").strip().strip("[]").strip()
        # normaliser.py ecrit la liste en YAML : un alias contenant « : » ou « , »
        # y est entre guillemets ; on les retire pour l'index.
        aliases = ", ".join(a.strip().strip("'\"") for a in aliases.split(", ")) if aliases else ""
        # MEMORY.md est charge en entier dans le contexte de chaque session :
        # une entree qui deborde coute a toutes les conversations. On garde les
        # premiers termes (les plus parlants sont ecrits en tete) et on coupe
        # sur une virgule pour ne jamais laisser un alias a moitie.
        if len(aliases) > MAX_ALIASES:
            aliases = aliases[:MAX_ALIASES].rsplit(",", 1)[0].strip() + ", …"
        typ = fm.get("type", "")
        if aliases and typ in ("project", "reference"):
            rows.append(f"- {slug} ⟨{aliases}⟩ — {hook}")
        else:
            rows.append(f"- {slug} — {hook}")
    header = ("# Memory Index (auto-generated — do not edit by hand)\n"
              "# Each topic's file = topics/<slug>.md\n\n")
    out = header + "\n".join(rows) + "\n"
    open(os.path.join(ROOT, "MEMORY.md"), "w", encoding="utf-8").write(out)
    print(f"wrote MEMORY.md: {len(rows)} topics, {len(out)} bytes")
    if len(out) > 40*1024:
        print("WARNING: index over 40KB", file=sys.stderr)
if __name__ == "__main__":
    main()

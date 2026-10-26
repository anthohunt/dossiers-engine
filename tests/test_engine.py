"""Tests du moteur sur de vrais fichiers (dépôt git jetable, vrais scripts). Aucun appel réseau : le projecteur
parle à de faux services Google qui enregistrent les appels reçus.
Lancer : python3 -m unittest discover -s tests   (PyYAML requis ; icalendar pour le test de l'import .ics)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
EX = ROOT / "examples"


def run(args, **kw):
    env = {**os.environ, **kw.pop("env", {})}
    return subprocess.run(args, capture_output=True, text=True, env=env, **kw)


class Depot(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="dossiers-test-"))
        (self.d / "topics").mkdir()
        (self.d / "journal").mkdir()
        for f in (EX / "topics").glob("*.md"):
            shutil.copy(f, self.d / "topics")
        for f in (EX / "journal").glob("*.md"):
            shutil.copy(f, self.d / "journal")
        self.env = {"DOSSIERS_DIR": str(self.d), "DOSSIERS_STATE": str(self.d / "_etat")}

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)


class TestIndex(Depot):
    def test_index_genere_avec_alias_et_resume(self):
        r = run([sys.executable, SCRIPTS / "gen-index.py"], env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        idx = (self.d / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("- project_fete_du_quartier ⟨fête du quartier, fête des voisins, repas de rue,", idx)
        self.assertIn("Repas de rue des Tilleuls le 20 juin 2026", idx)             # résumé = 1er point de l'état actuel
        self.assertIn("- feedback_reponses_courtes — ", idx)                          # feedback : pas d'alias
        self.assertNotIn("⟨", [l for l in idx.splitlines() if "feedback_" in l][0])

    def test_dossier_sans_entete_ignore(self):
        (self.d / "topics" / "brouillon.md").write_text("pas d'en-tête\n", encoding="utf-8")
        run([sys.executable, SCRIPTS / "gen-index.py"], env=self.env)
        self.assertNotIn("brouillon", (self.d / "MEMORY.md").read_text(encoding="utf-8"))


class TestNormaliser(Depot):
    def test_met_a_plat_et_corrige_les_liens(self):
        (self.d / "topics" / "project_x.md").write_text(textwrap.dedent("""\
            ---
            name: ""
            originSessionId: abc
            metadata:
              type: project
              updated: 2026-01-02
              aliases: [alpha, beta]
            links: [fete-du-quartier]
            ---

            ## État actuel
            • Voir [[reference-pain-au-levain]].
            """), encoding="utf-8")
        r = run([sys.executable, SCRIPTS / "normaliser.py"], env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        t = (self.d / "topics" / "project_x.md").read_text(encoding="utf-8")
        head = t.split("---")[1]
        self.assertNotIn("metadata", head)
        self.assertNotIn("originSessionId", head)
        self.assertIn("slug: project_x", head)
        self.assertIn("type: project", head)
        self.assertIn("[[project_fete_du_quartier]]", head)                          # lien d'en-tête résolu
        self.assertIn("[[reference_pain_au_levain]]", t)                             # lien du texte corrigé (tirets)
        again = run([sys.executable, SCRIPTS / "normaliser.py", "--dry"], env=self.env)
        self.assertIn("0 dossiers", again.stdout)                                    # idempotent

    def test_exemples_deja_normalises(self):
        r = run([sys.executable, SCRIPTS / "normaliser.py", "--dry"], env=self.env)
        self.assertIn("0 dossiers", r.stdout, r.stdout + r.stderr)


class TestJournal(Depot):
    def test_decoupage_conforme_et_ligne_perdue(self):
        orig = self.d / "orig.md"
        topic = (self.d / "topics" / "project_fete_du_quartier.md").read_text(encoding="utf-8")
        journal = (self.d / "journal" / "project_fete_du_quartier-journal.md").read_text(encoding="utf-8")
        orig.write_text(topic + "\n" + journal.split("---", 2)[2], encoding="utf-8")
        r = run([sys.executable, SCRIPTS / "verifier-journal.py", orig, "project_fete_du_quartier"], env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout)
        orig.write_text(orig.read_text(encoding="utf-8") + "\n• une ligne qui a disparu\n", encoding="utf-8")
        r = run([sys.executable, SCRIPTS / "verifier-journal.py", orig, "project_fete_du_quartier"], env=self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ligne perdue", r.stdout)


FAUX_GAUTH = '''
import json, os
LOG = os.environ["FAUX_GOOGLE_LOG"]
ETAT = LOG + ".etat"
def _etat():
    return json.load(open(ETAT)) if os.path.exists(ETAT) else {}
def _save(e): json.dump(e, open(ETAT, "w"))
def _w(op, **kw):
    open(LOG, "a").write(json.dumps({"op": op, **kw}, default=str) + "\\n")
class _Call:
    def __init__(self, val): self.val = val
    def execute(self): return self.val
class _Tasks:
    def tasklists(self): return self
    def list(self, **k): return _Call({"items": [{"title": "Fête du quartier", "id": "L1"}]})
    def tasks(self): return self
    def insert(self, tasklist=None, body=None): _w("task.insert", body=body); return _Call({"id": "T%d" % len(open(LOG).read().splitlines())})
    def get(self, tasklist=None, task=None): return _Call({"status": _etat().get("task:" + task, "needsAction")})
    def patch(self, tasklist=None, task=None, body=None):
        _w("task.patch", task=task, body=body); e = _etat(); e["task:" + task] = body["status"]; _save(e); return _Call({})
class _Events:
    def events(self): return self
    def insert(self, calendarId=None, body=None):
        _w("event.insert", body=body); i = "E%d" % len(open(LOG).read().splitlines()); e = _etat(); e["ev:" + i] = body; _save(e); return _Call({"id": i})
    def get(self, calendarId=None, eventId=None): return _Call(_etat().get("ev:" + eventId, {}))
    def patch(self, calendarId=None, eventId=None, body=None):
        _w("event.patch", body=body); e = _etat(); e.setdefault("ev:" + eventId, {}).update(body); _save(e); return _Call({})
    def delete(self, calendarId=None, eventId=None): _w("event.delete", id=eventId); return _Call({})
def tasks_service(): return _Tasks()
def calendar_service(): return _Events()
'''


class TestProjecteur(Depot):
    def setUp(self):
        super().setUp()
        self.faux = Path(tempfile.mkdtemp(prefix="faux-gauth-"))
        (self.faux / "gauth.py").write_text(FAUX_GAUTH, encoding="utf-8")
        shutil.copy(SCRIPTS / "projector" / "project.py", self.faux / "project.py")
        self.log = self.faux / "appels.jsonl"
        self.log.write_text("")
        self.env.update(FAUX_GOOGLE_LOG=str(self.log), DOSSIERS_TZ="Europe/Paris",
                        DOSSIERS_ALARM_CMD=f"{sys.executable} {self.faux / 'alarme.py'}")
        (self.faux / "alarme.py").write_text("import sys,json;open(sys.argv[0]+'.log','a').write(json.dumps(sys.argv[1:])+'\\n')\n")
        subprocess.run(["git", "init", "-q"], cwd=self.d)

    def tearDown(self):
        shutil.rmtree(self.faux, ignore_errors=True)
        super().tearDown()

    def test_projette_ecrit_les_marques_et_reste_idempotent(self):
        today = __import__("datetime").date.today().isoformat()
        f = self.d / "topics" / "project_fete_du_quartier.md"
        f.write_text(f.read_text(encoding="utf-8").replace("- 2026-06-20 09:00 Récupérer", f"- {today} 09:00 Récupérer"), encoding="utf-8")
        r = run([sys.executable, self.faux / "project.py"], env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        t = f.read_text(encoding="utf-8")
        self.assertRegex(t, r"- Relancer la mairie .*\(due 2026-06-05\) \[task:T\d+\]")
        self.assertRegex(t, r"Réunion des bénévoles chez Camille .*\[cal:E\d+\]")
        self.assertRegex(t, r"Repas de rue des Tilleuls \[cal:E\d+\]")
        self.assertIn(f"[alarm-set:{today}]", t)
        appels = [__import__("json").loads(l) for l in self.log.read_text().splitlines()]
        events = [a["body"] for a in appels if a["op"] == "event.insert"]
        visio = next(e for e in events if "bénévoles" in e["summary"])
        self.assertEqual(visio["location"], "https://meet.example.org/tilleuls-benevoles")   # le lien va dans « lieu »
        self.assertEqual(visio["start"]["timeZone"], "Europe/Paris")
        n = len(appels)
        r2 = run([sys.executable, self.faux / "project.py"], env=self.env)                      # 2e passe : rien de nouveau
        self.assertEqual(len(self.log.read_text().splitlines()), n, r2.stdout)

    def test_invite_externe_saute_et_ligne_barree_supprime(self):
        f = self.d / "topics" / "project_fete_du_quartier.md"
        t = f.read_text(encoding="utf-8")
        t = t.replace("- 2026-06-20 12:00 Repas de rue des Tilleuls", "- 2026-06-20 12:00 Repas @attendee=maire@example.org\n- ~~2026-06-21 10:00 Rangement~~ [cal:EXISTANT]")
        f.write_text(t, encoding="utf-8")
        r = run([sys.executable, self.faux / "project.py"], env=self.env)
        self.assertIn("NEEDS_CONFIRM", r.stdout)
        appels = self.log.read_text()
        self.assertNotIn("maire@example.org", appels)
        self.assertIn('"op": "event.delete", "id": "EXISTANT"', appels)

    def test_dry_run_sans_google(self):
        env = {**self.env}
        env.pop("FAUX_GOOGLE_LOG")
        r = run([sys.executable, SCRIPTS / "projector" / "project.py", "--dry-run"], env=env)      # aucun accès Google
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("create task 'Relancer la mairie", r.stdout)
        self.assertNotIn("[task:", (self.d / "topics" / "project_fete_du_quartier.md").read_text(encoding="utf-8").split("[task:EXEMPLE")[0])


class TestSync(Depot):
    def test_sync_commit_index_et_push(self):
        origin = self.d.parent / (self.d.name + "-origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        g = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *a], cwd=self.d, check=True, capture_output=True)
        g("init", "-q", "-b", "main")
        g("remote", "add", "origin", str(origin))
        g("add", "-A"); g("commit", "-q", "-m", "départ"); g("push", "-q", "-u", "origin", "main")
        (self.d / "topics" / "project_nouveau.md").write_text("---\nslug: project_nouveau\ntype: project\naliases: [nouveau]\n---\n\n## État actuel\n• **Sujet neuf.**\n", encoding="utf-8")
        env = {**self.env, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
        r = run(["bash", str(SCRIPTS / "sync.sh")], env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.d / ".sync_broken").exists())
        self.assertIn("project_nouveau", (self.d / "MEMORY.md").read_text(encoding="utf-8"))
        ahead = subprocess.run(["git", "rev-list", "--left-right", "--count", "@{u}...HEAD"], cwd=self.d, capture_output=True, text=True).stdout.split()
        self.assertEqual(ahead, ["0", "0"])                                           # tout est poussé
        shutil.rmtree(origin, ignore_errors=True)


class TestIcs(unittest.TestCase):
    def test_import_a_blanc(self):
        try:
            import icalendar  # noqa: F401
        except ImportError:
            self.skipTest("icalendar absent")
        ics = "BEGIN:VCALENDAR\r\nMETHOD:REQUEST\r\nBEGIN:VEVENT\r\nUID:abc@example.org\r\nDTSTART:20260620T100000Z\r\nDTEND:20260620T110000Z\r\nSUMMARY:Atelier\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        r = subprocess.run([sys.executable, str(SCRIPTS / "projector" / "ics-import.py"), "--dry-run"], input=ics, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"summary": "Atelier"', r.stdout)


if __name__ == "__main__":
    unittest.main()

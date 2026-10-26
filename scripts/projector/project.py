#!/usr/bin/env python3
"""Project dossier Pending/RDV/Alarme lines into Google Tasks + Calendar (+ an optional alarm command).

Idempotent via IDs written back into the files:
  Pending:  - <text> (due YYYY-MM-DD)            -> creates a Task, appends [task:ID]
            - ~~<text>~~ [task:ID]               -> marks the Task completed
  RDV:      - YYYY-MM-DD [HH:MM] <desc>          -> creates a Calendar event, appends [cal:ID]
            - ... @attendee=a@b.com (no [cal:])  -> NEEDS_CONFIRM, skipped (external invitee)
            - ~~...~~ [cal:ID]                   -> deletes the Calendar event

Tasks projection only runs for topics whose front-matter has `tasklist: <name>`.
Calendar projection runs for any RDV line (primary calendar, or the one named by front-matter
`calendar: <calendarId>`), unless it has an external attendee.
"""
import os, re, glob, sys, argparse, subprocess, datetime

ROOT = os.environ.get("DOSSIERS_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOPICS = os.path.join(ROOT, "topics")
TZ = os.environ.get("DOSSIERS_TZ", "UTC")   # fuseau des heures écrites dans les dossiers

DUE_RE = re.compile(r"\(due (\d{4}-\d{2}-\d{2})\)")
TASKID_RE = re.compile(r"\[task:([^\]]+)\]")
CALID_RE = re.compile(r"\[cal:([^\]]+)\]")
ATTENDEE_RE = re.compile(r"@attendee=(\S+)")
RDV_DT_RE = re.compile(r"^-\s*(?:~~)?\s*(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s+(.*)")
VISIO_SPLIT_RE = re.compile(r"\s*\|\s*visio\s*:\s*", re.I)
VISIO_URL_RE = re.compile(r"https?://\S+")


ALARMSET_RE = re.compile(r"\[alarm-(?:set|missed)[^\]]*\]")
ALARM_DATE_RE = re.compile(r"^-\s*(?:~~)?\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.*)")
ALARM_WEEKLY_RE = re.compile(r"^-\s*(?:~~)?\s*weekly:([A-Za-zÀ-ÿ,]+)\s+(\d{2}:\d{2})\s+(.*)", re.I)
DAYMAP = {"DIM":1,"LUN":2,"MAR":3,"MER":4,"JEU":5,"VEN":6,"SAM":7}
# Commande qui pose une alarme (voir alarme-ntfy.sh) ; absente = les lignes « ## Alarme » restent en attente.
PHONE_ALARM = os.environ.get("DOSSIERS_ALARM_CMD", "")


def _alarm_flags(line):
    low = line.lower()
    return ("[silent]" in low), ("[novib]" in low)


def _alarm_label(raw):
    return re.sub(r"\[[^\]]*\]", "", raw).strip()


def _run_phone_alarm(argv, dry, log, slug):
    if dry:
        log.append(f"[{slug}] DRY alarm " + " ".join(argv))
        return True
    if not PHONE_ALARM:
        log.append(f"[{slug}] pas de DOSSIERS_ALARM_CMD : alarme laissée en attente")
        return False
    try:
        r = subprocess.run(PHONE_ALARM.split() + argv, capture_output=True, text=True, timeout=40)
        if r.returncode == 0:
            return True
        log.append(f"[{slug}] alarm command FAILED rc={r.returncode}: {r.stderr.strip()[:120]} (retry next run)")
        return False
    except Exception as e:
        log.append(f"[{slug}] alarm command error {type(e).__name__} (retry next run)")
        return False


def front_matter(text):
    fm = {}
    if text.startswith("---"):
        raw = text[3:].partition("---")[0]
        for line in raw.strip().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
    return fm


def section_lines(text, heading):
    m = re.search(r"## " + re.escape(heading) + r"\s*\n(.*?)(\n## |\Z)", text, re.S)
    if not m:
        return []
    return [ln for ln in m.group(1).splitlines() if ln.strip().startswith("-")]


def is_struck(line):
    return "~~" in line


def clean_title(line):
    t = line.lstrip("- ").strip()
    t = t.replace("~~", "")
    t = TASKID_RE.sub("", t).strip()
    t = DUE_RE.sub("", t).strip()
    return t


class Tasks:
    def __init__(self, dry):
        self.dry = dry
        self._svc = None
        self._lists = None

    @property
    def svc(self):
        if self._svc is None:
            from gauth import tasks_service
            self._svc = tasks_service()
        return self._svc

    def list_id(self, name):
        if self.dry:
            return "DRY_LIST"
        if self._lists is None:
            self._lists = {l["title"]: l["id"] for l in self.svc.tasklists().list(maxResults=100).execute().get("items", [])}
        if name not in self._lists:
            lid = self.svc.tasklists().insert(body={"title": name}).execute()["id"]
            self._lists[name] = lid
        return self._lists[name]

    def create(self, list_name, title, due):
        body = {"title": title}
        if due:
            body["due"] = due + "T00:00:00.000Z"
        if self.dry:
            return "DRY_TASK_ID"
        try:
            return self.svc.tasks().insert(tasklist=self.list_id(list_name), body=body).execute()["id"]
        except Exception as e:
            print(f"  task create failed ('{title}'): {type(e).__name__}: {e}")
            return None

    def complete(self, list_name, tid):
        """Retourne True si un appel a ete fait (tache reellement cloturee), False sinon."""
        if self.dry:
            return False
        try:
            # Une ligne barree reste barree pour toujours : sans ce test, chaque run re-cloturait
            # toutes les taches deja faites (et Google repond 403 sur une tache deja completee).
            cur = self.svc.tasks().get(tasklist=self.list_id(list_name), task=tid).execute()
            if cur.get("status") == "completed":
                return False
            self.svc.tasks().patch(tasklist=self.list_id(list_name), task=tid, body={"status": "completed"}).execute()
            return True
        except Exception as e:
            print(f"  task complete failed ({tid}): {type(e).__name__}: {e}")
            return False


def _parse_rdv_desc(desc):
    """Split '<titre> | visio: <bloc>' -> (summary, location, description).
    location = 1st URL of the visio block (clickable + Join button on Zoom/Teams);
    description = full visio block (keeps Meeting ID / passcode). No visio -> (desc, None, None)."""
    parts = VISIO_SPLIT_RE.split(desc, maxsplit=1)
    if len(parts) < 2:
        return desc.strip(), None, None
    summary = parts[0].strip().rstrip(";,").strip()
    visio = parts[1].strip()
    m = VISIO_URL_RE.search(visio)
    location = m.group(0).rstrip(".,;)") if m else None
    return summary, location, "Visio : " + visio


class Calendar:
    def __init__(self, dry):
        self.dry = dry
        self._svc = None
        # Agenda cible du dossier en cours : front-matter `calendar: <calendarId>`, sinon primary.
        self.calendar_id = "primary"

    @property
    def svc(self):
        if self._svc is None:
            from gauth import calendar_service
            self._svc = calendar_service()
        return self._svc

    def create(self, date, time, desc):
        if time:
            start = {"dateTime": f"{date}T{time}:00", "timeZone": TZ}
            h, m = int(time[:2]), int(time[3:])
            end_h = (h + 1) % 24
            end = {"dateTime": f"{date}T{end_h:02d}:{m:02d}:00", "timeZone": TZ}
        else:
            start = {"date": date}
            end = {"date": date}
        summary, location, description = _parse_rdv_desc(desc)
        body = {"summary": summary, "start": start, "end": end,
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 1440}, {"method": "popup", "minutes": 60}]}}
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if self.dry:
            return "DRY_CAL_ID"
        try:
            return self.svc.events().insert(calendarId=self.calendar_id, body=body).execute()["id"]
        except Exception as e:
            print(f"  cal create failed ('{desc}'): {type(e).__name__}: {e}")
            return None

    def delete(self, eid):
        if self.dry:
            return
        try:
            self.svc.events().delete(calendarId=self.calendar_id, eventId=eid).execute()
        except Exception as e:
            print(f"  cal delete failed ({eid}): {type(e).__name__}")

    def update(self, eid, date, time, desc):
        """Re-sync an existing event: move a buried visio link out of the title
        into location/description. Patches only fields that differ. Returns the
        patched-body dict (or None if nothing to do / on error)."""
        summary, location, description = _parse_rdv_desc(desc)
        if location is None and description is None:
            return None
        try:
            ev = self.svc.events().get(calendarId=self.calendar_id, eventId=eid).execute()
        except Exception as e:
            print(f"  cal get failed ({eid}): {type(e).__name__}: {e}")
            return None
        body = {}
        if summary and ev.get("summary") != summary:
            body["summary"] = summary
        if location and ev.get("location") != location:
            body["location"] = location
        if description and ev.get("description") != description:
            body["description"] = description
        if not body:
            return None
        if self.dry:
            return body
        try:
            self.svc.events().patch(calendarId=self.calendar_id, eventId=eid, body=body).execute()
            return body
        except Exception as e:
            print(f"  cal patch failed ({eid}): {type(e).__name__}: {e}")
            return None


def project_file(path, tasks, cal, dry, log):
    text = open(path, encoding="utf-8").read()
    fm = front_matter(text)
    slug = fm.get("slug", os.path.basename(path)[:-3])
    tasklist = fm.get("tasklist")
    cal.calendar_id = fm.get("calendar") or "primary"
    new = text
    changed = False

    # --- Pending -> Tasks ---
    if tasklist:
        for line in section_lines(text, "Pending"):
            tid_m = TASKID_RE.search(line)
            if tid_m:
                if is_struck(line):
                    if tasks.complete(tasklist, tid_m.group(1)):
                        log.append(f"[{slug}] complete task {tid_m.group(1)}")
                continue
            if is_struck(line) or not clean_title(line):
                continue
            due_m = DUE_RE.search(line)
            title = clean_title(line)
            log.append(f"[{slug}] create task '{title}'" + (f" due {due_m.group(1)}" if due_m else "") + f" -> list '{tasklist}'")
            tid = tasks.create(tasklist, title, due_m.group(1) if due_m else None)
            if tid:
                new = new.replace(line, line.rstrip() + f" [task:{tid}]", 1)
                changed = True

    # --- RDV -> Calendar ---
    for line in section_lines(text, "RDV"):
        if line.strip() in ("- (aucun)", "-"):
            continue
        cid_m = CALID_RE.search(line)
        if cid_m:
            if is_struck(line):
                log.append(f"[{slug}] delete event {cid_m.group(1)}")
                cal.delete(cid_m.group(1))
            elif VISIO_SPLIT_RE.search(line):
                dtm = RDV_DT_RE.match(line.strip())
                if dtm:
                    d2, t2, desc2 = dtm.group(1), dtm.group(2), dtm.group(3).strip()
                    desc2 = ATTENDEE_RE.sub("", desc2)
                    desc2 = CALID_RE.sub("", desc2)
                    desc2 = TASKID_RE.sub("", desc2).strip()
                    body = cal.update(cid_m.group(1), d2, t2, desc2)
                    if body:
                        log.append(f"[{slug}] resync event {cid_m.group(1)}: " + ", ".join(body.keys()))
            continue
        if is_struck(line):
            continue
        if ATTENDEE_RE.search(line):
            log.append(f"NEEDS_CONFIRM [{slug}] external attendee, skipped: {line.strip()}")
            continue
        dt = RDV_DT_RE.match(line.strip())
        if not dt:
            continue
        date, time, desc = dt.group(1), dt.group(2), dt.group(3).strip()
        desc = ATTENDEE_RE.sub("", desc).strip()
        log.append(f"[{slug}] create event {date} {time or '(all-day)'} '{desc}'")
        cid = cal.create(date, time, desc)
        if cid:
            new = new.replace(line, line.rstrip() + f" [cal:{cid}]", 1)
            changed = True

    # --- Alarme -> phone-alarm (idempotent via [alarm-set]; retry si tel injoignable) ---
    today = datetime.date.today().isoformat()
    for line in section_lines(text, "Alarme"):
        if ALARMSET_RE.search(line):
            continue
        if is_struck(line):
            continue
        wk = ALARM_WEEKLY_RE.match(line.strip())
        dm = ALARM_DATE_RE.match(line.strip())
        silent, novib = _alarm_flags(line)
        if wk:
            toks = [d.strip()[:3].upper() for d in wk.group(1).split(",") if d.strip()]
            nums = [str(DAYMAP[d]) for d in toks if d in DAYMAP]
            if not nums:
                continue
            tm = wk.group(2); label = _alarm_label(wk.group(3))
            argv = ["--hour", str(int(tm[:2])), "--minute", tm[3:], "--label", label, "--days", ",".join(nums)]
            if silent: argv.append("--silent")
            if novib: argv.append("--no-vibrate")
            log.append(f"[{slug}] alarm weekly {','.join(toks)} {tm} '{label}'")
            if _run_phone_alarm(argv, dry, log, slug):
                new = new.replace(line, line.rstrip() + f" [alarm-set:{today}]", 1); changed = True
        elif dm:
            date, tm, rest = dm.group(1), dm.group(2), dm.group(3)
            label = _alarm_label(rest)
            if date > today:
                continue
            if date < today:
                log.append(f"[{slug}] alarm MISSED {date} {tm} '{label}'")
                new = new.replace(line, line.rstrip() + f" [alarm-missed:{today}]", 1); changed = True
                continue
            argv = ["--hour", str(int(tm[:2])), "--minute", tm[3:], "--label", label]
            if silent: argv.append("--silent")
            if novib: argv.append("--no-vibrate")
            log.append(f"[{slug}] alarm today {tm} '{label}'")
            if _run_phone_alarm(argv, dry, log, slug):
                new = new.replace(line, line.rstrip() + f" [alarm-set:{today}]", 1); changed = True

    if changed and not dry:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    tasks = Tasks(args.dry_run)
    cal = Calendar(args.dry_run)
    log, any_changed = [], False
    for path in sorted(glob.glob(os.path.join(TOPICS, "*.md"))):
        if os.path.basename(path).startswith("_"):
            continue
        try:
            if project_file(path, tasks, cal, args.dry_run, log):
                any_changed = True
        except Exception as e:
            log.append(f"ERROR projecting {os.path.basename(path)}: {type(e).__name__}: {e}")
    for line in log:
        print(line)
    if not log:
        print("nothing to project")
    if any_changed and not args.dry_run:
        subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "commit", "-m", "project: tasks/calendar"], cwd=ROOT, capture_output=True)
        print("committed ID write-backs")


if __name__ == "__main__":
    main()

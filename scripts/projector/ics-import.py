#!/usr/bin/env python3
"""ics-import.py : importe une invitation .ics (stdin) dans Google Calendar.

Pour importer une invitation reçue par mail (pièce jointe .ics) sans passer par l'interface de l'agenda.
Réutilise le jeton du projecteur de dossiers (gauth.py, même agenda).

Par VEVENT : cherche l'event par iCalUID ; absent -> events.import ;
présent -> patch des champs qui changent ; METHOD:CANCEL -> statut annulé.
Sortie : une ligne JSON {ok, events:[{action, summary, start, end, link, id}]}.
Options : --dry-run (ne touche pas à l'agenda), --calendar <id> (défaut primary).
"""
import sys, json, argparse, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icalendar import Calendar

TZ = os.environ.get("DOSSIERS_TZ", "UTC")
FIELDS = ("summary", "location", "description", "start", "end", "status", "sequence")


def _when(prop):
    """Propriété DTSTART/DTEND -> dict Google ({date} ou {dateTime,timeZone})."""
    v = prop.dt
    if isinstance(v, datetime.datetime):
        tzid = prop.params.get("TZID")
        if v.tzinfo is None:
            return {"dateTime": v.isoformat(), "timeZone": tzid or TZ}
        if tzid:
            return {"dateTime": v.replace(tzinfo=None).isoformat(), "timeZone": str(tzid)}
        return {"dateTime": v.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return {"date": v.isoformat()}


def _text(ev, key):
    v = ev.get(key)
    return str(v).strip() if v is not None else None


def events_from_ics(raw):
    cal = Calendar.from_ical(raw)
    method = str(cal.get("METHOD") or "REQUEST").upper()
    out = []
    for ev in cal.walk("VEVENT"):
        uid = _text(ev, "UID")
        if not uid:
            continue
        body = {"iCalUID": uid, "start": _when(ev["DTSTART"])}
        if ev.get("DTEND") is not None:
            body["end"] = _when(ev["DTEND"])
        elif ev.get("DURATION") is not None:
            end = ev["DTSTART"].dt + ev["DURATION"].dt
            body["end"] = _when(type("P", (), {"dt": end, "params": ev["DTSTART"].params})())
        else:
            body["end"] = dict(body["start"])
        for k in ("summary", "location", "description"):
            t = _text(ev, k.upper())
            if t:
                body[k] = t
        seq = ev.get("SEQUENCE")
        if seq is not None:
            body["sequence"] = int(seq)
        st = _text(ev, "STATUS")
        if method == "CANCEL" or (st and st.upper() == "CANCELLED"):
            body["status"] = "cancelled"
        elif st and st.upper() == "TENTATIVE":
            body["status"] = "tentative"
        else:
            body["status"] = "confirmed"
        rr = ev.get("RRULE")
        if rr is not None:
            body["recurrence"] = ["RRULE:" + rr.to_ical().decode()]
        out.append(body)
    return method, out


def _differs(ev, body):
    patch = {}
    for k in FIELDS:
        if k in body and ev.get(k) != body[k]:
            if k in ("start", "end"):
                # Google renvoie un offset ; on compare après normalisation grossière
                a, b = ev.get(k, {}), body[k]
                same = ("date" in a and a.get("date") == b.get("date")) or (
                    "dateTime" in a and b.get("dateTime") and a["dateTime"][:19] == b["dateTime"][:19]
                    and (not b.get("timeZone") or a.get("timeZone") == b.get("timeZone")))
                if same:
                    continue
            patch[k] = body[k]
    return patch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--calendar", default="primary")
    a = ap.parse_args()
    raw = sys.stdin.buffer.read()
    method, bodies = events_from_ics(raw)
    if not bodies:
        print(json.dumps({"ok": False, "error": "aucun VEVENT dans le fichier"}))
        return 2
    if a.dry_run:
        print(json.dumps({"ok": True, "dry": True, "method": method,
                          "events": [{"action": "dry", **b} for b in bodies]}, ensure_ascii=False))
        return 0
    from gauth import calendar_service
    svc = calendar_service()
    results = []
    for body in bodies:
        found = svc.events().list(calendarId=a.calendar, iCalUID=body["iCalUID"],
                                  showDeleted=True, maxResults=5).execute().get("items", [])
        found = [f for f in found if not f.get("recurringEventId")] or found
        if found:
            ev = found[0]
            patch = _differs(ev, body)
            if patch:
                ev = svc.events().patch(calendarId=a.calendar, eventId=ev["id"], body=patch).execute()
                action = "mis à jour" if body["status"] != "cancelled" else "annulé"
            else:
                action = "déjà à jour"
        else:
            if body["status"] == "cancelled":
                results.append({"action": "annulation ignorée (absent)", "summary": body.get("summary")})
                continue
            body.setdefault("reminders", {"useDefault": False, "overrides": [
                {"method": "popup", "minutes": 1440}, {"method": "popup", "minutes": 60}]})
            ev = svc.events().import_(calendarId=a.calendar, body=body).execute()
            action = "ajouté"
        results.append({"action": action, "summary": ev.get("summary"), "start": ev.get("start"),
                        "end": ev.get("end"), "link": ev.get("htmlLink"), "id": ev.get("id")})
    print(json.dumps({"ok": True, "method": method, "events": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        sys.exit(1)

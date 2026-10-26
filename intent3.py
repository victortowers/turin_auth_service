import re
from datetime import timedelta
import datetime as dt
import unicodedata

FMT        = "%Y-%m-%dT%H:%M"

WEEKDAY = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
           "sexta": 4, "sabado": 5, "domingo": 6}

REL    = r"depois de amanh[ãa]|amanh[ãa]|hoje"
WDS    = r"segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo"
PERIOD = r"manh[ãa]|tarde|noite|madrugada"
MARK   = r"[àa]s|at[ée]|pelas?|por volta"

UNIT = r"(?!\s*(?:min\w*|km|metros?|reais|pessoas|anos)\b)"

A = re.compile(
    r"\b(?:[àa]s|at[ée]|pelas?|por volta das?)\s+"
    r"(?<!\d)(\d{1,2})(?:[:h](\d{2}))?" + UNIT + r"(?!\d)", re.I)

B  = re.compile(r"(?<!\d)(\d{1,2})h(?:(\d{2}))?(?!\d)", re.I)
C  = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
# bare colon, lowest confidence ("18:30")

# ── PHASE 2 · what does the clock mean? ────────────────────────────
D = re.compile(
    r"cheg\w*|"
    r"\best(?:ar|ou|arei|aremo?s|á|ão|ive|iver|ivemo?s|ava|avam)\b", re.I)
# ARRIVE verb: chegar / estarei / estaremos / estivemos / estavam

E = re.compile(r"\bsai\w*|\bpart\w*|\bsa[íi]da\b", re.I)

E2 = re.compile(r"\b(?:vou|vai|vamos|ir(?:ei|á|ão|emos)?)\b", re.I)

H = re.compile(rf"\b(?:{REL})\b", re.I)
I = re.compile(rf"\b(?P<wd>{WDS})(?:[- ]?feira)?\b", re.I)
J = re.compile(rf"\b(?:d[ae]|à|a|pela)\s+({PERIOD})\b", re.I)

# prepositions that can introduce a PLACE — no de/da/do
PREP = r"ao|a|à|para|pra|pro|na|no|em"

G = (rf"{MARK}|{REL}|{WDS}|{PERIOD}|"
     r"cheg\w*|sai\w*|part\w*|sa[íi]da|ir(?:ei|á|ão|emos)?|vou|vai|vamos")

PLACE = re.compile(
    rf"\b(?:{PREP})\s+"
    rf"(?!(?:{REL}|{WDS}|{PERIOD})\b)"          # day/period word ≠ destination
    r"(.{2,40}?)(?=\s+(?:" + G + r")\b|\s*$)",  # stops at a G terminator or EOS
    re.I)

WEEKDAY = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
DEFAULT_HOUR = {"manha": 9, "tarde": 14, "noite": 20, "madrugada": 1}
BAD_PLACE    = {"noite", "tarde", "manha", "madrugada", "amanha", "hoje",
                "depois de amanha", "agora"}

BUFFER = 0.1

def flat(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

def day(text, now):
    m = H.search(text)
    if not m:
        return 0, None
    w = flat(m.group(0).strip())
    if w.startswith("depois"): return 2, "depois de amanha"
    if w.startswith("amanha"): return 1, "amanha"
    if w.startswith("hoje"):   return 0, "hoje"
    name  = flat(m.group(1))
    delta = (WEEKDAY[name] - now.weekday()) % 7
    return (delta or 7), name

NUM_PERIOD = re.compile(
    r"(?<!\d)(\d{1,2})(?::(\d{2}))?(?:\s*horas?)?\s+d[ae]\s+"
    r"(?:manh[ãa]|tarde|noite|madrugada)\b", re.I)

LADDER = (A, NUM_PERIOD, B, C)         # confidence order


def decode(h, mi):
    h, mi = int(h), int(mi or 0)
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def clock(s):
    """'às 18' | 'até 7:00' | '18h30' | '18:36' → 'HH:MM' | None"""
    if not s or not isinstance(s, str):
        return None
    for rx in LADDER:
        m = rx.search(s)
        if m:
            v = decode(m.group(1), m.group(2))
            if v:
                return v        # ← must be inside `if v`, see below
    return None

def period(text):
        m = I.search(text)
        if not m: return None
        p = flat(m.group(1))
        return "manha" if p.startswith("manh") else p


def fix_hour(h, p):
        """period word → 24h, or contradiction"""
        if p is None: return h, None
        if p == "tarde":
            if 1 <= h <= 11: h += 12
            return (h, None) if 12 <= h <= 19 else (None, "contradictory_period")
        if p == "noite":
            if 6 <= h <= 11:  h += 12
            elif h == 12:     h = 0
            return (h, None) if (h >= 18 or h <= 5) else (None, "contradictory_period")
        if p == "manha":
            return (h, None) if h <= 12 else (None, "contradictory_period")
        return (h, None) if h <= 5 else (None, "contradictory_period")

def _clock(text, now, day, period):
    m = None
    for rx in (A, B, C):
        m = rx.search(text)
        if m: break
    if m is None:
        return None, None                      # no clock at all

    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return None, "invalid_time"

    h, err = _fix_hour(h, period)
    if err:
        return None, err

    base = (now + timedelta(days=day)).replace(
        hour=h, minute=mi, second=0, microsecond=0)

    if day == 0 and base < now:                # explicit "hoje" that already passed
        return None, "in_the_past"
    return base, None

def parse2(text, time):
    now = dt.datetime.now()
    print(now)

    f1 = PLACE.search(text)
    a1 = A.search(text)
    b1 = B.search(text)
    c1 = C.search(text)
    d1 = bool(D.search(text))
    e1 = bool(E.search(text))
    e2 = E2.search(text)

    h1 = H.search(text)
    i1 = I.search(text)
    j1 = J.search(text)

    b2 = clock(b1.group(0))
    print(a1, b1, c1, d1, e1,e2, f1, h1, i1, j1)

    return {
        "time": b2 if b2 else c1.group(0) if c1 else None,
        "time_limit": a1.group(0) if a1 else None,
        "time_heuristic": j1.group(1) if j1 else None,
        "time_heuristic_day": h1.group(1) if h1 else None,
        "action": "chegar" if d1 else "sair" if e1 else None,
        "destination": f1.group(1) if f1 else None,
    }

prompt = "vou ao cinema às 18"
print(prompt)
print(parse2(prompt, dt.time()))

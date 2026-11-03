
import csv
import json
import re
import sys
import time
import unicodedata

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

FMT = "%Y-%m-%dT%H:%M"

WEEKDAYS = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}

RELATIVE_DAYS = {
    ("hoje",): 0,
    ("amanha",): 1,
    ("depois", "de", "amanha"): 2,
}

P = {
    ("de", "manha"): "manha",
    ("da", "manha"): "manha",
    ("a", "tarde"): "tarde",
    ("de", "tarde"): "tarde",
    ("da", "tarde"): "tarde",
    ("a", "noite"): "noite",
    ("de", "noite"): "noite",
    ("da", "noite"): "noite",
    ("de", "madrugada"): "madrugada",
    ("da", "madrugada"): "madrugada",
}

# These are exact token matches, not substring matches.
A = {
    "chegar", "chego", "chega", "cheguei", "chegou",
    "chegando", "chegara", "chegarei", "chegarao",
    "estarei", "estaremos", "estarao",
    "estava", "estavam", "esteve", "estive",
}

D = {
    "sair", "saio", "sai", "saia", "saindo",
    "sairei", "saira", "sairao", "saida",
    "partir", "parto", "partiu", "partindo",
    "partirei", "partira", "partirao",
}

I = {
    "vou", "vai", "vamos", "irei", "ira", "irao", "iremos"
}

P = {
    "ao", "a", "para", "pra", "pro", "na", "no", "em"
}

TIME_MARKERS = {
    ("as",),
    ("ate",),
    ("pelas",),
    ("pela",),
    ("por", "volta"),
}

TOKEN_RE = re.compile(
    r"\d{1,2}(?:[:h]\d{2})?"
    r"|[^\W\d_]+"
    r"|\d+"
    r"|[^\w\s]",
    re.UNICODE | re.IGNORECASE,
)

BUFFER = 0.1

def normalize_word(text):
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in text
        if unicodedata.category(char) != "Mn"
    )


@dataclass
class Token:
    value: str
    raw: str
    start: int
    end: int


def tokenize(text):
    result = []

    for match in TOKEN_RE.finditer(text):
        raw = match.group(0)

        result.append(
            Token(
                value=normalize_word(raw),
                raw=raw,
                start=match.start(),
                end=match.end(),
            )
        )

    return result

def words(tokens):
    return [token.value for token in tokens]

def find_phrases(tokens, phrases):
    found = []
    i = 0

    while i < len(tokens):
        match = None

        for phrase, value in sorted(
            phrases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            end = i + 1

            if tuple(tokens[i:end]) == phrase:
                match = (i, end, value)
                break

        if match:
            found.append(match)
            i = match[1]
        else:
            i += 1

    return found

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


def error_handler(err1):
    return {
        "error": "error",
        "message": err1,
    }

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

def time_period(time):
    try:
        hora = dt.time.fromisoformat(time)
        if hora < dt.time(5):
            return "madrugada"

        elif hora < dt.time(12):
            return "manhã"

        elif hora < dt.time(18):
            return "tarde"

        elif hora >= dt.time(18):
            return "noite"

    except Exception as e:
        print("Error has occured", e)
        raise Exception(e)


def parse2(text):
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

    candidate = a1 or b1 or c1
    a2 = clock(candidate.group(0)) if candidate else None
    print(a1, b1, c1, d1, e1,e2, f1, h1, i1, j1)

    return {
        "time": a2,
        "time_limit": a1.group(0) if a1 else None,
        "time_heuristic": j1.group(1) if j1 else time_period(a2),
        "time_heuristic_day": h1.group(0) if h1 else None,
        "action": "chegar" if d1 else "sair" if e1 else None,
        "action2": e2.group(0) if e2 else None,
        "destination": f1.group(1) if f1 else None,
        "compute_time": dt.datetime.now() - now,
        "weekday": i1.group("wd") if i1 else None,
    }

prompt = "vou ao cinema às 18 horas"
print(prompt)
print(parse2(prompt))

import time
N = 20000
t = time.perf_counter()
for _ in range(N): print(parse2("vou chegar às 7 da noite no shopping"))
print((time.perf_counter() - t) / N * 1e6, "µs/call")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default: test one prompt interactively.
        prompt = input("Prompt: ")
        print(parse2(prompt))

    else:
        path = Path(sys.argv[1])

        if path.suffix.lower() == ".txt":
            with path.open(encoding="utf-8-sig") as f:
                prompts = [
                    line.strip()
                    for line in f
                    if line.strip()
                ]

        elif path.suffix.lower() == ".csv":
            with path.open(
                encoding="utf-8-sig", newline=""
            ) as f:
                prompts = [
                    row["prompt"].strip()
                    for row in csv.DictReader(f)
                    if row.get("prompt", "").strip()
                ]

        else:
            raise ValueError("Use a .txt or .csv file")

        for i, prompt in enumerate(prompts, 1):
            print(f"\n--- Test {i}: {prompt}")
            result = parse2(prompt)
            print(result)
            has_error = any(
                isinstance(value, dict) and "error" in value
                for value in result.values()
            )

            if has_error:
                print(f"\n--- Test {i}: {prompt}")
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

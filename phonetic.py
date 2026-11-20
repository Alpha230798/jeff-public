"""Sound-based matching and personal spelling memory for informally written Mauritian Creole.

Most people write Creole the way it sounds, so one word has many spellings:
    manze / manze / manje / manger / manG      -> manze  (to eat)
    korek / corec / correct / krk              -> korek  (OK, correct)
    rode / rod / roder / roD                   -> rode   (to seek)

Three tricks are used, from strongest to weakest:
  1. learned    : a spelling the user has already confirmed (spelling memory).
  2. sound      : both words reduce to the same sound key (e.g. "corec" == "korek").
                  French source words from the dictionary are indexed too, so "manger" finds "manze".
  3. skeleton   : SMS-style consonant-only writing ("krk") matches words with the same consonants.
And one assumption, to be confirmed with the user:
  * A capital letter inside a lowercase word is read as its French letter name:
    manG = man + "jé" = manze ; roD = ro + "dé" = rode.

Use:
    idx = SpellingIndex(entries, load_variants())
    idx.hints_block("mo pe manG enn ti dipen")   # text to attach to the message sent to the model
    idx.learn("krk", "korek")                    # after the user confirms a reading
"""
import json
import re
import time
import unicodedata
from pathlib import Path

HOME_DIR = Path.home() / ".jeff"
VARIANTS_PATH = HOME_DIR / "spelling_variants.json"
SAMPLES_PATH = HOME_DIR / "writing_samples.jsonl"

LETTER_NAMES = {
    "b": "be", "c": "se", "d": "de", "f": "ef", "g": "ze", "j": "zi", "k": "ka",
    "l": "el", "m": "em", "n": "en", "p": "pe", "q": "ku", "r": "er", "s": "es",
    "t": "te", "v": "ve", "x": "iks", "z": "zed",
}

SKIP = set("mo to li nu zot ti pe pa enn la ek ar dan pu ki sa me si ena bann tu kot kan finn so "
           "the and you for are not but with this that have what how why when ok yes jeff".split())

TOKEN = re.compile(r"[A-Za-z\u00C0-\u00FF']+")
HEAD = re.compile(r"^([a-z][a-z'\-]*)(?: \(\d\))?(?: \(([^)]*)\))?(?: (\[[^\]]*\]))?")


def strip_accents(s):
    s = unicodedata.normalize("NFKD", s.replace("\u2019", "'"))
    return "".join(c for c in s if not unicodedata.combining(c))


def expand_letter_names(token):
    """manG -> manze, roD -> rode. Only for tokens that mix lower and upper case:
    capitals after the first letter are read as French letter names."""
    t = strip_accents(token)
    if not (any(c.islower() for c in t) and any(c.isupper() for c in t[1:])):
        return t
    out = []
    for i, c in enumerate(t):
        if i > 0 and c.isupper() and c.lower() in LETTER_NAMES:
            out.append(LETTER_NAMES[c.lower()])
        else:
            out.append(c)
    return "".join(out)


def phon(word):
    """Reduce a spelling (French-style, Creole-style or in between) to a rough sound key."""
    w = re.sub(r"[^a-z]", "", strip_accents(word).lower())
    w = re.sub(r"eau|au", "o", w)
    w = w.replace("ou", "u").replace("oi", "wa")
    w = re.sub(r"ai|ei", "e", w)
    w = w.replace("ph", "f").replace("th", "t")
    w = re.sub(r"ch|sh", "S", w)
    w = w.replace("gn", "ny")
    w = re.sub(r"qu|ck|q", "k", w)
    w = re.sub(r"g(?=[eiy])", "z", w).replace("j", "z")
    w = re.sub(r"c(?=[eiy])", "s", w).replace("c", "k")
    w = w.replace("x", "ks").replace("h", "")
    w = w.replace("tion", "syon")
    w = re.sub(r"(.)\1+", r"\1", w)
    w = re.sub(r"(er|ez)$", "e", w)
    w = re.sub(r"(?<=[^aeiou])[tsdx]$", "", w)
    w = re.sub(r"(?<=[aeiou])[tsx]$", "", w)
    return w


def skeleton(word):
    """Consonants only, for SMS-style writing (krk, mnz, rd)."""
    return re.sub(r"[aeiouwy]", "", phon(word))


def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _vowel_count(s):
    return sum(c in "aeiou" for c in strip_accents(s).lower())


class SpellingIndex:
    def __init__(self, entries, variants=None):
        self.entries = entries
        self.variants = dict(variants or {})
        self.heads = {}
        self.by_phon = {}
        self.by_skel = {}
        for i, e in enumerate(entries):
            m = HEAD.match(e.lower())
            if not m:
                continue
            head, paren, bracket = m.groups()
            self.heads.setdefault(head, []).append(i)
            forms = [head]
            for v in (paren or "").split(","):
                v = v.strip()
                if v and " " not in v and not v.isdigit():
                    forms.append(v)
                    self.heads.setdefault(v, []).append(i)
            fm = re.search(r"fre ([a-z]+)\]", strip_accents(bracket or ""))
            if fm:
                forms.append(fm.group(1))
            for f in forms:
                p = phon(f)
                if p:
                    self.by_phon.setdefault(p, []).append((i, f))
                s = skeleton(f)
                if len(s) >= 2:
                    self.by_skel.setdefault(s, []).append((i, f))

    def learn(self, variant, canonical, path=VARIANTS_PATH):
        """Remember that the user writes `variant` for the Creole word `canonical`."""
        self.variants[strip_accents(variant).lower()] = canonical.lower()
        save_variants(self.variants, path)

    def candidates(self, token, limit=3):
        expanded = expand_letter_names(token)
        key = expanded.lower()
        raw_key = strip_accents(token).lower()
        found = {}

        def add(i, tier, dist, why, form):
            if i not in found or (tier, dist) < found[i][:2]:
                found[i] = (tier, dist, why, form)

        target = self.variants.get(raw_key) or self.variants.get(key)
        for i in self.heads.get(target or "", []):
            add(i, 0, 0, "learned", target)
        p = phon(expanded)
        for i, f in self.by_phon.get(p, []):
            add(i, 1, levenshtein(key, f), "sound", f)
        if _vowel_count(expanded) <= 1 and not token[:1].isupper():
            s = skeleton(expanded)
            if len(s) >= 2:
                for i, f in self.by_skel.get(s, []):
                    if abs(len(phon(f)) - len(p)) <= 4:
                        add(i, 2, levenshtein(p, phon(f)), "skeleton", f)
        ranked = sorted(found.items(), key=lambda kv: kv[1][:2])[:limit]
        return [{
            "headword": HEAD.match(self.entries[i].lower()).group(1),
            "entry": self.entries[i],
            "why": why,
            "form": form,
        } for i, (_, _, why, form) in ranked]

    def interpret(self, text, limit=2):
        out = []
        for tok in TOKEN.findall(text):
            low = strip_accents(tok).lower()
            rebus = expand_letter_names(tok).lower() != low
            if len(low) < 2 or low in SKIP:
                continue
            if low in self.heads and not rebus and low not in self.variants:
                continue
            c = self.candidates(tok, limit)
            if c:
                out.append((tok, c))
        return out

    def hints_block(self, text, max_tokens=8):
        lines = []
        for tok, cands in self.interpret(text)[:max_tokens]:
            unique_heads = {candidate["headword"] for candidate in cands}
            rebus = expand_letter_names(tok).lower() != strip_accents(tok).lower()
            if not rebus and len(unique_heads) > 1:
                continue
            parts = []
            for c in cands:
                rest = c["entry"].split(":", 1)[1].strip() if ":" in c["entry"] else ""
                gloss = re.split(r"\.\s+(?=[A-Z])", rest, maxsplit=1)[0][:45]
                parts.append(f"{c['headword']} ({gloss}) [{c['why']}]")
            lines.append(f'- "{tok}" probably = ' + " / ".join(parts))
        if not lines:
            return ""
        return (
            "<spelling_hints>\nThe user writes Creole by sound. These words are probably spelled informally:\n"
            + "\n".join(lines)
            + "\n</spelling_hints>"
        )


def load_variants(path=VARIANTS_PATH):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_variants(variants, path=VARIANTS_PATH):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(variants, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def forget_variant(variant, path=VARIANTS_PATH):
    """Delete one user-confirmed spelling, returning whether it existed."""
    variants = load_variants(path)
    key = strip_accents(variant).lower()
    if key not in variants:
        return False
    del variants[key]
    save_variants(variants, path)
    return True


def log_message(text, path=SAMPLES_PATH):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": int(time.time()), "text": text}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys
    here = Path(__file__).parent
    idx = SpellingIndex(json.loads((here / "dictionary.json").read_text(encoding="utf-8")), load_variants())
    msg = " ".join(sys.argv[1:]) or "mo pe manG enn ti dipen epi roD mo kle, krk sa"
    print(idx.hints_block(msg) or "(no hints)")

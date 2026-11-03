"""Narration text -> cooking steps with honest quantity ranges. No network, no LLM."""
import re, difflib

_BN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
TASTE, SARHE, AND = "<taste>", {"sarhe", "saade", "সাড়ে"}, {"ar", "aar", "আর", "ও", "and", "aur", "और"}


def _table(rows):
    out = {}
    for val, words in rows:
        for w in words.split():
            out[w] = val
    return out


NUM = _table([(1, "ek এক ekta একটা একটি akta"), (2, "dui duto দুই দুটো দুটি do dute"), (3, "tin তিন teen tinte"),
              (4, "char চার chaar"), (5, "panch pach পাঁচ paanch"), (6, "chhoy choy ছয় chhe"), (7, "saat sat সাত"),
              (8, "aat আট aath"), (9, "noy নয় nau"), (10, "dosh dos দশ das"), (15, "panero পনেরো"),
              (20, "bish বিশ"), (30, "tirish তিরিশ"), (0.5, "adha aadha adh আধা আধ half"),
              (1.5, "der dedh দেড়"), (2.5, "arai dhai আড়াই")])
UNIT = _table([("muthi", "muthi mutho muthhi mutthi মুঠো মুঠি মুঠা"), ("chimti", "chimti chimte chimta chutki চিমটি চিমটে pinch"),
               ("cup", "kap cup কাপ"), ("spoon", "chamoch chamach chamcha spoon চামচ চামচে"), ("tsp", "tsp teaspoon"),
               ("tbsp", "tbsp tablespoon"), ("bowl", "bati বাটি katori"), ("glass", "glass গ্লাস গেলাস gelas"),
               ("poa", "poa পোয়া"), ("chhatak", "chhatak chhotak chatak ছটাক"), ("ser", "ser seer সের"),
               ("g", "g gm gram grams গ্রাম"), ("kg", "kg kilo কেজি কিলো"), ("ml", "ml মিলি"),
               ("litre", "litre liter লিটার")])
DUR = _table([("min", "minute minutes min minit মিনিট"), ("hour", "ghonta ghanta hour ঘণ্টা ঘন্টা")])
ING = _table([(("rice", "grain"), "chal চাল chawal rice"), (("lentils", "grain"), "dal ডাল daal"),
              (("flour", "flour"), "atta আটা moyda ময়দা maida besan বেসন"), (("salt", "salt"), "nun নুন lobon লবণ namak salt"),
              (("sugar", "sugar"), "chini চিনি sugar cheeni"), (("oil", "liquid"), "tel তেল oil"), (("ghee", "liquid"), "ghee ঘি"),
              (("water", "liquid"), "jol জল pani পানি water"), (("milk", "liquid"), "dudh দুধ milk"),
              (("turmeric", "spice"), "holud হলুদ haldi"), (("chilli", "spice"), "lonka লঙ্কা lanka mirch"),
              (("cumin", "spice"), "jeere jeera জিরে জিরা"), (("onion", "produce"), "peyaj পেঁয়াজ onion"),
              (("potato", "produce"), "alu আলু"), (("tomato", "produce"), "tomato টমেটো"), (("garlic", "produce"), "roshun রসুন"),
              (("ginger", "produce"), "ada আদা"), (("coriander leaves", "herb"), "dhone ধনে dhonepata ধনেপাতা")])

# STARTING ESTIMATES, not measurements. (unit, ingredient class) -> (low, high, output unit). Calibrate to replace them.
D = {("muthi", "grain"): (30, 50, "g"), ("muthi", "flour"): (25, 45, "g"), ("muthi", "herb"): (5, 15, "g"), ("muthi", "*"): (25, 50, "g"),
     ("chimti", "salt"): (.3, 1, "g"), ("chimti", "spice"): (.2, .8, "g"), ("chimti", "sugar"): (.5, 1.5, "g"), ("chimti", "*"): (.3, 1, "g"),
     ("cup", "grain"): (120, 200, "g"), ("cup", "flour"): (90, 130, "g"), ("cup", "sugar"): (150, 220, "g"), ("cup", "*"): (150, 240, "ml"),
     ("spoon", "liquid"): (5, 15, "ml"), ("spoon", "*"): (3, 15, "g"), ("tsp", "liquid"): (4, 6, "ml"), ("tsp", "*"): (2, 6, "g"),
     ("tbsp", "liquid"): (12, 15, "ml"), ("tbsp", "*"): (8, 18, "g"), ("bowl", "liquid"): (150, 250, "ml"), ("bowl", "*"): (120, 220, "g"),
     ("glass", "liquid"): (200, 300, "ml"), ("glass", "*"): (150, 220, "g"), ("poa", "liquid"): (220, 250, "ml"), ("poa", "*"): (220, 250, "g"),
     ("chhatak", "liquid"): (55, 62, "ml"), ("chhatak", "*"): (55, 62, "g"), ("ser", "liquid"): (930, 1000, "ml"), ("ser", "*"): (930, 1000, "g")}
EXACT = {"g": (1, "g"), "kg": (1000, "g"), "ml": (1, "ml"), "litre": (1000, "ml")}
BREAK = [" uske baad ", " after that ", " tarpore ", " tarpor ", " erpor ", " erpore ", " এরপর ", " তারপরে ", " তারপর ", " phir ", " then ", " ebar ", " এবার "]
TASTE_P = ["jemon lage", "joto lage", "swad moto", "swadmoto", "pariman moto", "যেমন লাগে", "যতটা লাগে", "স্বাদমতো", "স্বাদ মতো", "to taste", "ektu", "একটু"]
UNIT_P = [("choto chamoch", " tsp "), ("chhoto chamoch", " tsp "), ("ছোট চামচ", " tsp "), ("boro chamoch", " tbsp "), ("বড় চামচ", " tbsp ")]
SUF = ["টুকু", "গুলো", "খানা", "টা", "টি", "tuku", "gulo", "khana", "ta", "ti"]
CMD = [("prev", "back previous ager আগের pichla पिछला pichone পিছনে"), ("repeat", "repeat abar আবার dobara दोबारा phirse"),
       ("stop", "stop thamo থামো ruko रुको"), ("next", "next porer পরের tarpor তারপর agla अगला hoyeche হয়েছে done ok")]


def r(x):
    return round(x, 1) if x < 10 else int(round(x))


def norm(t):
    t = t.translate(_BN).lower()
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"[।!?;:()\"“”\n]", " | ", t)
    t = re.sub(r"\.(?!\d)", " | ", t).replace(",", " , ")
    t = " " + re.sub(r"\s+", " ", t) + " "
    for a, b in UNIT_P:
        t = t.replace(a, b)
    for p in TASTE_P:
        t = t.replace(" " + p + " ", " " + TASTE + " ")
    for p in BREAK:
        t = t.replace(p, " | ")
    return t


def num(tok):
    if tok in NUM:
        return NUM[tok]
    try:
        if "/" in tok:
            a, b = tok.split("/")
            return float(a) / float(b)
        return float(tok)
    except ValueError:
        return None


def look(tok, table):
    for t in [tok] + [tok[:-len(s)] for s in SUF if tok.endswith(s) and len(tok) > len(s) + 1]:
        if t in table:
            return table[t]
    if tok.isascii() and tok.isalpha() and len(tok) >= 4:
        c = difflib.get_close_matches(tok, [k for k in table if k.isascii() and len(k) >= 4], 1, 0.85)
        if c:
            return table[c[0]]
    return None


def measure(qty, unit, key, cls, cal):
    if unit in EXACT:
        f, u = EXACT[unit]
        return dict(lo=r(qty * f), hi=r(qty * f), unit=u, basis="exact")
    d = D.get((unit, cls)) or D.get((unit, "*"))
    m = (cal or {}).get(f"{unit}|{key}")
    if m and d:  # one weighing: +-15%; several: observed spread +-5%
        lo, hi = (m[0] * .85, m[0] * 1.15) if len(m) == 1 else (min(m) * .95, max(m) * 1.05)
        return dict(lo=r(lo * qty), hi=r(hi * qty), unit=d[2], basis="yours")
    if not d:
        return None
    return dict(lo=r(d[0] * qty), hi=r(d[1] * qty), unit=d[2], basis="typical")


def clause(toks, cal):
    nums, unit, ing, dur, taste, i = [], None, None, None, False, 0
    while i < len(toks):
        w = toks[i]
        if w == TASTE:
            taste = True
        elif w in SARHE and i + 1 < len(toks) and num(toks[i + 1]) is not None:
            nums.append((i, num(toks[i + 1]) + .5)); i += 1
        elif num(w) is not None:
            nums.append((i, num(w)))
        elif look(w, DUR):
            if nums and nums[-1][0] == i - 1:
                dur = (dur or 0) + nums.pop()[1] * (60 if look(w, DUR) == "hour" else 1)
        elif look(w, UNIT):
            unit = unit or (look(w, UNIT), i)
        elif look(w, ING):
            ing = ing or look(w, ING)
        i += 1
    qty = None
    if nums:
        before = [n for j, n in nums if unit and j < unit[1]]
        qty = before[-1] if before else nums[0][1]
    key, cls = (ing[0], ing[1]) if ing else ("any", "*")
    item = None
    if unit and qty is not None:
        item = dict(qty=qty, unit=unit[0], ingredient=ing[0] if ing else None, range=measure(qty, unit[0], key, cls, cal))
    elif ing and qty is not None:
        item = dict(qty=qty, unit="pc", ingredient=ing[0], range=None)
    elif ing and taste:
        item = dict(qty=None, unit=None, ingredient=ing[0], range=None, to_taste=True)
    return item, dur


def parse(text, cal=None):
    steps = []
    for chunk in norm(text).split("|"):
        toks = chunk.split()
        if not toks:
            continue
        items, dur, cur = [], None, []
        for w in toks + [","]:
            if w == "," or w in AND:
                if cur:
                    it, d = clause(cur, cal)
                    items += [it] if it else []
                    dur = (dur or 0) + d if d else dur
                    cur = []
            else:
                cur.append(w)
        steps.append(dict(i=len(steps) + 1, text=chunk.replace(" , ", ", ").replace(TASTE, "to taste").strip(), items=items, timer_min=dur and r(dur)))
    return steps


def command(text):
    toks = set(norm(text).split())
    return next((c for c, ws in CMD if toks & set(ws.split())), None)

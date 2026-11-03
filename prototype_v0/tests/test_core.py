import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from core import parse, command


def test_basic():
    s = parse("ek muthi chal, ek chimti nun, jol ta jemon lage")
    assert len(s) == 1
    rice, salt, water = s[0]["items"]
    assert rice["ingredient"] == "rice" and (rice["range"]["lo"], rice["range"]["hi"]) == (30, 50)
    assert salt["range"]["unit"] == "g" and water["to_taste"]


def test_bengali_script_and_halves():
    it = parse("আড়াই কাপ জল দাও")[0]["items"][0]
    assert it["qty"] == 2.5 and it["ingredient"] == "water" and it["range"]["lo"] == 375
    assert parse("sarhe tin chamoch tel")[0]["items"][0]["qty"] == 3.5


def test_calibration_narrows():
    r = parse("ek muthi chal", {"muthi|rice": [38]})[0]["items"][0]["range"]
    assert (r["lo"], r["hi"], r["basis"]) == (32, 44, "yours")


def test_timer_and_split():
    s = parse("dosh minute dhimi anche ranna koro tarpor ek muthi chal dao")
    assert s[0]["timer_min"] == 10 and len(s) == 2


def test_spelling_variants_and_commands():
    assert parse("ek mutho chal")[0]["items"][0]["unit"] == "muthi"
    assert command("পরের") == "next" and command("abar bolo") == "repeat"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)

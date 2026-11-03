#!/usr/bin/env python3
"""Evidence report from git history: commits, lines and folders touched per author.
Supports, never replaces, the human-written contributions/LEDGER.md.
Usage: python scripts/contrib_report.py [output.md]"""
import collections
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "contributions/GIT_REPORT.md"
    raw = git("log", "--no-merges", "--numstat", "--date=short", "--format=@@%an|%ae|%ad")
    people = collections.defaultdict(lambda: {"commits": 0, "add": 0, "del": 0, "areas": collections.Counter(), "first": "9999", "last": "0000"})
    cur = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            name, email, day = line[2:].split("|", 2)
            cur = people[f"{name} <{email}>"]
            cur["commits"] += 1
            cur["first"], cur["last"] = min(cur["first"], day), max(cur["last"], day)
        elif line.strip() and cur is not None:
            a, d, path = line.split("\t", 2)
            if a == "-":
                continue
            cur["add"] += int(a)
            cur["del"] += int(d)
            cur["areas"][path.split("/")[0] if "/" in path else "(root)"] += int(a) + int(d)
    rows = ["# Git report (evidence only)", "", "Lines of code are a weak signal; the ledger is the record of who did what.", "",
            "| Author | Commits | Lines + | Lines - | First | Last | Top areas |", "|---|---|---|---|---|---|---|"]
    for who, p in sorted(people.items(), key=lambda kv: -kv[1]["commits"]):
        top = ", ".join(f"{k} ({v})" for k, v in p["areas"].most_common(4))
        rows.append(f"| {who} | {p['commits']} | {p['add']} | {p['del']} | {p['first']} | {p['last']} | {top} |")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print(f"wrote {out} for {len(people)} author(s)")


if __name__ == "__main__":
    main()

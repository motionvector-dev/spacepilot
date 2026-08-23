#!/usr/bin/env python3
"""Re-check every registry number that claims to have been measured.

A `checked:` date is a promise that somebody looked. This is how that promise
stays true: it re-resolves each repo against the Hub, re-sums the files the
variant's patterns actually select, and reports any download size that has
drifted. Run it before publishing anything derived from the registry.

Sizes are re-summed **at the pinned revision**, not against whatever the repo's
default branch holds today. Checking against main would make the number drift
every time an author pushes, and would quietly describe bytes nobody who
follows the registry will ever download.

An unpinned variant fails the gate. It is allowed to exist — a variant has to
be describable before anyone resolves a SHA for it — but it must never leave
the repo looking like a pinned one, so shipping past it takes
`--allow-unpinned` and says so out loud.

    python tools/verify_registry.py                  # report
    python tools/verify_registry.py --fix            # rewrite drifted sizes and dates
    python tools/verify_registry.py --allow-unpinned # warn on unpinned, do not fail

Exits non-zero when something is wrong, so it can gate a release.
"""

import argparse
import datetime as dt
import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spacepilot.pluto.registry import REGISTRY_DIR, load_registry  # noqa: E402

TOLERANCE = 0.02  # Hub totals move slightly as repos are repacked.


def selected_bytes(api, repo: str, patterns, revision=None):
    info = api.model_info(repo, revision=revision, files_metadata=True)
    siblings = info.siblings or []
    if patterns:
        siblings = [f for f in siblings
                    if any(fnmatch.fnmatch(f.rfilename, p) for p in patterns)]
        if not siblings:
            return None, "no file matched the patterns — the checkpoint was probably renamed"
    return sum(f.size or 0 for f in siblings), None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="rewrite drifted sizes in place")
    ap.add_argument("--allow-unpinned", action="store_true",
                    help="report variants with no revision instead of failing on them")
    args = ap.parse_args()

    from huggingface_hub import HfApi
    api = HfApi()
    today = dt.date.today().isoformat()

    reg = load_registry()
    problems, fixes = [], []

    unpinned = reg.unpinned()

    for v in reg.variants:
        try:
            actual, err = selected_bytes(api, v.repo, v.files, v.revision)
        except Exception as e:
            problems.append(f"{v.id}: {v.repo} could not be read — {e}")
            continue
        if err:
            problems.append(f"{v.id}: {err}")
            continue

        declared = int(v.download.value)
        drift = abs(actual - declared) / max(declared, 1)
        if drift > TOLERANCE:
            problems.append(
                f"{v.id}: download is {actual/2**30:.2f} GB, registry says "
                f"{declared/2**30:.2f} GB ({drift:.0%} out)")
            fixes.append((v.id, declared, actual))
        else:
            pin = v.revision[:12] if v.revision else "UNPINNED"
            print(f"  ok  {v.id:34s} {actual/2**30:7.2f} GB  {pin}")

        if v.working_set.source == "estimated" and not v.speed:
            print(f"      {'':34s} no measured footprint or speed on any machine")

    if args.fix and fixes:
        for path in sorted(REGISTRY_DIR.glob("*.yaml")):
            text = path.read_text()
            for vid, old, new in fixes:
                # Only rewrite the value inside the block that declares this id.
                block = re.search(rf"(  - id: {re.escape(vid)}\n.*?)(?=\n  - id: |\Z)", text, re.S)
                if not block:
                    continue
                patched = block.group(1)
                patched = patched.replace(f"value: {old}", f"value: {new}")
                patched = re.sub(r'(download:\n(?:.*\n)*?\s+checked: ")[^"]+(")',
                                 rf"\g<1>{today}\g<2>", patched, count=1)
                text = text.replace(block.group(1), patched)
            path.write_text(text)
        print(f"\nrewrote {len(fixes)} size(s) and stamped them {today}")
        return 0

    if unpinned:
        print(f"\n  {len(unpinned)} variant(s) carry no revision — each one names a repo "
              f"that is free to change under it, so any measurement of them\n"
              f"  describes weights that cannot be fetched again:")
        for v in unpinned:
            print(f"    ?? {v.id:34s} {v.repo}")
        if not args.allow_unpinned:
            problems.append(
                f"{len(unpinned)} unpinned variant(s); pin them or pass --allow-unpinned")

    if problems:
        print("\n" + "\n".join(f"  !! {p}" for p in problems))
        print(f"\n{len(problems)} problem(s). Re-run with --fix to update sizes.")
        return 1

    print(f"\nall {len(reg.variants)} variants verified against the Hub "
          f"at their pinned revisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""MERGE ONE HALF OF THE SYSTEM 1 vs SYSTEM 2 RUN. Amendment 3 runs one model at a time, so a half is
several promptfoo exports. This joins them into the one file analyze_s1s2.py reads.

    python3 merge_s1s2.py -o results.s1s2.A.json run/nemotron.A.json run/luna.A.json ...

A file named <x>.retry.json next to <x>.json holds the one retry of that file's errored items
(promptfoo --filter-errors-only). A retried item replaces the errored one only if the retry did not
error too; the count of retried and still-errored items is printed and written to the merged file's
"merge" block, so the report can state it. Stdlib only. Nothing else is changed.
"""
import argparse, json, pathlib


def rows(doc):
    return doc["results"]["results"]


def key(x):
    # By the probe's own variables, not testIdx: a filtered retry renumbers its tests.
    return (x["provider"].get("label"), x["prompt"].get("label"), json.dumps(x.get("vars"), sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    merged, info = None, []
    for f in a.files:
        p = pathlib.Path(f)
        doc = json.loads(p.read_text())
        rs = rows(doc)
        errored = [x for x in rs if x.get("error")]
        fixed = still = 0
        rt = p.with_name(p.stem + ".retry.json")
        if errored and rt.exists():
            retry = {key(x): x for x in rows(json.loads(rt.read_text()))}
            for i, x in enumerate(rs):
                if x.get("error"):
                    y = retry.get(key(x))
                    if y is not None and not y.get("error"):
                        rs[i] = y
                        fixed += 1
                    else:
                        still += 1
        else:
            still = len(errored)
        info.append({"file": p.name, "items": len(rs), "errored_first_pass": len(errored),
                     "replaced_by_retry": fixed, "still_errored": still})
        if merged is None:
            merged = doc
        else:
            rows(merged).extend(rs)
    merged["merge"] = info
    pathlib.Path(a.out).write_text(json.dumps(merged, indent=1))
    for i in info:
        print(i)
    print("wrote", a.out, "items", len(rows(merged)))


if __name__ == "__main__":
    main()

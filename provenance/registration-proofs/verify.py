#!/usr/bin/env python3
"""Verify the registration proofs against this repository.

    python provenance/registration-proofs/verify.py [--repo PATH] [-v]

Needs only Python 3.8+ and git. For every registration and blind-prediction commit of the original
(private) repository it checks, from the raw git objects stored in objects/:

 1. Each stored object hashes to its name: sha1("<type> <size>\\0" + bytes). So the stored commit is
    exactly the commit with the original hash cited in the paper, and the stored trees are its trees.
 2. The GitHub activity-log event (an export of the original repository's log, in provenance/) has
    that commit as its new tip, or a new tip whose parent chain (stored commits, each hash-checked)
    leads to it. The event's timestamp is when GitHub received the commit.
 3. For a tag: the stored tag object hashes to the name in the ls-remote snapshot, points at the
    commit, and equals this repository's tag except for the commit it points to.
 4. The commit in this repository (provenance/commit-map-public.tsv) has the same author, committer,
    dates and message, and its parents are the mapped parents. If proofs.json marks the message as
    redacted (provenance/REDACTIONS.md, "Commit and tag messages"), the message here must be the
    original message with some spans replaced by "[redacted: ...; see provenance/REDACTIONS.md]"
    markers and nothing else; the original bytes are still the ones hashed in check 1.
 5. The original and this repository's root trees are equal entry by entry except the redacted files
    and the removed files, which are absent here (provenance/REDACTIONS.md); in particular configs/, prereg/, src/, results/, analysis/ and slurm/
    have identical tree hashes. notes/ differs only in the redacted notes files.
 6. Each registered file named in the proof has the same blob hash in both repositories; its SHA-256
    in this repository is printed, and compared with the SHA-256 recorded in the tag message if any.
Exit status 0 if every check passes.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROV = os.path.dirname(HERE)


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.decode(errors="replace").strip()))
    return r.stdout


def parse_tree(data):
    out, i = {}, 0
    while i < len(data):
        sp = data.index(b" ", i)
        nul = data.index(b"\0", sp)
        out[data[sp + 1:nul].decode("utf-8", "surrogateescape")] = (data[i:sp].decode(), data[nul + 1:nul + 21].hex())
        i = nul + 21
    return out


def headers(data):
    head, _, msg = data.partition(b"\n\n")
    hs = []
    for ln in head.split(b"\n"):
        if ln.startswith(b" ") and hs:
            hs[-1] = (hs[-1][0], hs[-1][1] + b"\n" + ln)
        else:
            k, _, v = ln.partition(b" ")
            hs.append((k.decode(), v))
    return hs, msg


MARKER = re.compile(rb"\[redacted: [^;\]]*; see provenance/REDACTIONS\.md\]")


def same_message(orig, here, redacted):
    """orig == here, or (when the proof says the message was redacted) here is orig with markers."""
    if orig == here:
        return True
    if not redacted:
        return False
    segs = MARKER.split(here)
    if len(segs) == 1:
        return False
    return re.fullmatch(b"(?s)" + b".+?".join(re.escape(x) for x in segs), orig) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(PROV))
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    repo = a.repo
    bundle = json.load(open(os.path.join(HERE, "proofs.json"), encoding="utf-8"))
    redacted = set(bundle["redacted_paths"])
    redacted_top = {p.split("/")[0] for p in redacted}
    removed_top = {p.split("/")[0] for p in bundle.get("removed_paths", [])}
    redacted_notes = {p.split("/", 1)[1] for p in redacted if p.startswith("notes/")}
    events = {e["id"]: e for e in json.load(open(os.path.join(PROV, bundle["activity_file"]), encoding="utf-8"))}
    lsr = {}
    for ln in open(os.path.join(PROV, bundle["ls_remote_file"]), encoding="utf-8"):
        f = ln.split()
        if len(f) == 2:
            lsr[f[1]] = f[0]
    cmap = {}
    for ln in open(os.path.join(PROV, bundle["commit_map_file"]), encoding="utf-8"):
        f = ln.rstrip("\n").split("\t")
        if len(f) >= 3 and f[0] in ("commit", "tag"):
            cmap[f[1]] = f[2]
    fails = []

    def fail(msg):
        fails.append(msg)
        print("    FAIL", msg)

    # 1. every stored object
    objs = {}
    for oid, typ in bundle["objects"].items():
        data = open(os.path.join(HERE, "objects", oid), "rb").read()
        h = hashlib.sha1(b"%s %d\0" % (typ.encode(), len(data)) + data).hexdigest()
        if h != oid:
            fail("object %s hashes to %s" % (oid, h))
        objs[oid] = data
    print("%d stored objects hash-checked" % len(objs))

    for p in bundle["proofs"]:
        c = p["old_commit"]
        print("\n== %s: original commit %s -> %s" % (p["label"], c[:12], p["new_commit"][:12]))
        n0 = len(fails)
        if c not in objs:
            fail("commit object missing")
            continue
        ch, msg = headers(objs[c])
        hd = dict(ch)
        root = hd["tree"].decode()
        if root != p["old_root_tree"] or root not in objs:
            fail("root tree missing or not the commit's tree")
            continue
        # 2. activity log
        ev = p.get("event")
        if not ev:
            fail("no GitHub activity event")
        else:
            e = events.get(ev["id"])
            if not e or e["after"] != ev["after"] or e["timestamp"] != ev["timestamp"] or e["ref"] != ev["ref"]:
                fail("activity event %s not found in %s as recorded" % (ev["id"], bundle["activity_file"]))
            chn = p["chain"]
            if chn[0] != ev["after"] or chn[-1] != c:
                fail("parent chain does not run from the event's new tip to the commit")
            for x, y in zip(chn, chn[1:]):
                if x not in objs or y.encode() not in [v for k, v in headers(objs[x])[0] if k == "parent"]:
                    fail("%s is not a stored parent of %s" % (y[:12], x[:12]))
            print("   GitHub: %s %s %s..%s at %s (%s)%s" % (
                ev["activity_type"], ev["ref"], ev["before"][:7], ev["after"][:7], ev["timestamp"], ev["local_time"],
                "" if len(chn) == 1 else ", reached through %d parent link(s)" % (len(chn) - 1)))
        # 3. tag
        if p.get("tag"):
            t = p["old_tag_object"]
            th, tmsg = headers(objs.get(t, b""))
            if dict(th).get("object", b"").decode() != c:
                fail("tag object does not point at the commit")
            if lsr.get("refs/tags/" + p["tag"]) != t:
                fail("tag object is not the one in the ls-remote snapshot")
            new_t = git(repo, "rev-parse", "refs/tags/" + p["tag"]).decode().strip()
            nh, nmsg = headers(git(repo, "cat-file", "tag", new_t))
            if new_t != p["new_tag_object"]:
                fail("this repository's tag %s is %s, expected %s" % (p["tag"], new_t, p["new_tag_object"]))
            same = [h for h in th if h[0] != "object"] == [h for h in nh if h[0] != "object"]
            if bundle.get("mailmap_applied"):
                strip = lambda hs: [(k, v.rsplit(b">", 1)[-1] if k == "tagger" else v) for k, v in hs if k != "object"]
                same = strip(th) == strip(nh)
            if (not same or not same_message(tmsg, nmsg, p.get("tag_message_redacted"))
                    or dict(nh)["object"].decode() != p["new_commit"]):
                fail("tag differs from the original apart from the commit it points to")
            tg = dict(th)["tagger"].decode().rsplit(" ", 2)
            print("   tag %s: object %s (ls-remote snapshot), tagger time %s %s" % (p["tag"], t[:12], tg[1], tg[2]))
        # 4. the public commit
        new = p["new_commit"]
        if cmap.get(c) != new:
            fail("commit map does not map %s to %s" % (c, new))
        nh, nmsg = headers(git(repo, "cat-file", "commit", new))
        keep = lambda hs: [(k, v) for k, v in hs if k not in ("tree", "parent")]
        if bundle.get("mailmap_applied"):
            keep = lambda hs: [(k, v.rsplit(b">", 1)[-1] if k in ("author", "committer") else v)
                               for k, v in hs if k not in ("tree", "parent")]
        if keep(ch) != keep(nh) or not same_message(msg, nmsg, p.get("message_redacted")):
            fail("author/committer/date/message differ from the original commit")
        elif msg != nmsg:
            print("   message: redacted here (provenance/REDACTIONS.md); the rest is identical to the original")
        op = [v.decode() for k, v in ch if k == "parent"]
        npar = [v.decode() for k, v in nh if k == "parent"]
        if [cmap.get(x) for x in op] != npar:
            fail("parents are not the mapped parents")
        # 5. trees
        ot = parse_tree(objs[root])
        nt = parse_tree(git(repo, "cat-file", "tree", dict(nh)["tree"].decode()))
        for name in sorted(set(ot) | set(nt)):
            if ot.get(name) != nt.get(name) and name not in redacted_top:
                if name in removed_top and name not in nt:
                    print("   %s: removed in this repository (see REDACTIONS.md, Removed files)" % name)
                    continue
                fail("top-level entry %s differs" % name)
        st = []
        for s in bundle["compared_subtrees"]:
            if s in ot or s in nt:
                ok = ot.get(s) == nt.get(s)
                st.append("%s/ %s" % (s, "=" if ok else "DIFFERS"))
                if not ok:
                    fail("subtree %s/ differs" % s)
        print("   identical subtrees: " + ", ".join(st))
        if "notes" in ot:
            onotes = parse_tree(objs[ot["notes"][1]])
            nnotes = parse_tree(git(repo, "cat-file", "tree", nt["notes"][1]))
            diff = sorted(n for n in set(onotes) | set(nnotes) if onotes.get(n) != nnotes.get(n))
            if any(d not in redacted_notes for d in diff):
                fail("notes/ differs outside the redacted files: %s" % diff)
            print("   notes/: %d entries, differing only in %s" % (len(onotes), ", ".join(diff) or "nothing"))
        # 6. registered files
        for f in p["files"]:
            if f["redacted_path"]:
                print("   %s: a redacted file, blob differs by design (see REDACTIONS.md)" % f["path"])
                continue
            cur, ok = root, True
            parts = f["path"].split("/")
            for part in parts[:-1]:
                ent = parse_tree(objs.get(cur, b""))
                if part not in ent:
                    ok = False
                    break
                cur = ent[part][1]
            ent = parse_tree(objs.get(cur, b"")) if ok else {}
            if not ok or ent.get(parts[-1], (None, None))[1] != f["old_blob"]:
                fail("%s: blob not provable from stored trees" % f["path"])
                continue
            nb = git(repo, "rev-parse", "%s:%s" % (new, f["path"])).decode().strip()
            data = git(repo, "cat-file", "blob", nb)
            sha = hashlib.sha256(data).hexdigest()
            if nb != f["old_blob"]:
                fail("%s: blob %s here, %s in the original" % (f["path"], nb, f["old_blob"]))
            extra = ""
            if f.get("claimed_sha256"):
                extra = ", matches the tag message" if sha == f["claimed_sha256"] else ", DOES NOT match the tag message"
                if sha != f["claimed_sha256"]:
                    fail("%s: SHA-256 differs from the tag message" % f["path"])
            if a.verbose or f.get("claimed_sha256") or f["path"].startswith(("configs/", "prereg/")):
                print("   %s: blob %s identical, sha256 %s%s" % (f["path"], nb[:12], sha, extra))
        print("   %s" % ("OK" if len(fails) == n0 else "FAILED"))
    print("\n%d proofs, %d failures" % (len(bundle["proofs"]), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

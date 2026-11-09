"""UI hierarchy XML -> compact element list for the planner."""
import hashlib
import re
import xml.etree.ElementTree as ET

CAP = 40
_B = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _bounds(n):
    m = _B.match(n.get("bounds", ""))
    return tuple(map(int, m.groups())) if m else None


def _texts(n, out):
    """Collect labels of non-clickable descendants (for label merge)."""
    for c in n:
        if c.get("visible-to-user") == "false":
            continue
        t = c.get("text") or c.get("content-desc")
        if t:
            out.append(t)
        if c.get("clickable") != "true":
            _texts(c, out)
    return out


def _uncovered(els, nodes):
    """Drop elements whose centre is under a tappable node drawn on top: a tap there hits the cover instead
    (a video row behind YouTube's bottom bar tapped Android's Home button, Nov 6). The hash ignores this, so scrolling
    one out from under a bar still counts as a screen change.
    Later nodes draw on top; System UI (nav bar) comes first in the dump but is always on top."""
    # ponytail: clickable covers only; a non-clickable overlay is not seen. Add one if an app needs it.
    order = {id(n): i for i, n in enumerate(nodes)}
    covers = [(order[id(n)], n.get("package") == "com.android.systemui", _bounds(n), n) for n in nodes
              if n.get("clickable") == "true" and n.get("visible-to-user") != "false" and _bounds(n)]
    keep = []
    for e in els:
        own = {id(x) for x in e["node"].iter("node")}
        i = order[id(e["node"])]
        hit = any((sys or j > i) and id(n) not in own and b[0] <= e["cx"] < b[2] and b[1] <= e["cy"] < b[3]
                  for j, sys, b, n in covers)
        if not hit:
            keep.append(e)
    return keep


def compact(xml, size=None, cap=CAP):
    """Return (elements, screen_hash, package). size=(w,h) clips off-screen nodes."""
    root = ET.fromstring(xml)
    nodes = list(root.iter("node"))
    boxes = [b for b in map(_bounds, nodes) if b]
    w, h = size or (max(b[2] for b in boxes), max(b[3] for b in boxes))
    pkgs = [n.get("package") for n in nodes if n.get("package") not in (None, "com.android.systemui")]
    package = pkgs[0] if pkgs else (nodes[0].get("package") if nodes else "")
    merged, els = set(), []

    def walk(n):
        b = _bounds(n)
        keep = n.get("visible-to-user") != "false" and b and b[2] > b[0] and b[3] > b[1] \
            and b[0] < w and b[1] < h and b[2] > 0 and b[3] > 0
        if keep and id(n) not in merged and n.get("package") != "com.android.systemui":  # status bar/shade = noise
            text, desc = n.get("text", ""), n.get("content-desc", "")
            click, scroll = n.get("clickable") == "true", n.get("scrollable") == "true"
            edit = n.get("class", "").endswith("EditText")
            if click and not (text or desc):  # label merge: container takes children's text
                kids = _texts(n, [])
                text = " ".join(kids)
                for d in n.iter("node"):
                    if d is not n and d.get("clickable") != "true":
                        merged.add(id(d))
            rid = n.get("resource-id", "").split("/")[-1]
            if text or desc or rid or click or scroll or edit:
                if text or desc or click or scroll or edit:  # bare rid-only nodes are noise
                    els.append(dict(text=text, desc=desc, rid=rid, cls=n.get("class", "").split(".")[-1],
                                    click=click, scroll=scroll, edit=edit,
                                    cx=(b[0] + b[2]) // 2, cy=(b[1] + b[3]) // 2, b=b, node=n))
        for c in n:
            walk(c)

    walk(root)
    sig = sorted((e["cls"], e["text"], e["desc"], tuple(round(v / 20) for v in e["b"])) for e in els)
    shash = hashlib.sha1((package + repr(sig)).encode()).hexdigest()[:12]
    els = _uncovered(els, nodes)
    els.sort(key=lambda e: (e["b"][1], e["b"][0]))
    if len(els) > cap:  # interactive first, then keep reading order
        pri = sorted(range(len(els)), key=lambda i: not (els[i]["edit"] or els[i]["click"] or els[i]["scroll"]))
        els = [els[i] for i in sorted(pri[:cap])]
    for i, e in enumerate(els):
        e.pop("b"), e.pop("node")
        e["id"] = i
    return els, shash, package

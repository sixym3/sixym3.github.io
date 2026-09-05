#!/usr/bin/env python3
"""Build-time stamping for the site.

Two things get baked into the HTML on deploy so that no visitor's browser has
to fetch anything to render a complete page:

  1. "Last updated"  - the date this deploy ran.
  2. Prev / next pager on each project page - from the order of
     projects/index.html, which stays the single source of truth.

Idempotent: it overwrites whatever is already there, so running it twice is
the same as running it once, and it does not matter whether the file currently
holds an empty placeholder or a value from a previous run. That means you can
run it locally to see the real output, and either commit the result or not -
the next deploy overwrites it either way.

    python .github/scripts/build.py --check    # report only, writes nothing
    python .github/scripts/build.py            # stamp in place
"""
import argparse
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Match the empty placeholder *or* an already-stamped element, so a re-run
# replaces the old value instead of skipping it.
LAST_UPDATED_RE = re.compile(r'<time class="last-updated"[^>]*>.*?</time>', re.S)
PAGER_RE = re.compile(r'<nav class="pager"[^>]*>.*?</nav>', re.S)


def html_files():
    return sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("projects/*.html")))


def build_date():
    """The moment of this deploy.

    Deliberately the build time rather than the newest commit date: what the
    line claims is when the published site was last refreshed, and a manual
    re-deploy of an old commit should still count as an update.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def project_order():
    """The project pages, in the order projects/index.html lists them."""
    listing = ROOT / "projects" / "index.html"
    items = re.findall(
        r'<span class="mini-main">\s*<a href="([A-Za-z][A-Za-z0-9_-]*\.html)">(.*?)</a>',
        listing.read_text(encoding="utf-8"), re.S,
    )
    return [(href, re.sub(r"\s+", " ", name).strip())
            for href, name in items if href != "index.html"]


def pager_html(order, i):
    parts = []
    if i > 0:
        parts.append('<a href="%s">&larr; %s</a>' % order[i - 1])
    parts.append('<a href="index.html">All projects</a>')
    if i < len(order) - 1:
        parts.append('<a href="%s">%s &rarr;</a>' % order[i + 1])
    return '<nav class="pager">' + "".join(parts) + "</nav>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    iso = build_date()
    human = datetime.fromisoformat(iso).strftime("%B %Y")
    stamped = ('<time class="last-updated" datetime="%s">Last updated %s</time>'
               % (iso, human))

    order = project_order()
    if not order:
        print("ERROR: no projects found in projects/index.html", file=sys.stderr)
        return 1
    index = {href: i for i, (href, _) in enumerate(order)}

    print("last updated : %s (%s)" % (human, iso))
    print("project order: %d pages" % len(order))

    touched = pagers = 0
    for path in html_files():
        text = original = path.read_text(encoding="utf-8")

        text, n_time = LAST_UPDATED_RE.subn(lambda _m: stamped, text)

        n_pager = 0
        if PAGER_RE.search(text):
            i = index.get(path.name)
            if i is None:
                print("  WARNING: %s has a pager but is not listed in projects/index.html"
                      % path.relative_to(ROOT))
            else:
                text, n_pager = PAGER_RE.subn(lambda _m: pager_html(order, i), text)
                pagers += n_pager

        if n_time or n_pager:
            touched += 1
        if text != original and not args.check:
            path.write_text(text, encoding="utf-8")

    verb = "would stamp" if args.check else "stamped"
    print("%s %d files (%d pagers)" % (verb, touched, pagers))
    return 0


if __name__ == "__main__":
    sys.exit(main())

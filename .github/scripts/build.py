#!/usr/bin/env python3
"""Build-time stamping for the site.

Five things get baked into the HTML on deploy so that no visitor's browser has
to fetch anything to render a complete page:

  1. "Last updated"  - the date this deploy ran.
  2. Prev / next pager on each project page - from the order of
     projects/index.html, which stays the single source of truth.
  3. The homepage "Other Projects" list - the most recent entries from that
     same listing that the curated section does not already show.
  4. A <picture> wrapper with srcset around every image that has generated
     size variants, so a page only ever has to name the file.
  5. A content hash on the site.css / site.js URLs - so a browser can never
     pair freshly deployed HTML with a stale stylesheet or script. Without it
     a cached script leaves videos that never start, and a cached stylesheet
     leaves the block diagrams unstyled.

Idempotent: it overwrites whatever is already there, so running it twice is
the same as running it once, and it does not matter whether the file currently
holds an empty placeholder or a value from a previous run. That means you can
run it locally to see the real output, and either commit the result or not -
the next deploy overwrites it either way.

    python .github/scripts/build.py --check    # report only, writes nothing
    python .github/scripts/build.py            # stamp in place
"""
import argparse
import hashlib
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]

# How many entries the homepage "Other Projects" list shows.
OTHER_LIMIT = 3

# Cache-busted at deploy time; see item 4 above.
VERSIONED_ASSETS = ("assets/css/site.css", "assets/js/site.js")

# Responsive images. A page just names the file:
#
#     <img src="../images/projects/X/photo.jpg" alt="...">
#
# and this fills in the <picture>/srcset around it from whatever widths
# tools/optimize.py generated. Nothing to remember while authoring, and the
# committed HTML stays readable. Add data-raw to opt a single image out.
IMG_RE = re.compile(r'<img[^>]*?>', re.S)
IMG_SRC_RE = re.compile(r'src\s*=\s*"([^"]+)"')
PICTURE_RE = re.compile(r'<picture>\s*<source[^>]*>\s*(<img[^>]*?>)\s*</picture>', re.S)
GENERATED_ATTRS_RE = re.compile(r'\s+(?:loading|decoding|data-full)="[^"]*"')
SRCSET_WIDTHS = (320, 800, 1600)

# How wide the image actually renders, so the browser picks the right file.
SIZES_GRID = "(max-width: 700px) 100vw, 380px"   # two-up figure grid
SIZES_WIDE = "(max-width: 860px) 100vw, 800px"   # banner / full column
SIZES_AVATAR = "148px"                           # the fixed-size bio photo

# Match the empty placeholder *or* an already-stamped element, so a re-run
# replaces the old value instead of skipping it.
LAST_UPDATED_RE = re.compile(r'<time class="last-updated"[^>]*>.*?</time>', re.S)
PAGER_RE = re.compile(r'<nav class="pager"[^>]*>.*?</nav>', re.S)

# The <ul> inside the homepage's Other Projects section, and the curated
# section whose links it must not duplicate.
OTHER_LIST_RE = re.compile(r'(<section id="projects">.*?)<ul class="mini">.*?</ul>', re.S)
RESEARCH_RE = re.compile(r'<section id="research">(.*?)</section>', re.S)

# One entry on projects/index.html: link, title, and the year in the margin.
LISTING_ITEM_RE = re.compile(
    r'<li>\s*<span class="mini-main">\s*'
    r'<a href="([A-Za-z][A-Za-z0-9_-]*\.html)">(.*?)</a>'
    r'.*?</span>\s*'
    r'<span class="mini-meta">([^<]*)</span>\s*</li>',
    re.S,
)


def html_files():
    return sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("projects/*.html")))


def build_date():
    """The moment of this deploy.

    Deliberately the build time rather than the newest commit date: what the
    line claims is when the published site was last refreshed, and a manual
    re-deploy of an old commit should still count as an update.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def project_entries():
    """Every project on projects/index.html, in the order it lists them."""
    listing = (ROOT / "projects" / "index.html").read_text(encoding="utf-8")
    out = []
    for href, title, meta in LISTING_ITEM_RE.findall(listing):
        if href == "index.html":
            continue
        year = re.search(r"(\d{4})", meta)
        out.append({
            "href": href,
            "title": re.sub(r"\s+", " ", title).strip(),
            "meta": meta.strip(),
            "year": int(year.group(1)) if year else 0,
        })
    return out


def project_order(entries):
    return [(e["href"], e["title"]) for e in entries]


def pager_html(order, i):
    parts = []
    if i > 0:
        parts.append('<a href="%s">&larr; %s</a>' % order[i - 1])
    parts.append('<a href="index.html">All projects</a>')
    if i < len(order) - 1:
        parts.append('<a href="%s">%s &rarr;</a>' % order[i + 1])
    return '<nav class="pager">' + "".join(parts) + "</nav>"


def other_projects_html(entries, curated):
    """The newest entries the curated section does not already show.

    Sorted newest first; ties keep the order projects/index.html gives them,
    so that page stays in charge of how same-year projects rank.
    """
    rest = [e for e in entries if "projects/" + e["href"] not in curated]
    rest.sort(key=lambda e: -e["year"])          # list.sort is stable
    picked = rest[:OTHER_LIMIT]

    rows = [
        '      <li>\n'
        '        <span class="mini-main"><a href="projects/%s">%s</a></span>\n'
        '        <span class="mini-meta">%s</span>\n'
        '      </li>' % (e["href"], e["title"], e["meta"])
        for e in picked
    ]
    return '<ul class="mini">\n' + "\n".join(rows) + "\n    </ul>", picked


def expand_responsive_images(text, page):
    """Wrap every <img> that has generated variants in a <picture>.

    Idempotent: an already-wrapped image is unwrapped first, so re-running
    after changing the width list produces the new markup rather than nesting.
    """
    text = PICTURE_RE.sub(lambda m: GENERATED_ATTRS_RE.sub("", m.group(1)), text)

    depth = "" if page.parent == ROOT else "../"
    out, last, count = [], 0, 0

    for m in IMG_RE.finditer(text):
        tag = m.group(0)
        if "lightbox-image" in tag or "data-raw" in tag:
            continue
        sm = IMG_SRC_RE.search(tag)
        if not sm:
            continue
        url = sm.group(1)
        stem, ext = os.path.splitext(url)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            continue

        # Which widths actually exist on disk?
        rel = url[len(depth):] if depth and url.startswith(depth) else url
        widths = [w for w in SRCSET_WIDTHS
                  if (ROOT / ("%s-%d.webp" % (os.path.splitext(rel)[0], w))).exists()]
        if not widths:
            continue

        head = text[:m.start()]
        if "bio-photo" in head[-300:]:
            sizes, widths = SIZES_AVATAR, [w for w in widths if w <= 800]
        else:
            gi, gclose = head.rfind("figure-grid"), head.rfind("</div>")
            sizes = SIZES_GRID if (gi != -1 and gi > gclose) else SIZES_WIDE
        custom = re.search(r'data-sizes="([^"]+)"', tag)
        if custom:
            sizes = custom.group(1)

        srcset = ", ".join("%s-%d.webp %dw" % (stem, w, w) for w in widths)
        full = "%s-%d.webp" % (stem, max(widths))
        eager = "banner" in head[-400:] or "bio-photo" in head[-300:]

        newtag = tag[:-1].rstrip()
        newtag += ' loading="%s" decoding="async"' % ("eager" if eager else "lazy")
        newtag += ' data-full="%s">' % full          # lightbox opens the big one

        indent = " " * (m.start() - (head.rfind(chr(10)) + 1))
        out.append(text[last:m.start()])
        out.append('<picture>' + chr(10)
                   + indent + '    <source type="image/webp" srcset="%s" sizes="%s">' % (srcset, sizes) + chr(10)
                   + indent + '    ' + newtag + chr(10)
                   + indent + '</picture>')
        last = m.end()
        count += 1

    out.append(text[last:])
    return "".join(out), count


def asset_digests():
    out = {}
    for rel in VERSIONED_ASSETS:
        path = ROOT / rel
        if not path.exists():
            print("  WARNING: %s is missing, not versioning it" % rel, file=sys.stderr)
            continue
        out[pathlib.PurePosixPath(rel).name] = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    return out


def stamp_asset_urls(text, digests):
    for name, digest in digests.items():
        text = re.sub(
            r'((?:\.\./)?assets/(?:css|js)/' + re.escape(name) + r')(\?v=[0-9a-f]+)?',
            lambda m, d=digest: m.group(1) + "?v=" + d,
            text,
        )
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    iso = build_date()
    human = datetime.fromisoformat(iso).strftime("%B %Y")
    stamped = ('<time class="last-updated" datetime="%s">Last updated %s</time>'
               % (iso, human))

    entries = project_entries()
    if not entries:
        print("ERROR: no projects found in projects/index.html", file=sys.stderr)
        return 1
    order = project_order(entries)
    index = {href: i for i, (href, _) in enumerate(order)}

    digests = asset_digests()

    print("last updated : %s (%s)" % (human, iso))
    print("project order: %d pages" % len(order))
    print("asset hashes : %s" % ", ".join("%s=%s" % kv for kv in sorted(digests.items())))

    home = ROOT / "index.html"
    touched = pagers = images = 0

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

        if path == home:
            research = RESEARCH_RE.search(text)
            curated = set(re.findall(r'href="(projects/[^"#]+\.html)"',
                                     research.group(1) if research else ""))
            block, picked = other_projects_html(entries, curated)
            if OTHER_LIST_RE.search(text):
                text = OTHER_LIST_RE.sub(lambda m: m.group(1) + block, text, count=1)
                print("other projects: " + ", ".join(
                    "%s (%s)" % (e["title"], e["meta"]) for e in picked))
            else:
                print("  WARNING: no Other Projects list found in index.html")

        text, n_img = expand_responsive_images(text, path)
        images += n_img

        text = stamp_asset_urls(text, digests)

        if n_time or n_pager:
            touched += 1
        if text != original and not args.check:
            path.write_text(text, encoding="utf-8")

    verb = "would stamp" if args.check else "stamped"
    print("%s %d files (%d pagers, %d responsive images)"
          % (verb, touched, pagers, images))
    return 0


if __name__ == "__main__":
    sys.exit(main())

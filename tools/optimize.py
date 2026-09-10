#!/usr/bin/env python3
"""Generate every web-ready asset in images/ from the originals in _media/.

    _media/projects/X/photo.jpg     <- you put this here, full resolution
    images/projects/X/photo.jpg        served fallback, long edge 1600
    images/projects/X/photo-320.webp   generated
    images/projects/X/photo-800.webp   generated
    images/projects/X/photo-1600.webp  generated

    _media/projects/X/clip.mp4      <- you put this here
    images/projects/X/clip.mp4         served, long edge 1280
    images/projects/X/clip-sm.mp4      served to narrow viewports, long edge 640

Nothing under images/ should be edited by hand: this script owns it. Anything
in images/ with no counterpart in _media/ (logo.svg, the poster PDF) is left
alone.

Runs inside the pinned container so encodes are identical everywhere:

    docker build -t site-media:latest tools/
    docker run --rm -v "$(pwd -W):/work" site-media:latest python3 tools/optimize.py

A manifest records the SHA-256 of each original, so a second run re-encodes
only what actually changed. Pass --force to ignore it.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SRC_DIR = '_media'
OUT_DIR = 'images'
MANIFEST = 'tools/.media-manifest.json'

IMAGE_EXT = ('.jpg', '.jpeg', '.png')
VIDEO_EXT = ('.mp4',)

IMAGE_WIDTHS = (320, 800, 1600)   # webp variants offered through srcset
IMAGE_FALLBACK = 1600             # long edge of the same-format fallback
VIDEO_MAIN = 1280                 # long edge of the default encode
VIDEO_SMALL = 640                 # long edge of the -sm encode

# Names only this script ever produces, so they are safe to sweep.
GENERATED_RE = re.compile(r'-(?:\d+\.webp|sm\.mp4)$', re.I)


def which(*names):
    for n in names:
        if shutil.which(n):
            return n
    return None


# ImageMagick 7 exposes `magick`; the version in Ubuntu's apt is 6 and only
# ships `convert`. oxipng is a bonus and simply skipped when unavailable.
MAGICK = which('magick', 'convert')
OXIPNG = which('oxipng')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(' '.join(cmd) + os.linesep + r.stderr[-2000:] + os.linesep)
        raise SystemExit('encode failed')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def outputs_for(rel):
    """Every file this source is responsible for producing."""
    stem, ext = os.path.splitext(rel)
    out = [os.path.join(OUT_DIR, rel)]
    if ext.lower() in IMAGE_EXT:
        out += [os.path.join(OUT_DIR, '%s-%d.webp' % (stem, w)) for w in IMAGE_WIDTHS]
    elif ext.lower() in VIDEO_EXT:
        out.append(os.path.join(OUT_DIR, stem + '-sm.mp4'))
    return [p.replace(os.sep, '/') for p in out]


def encode_image(src, rel):
    stem, ext = os.path.splitext(rel)
    fallback = os.path.join(OUT_DIR, rel)
    os.makedirs(os.path.dirname(fallback), exist_ok=True)

    box = '%dx%d>' % (IMAGE_FALLBACK, IMAGE_FALLBACK)   # '>' shrinks only
    if ext.lower() == '.png':
        run([MAGICK, src, '-auto-orient', '-resize', box, '-strip', fallback])
        if OXIPNG:
            subprocess.run([OXIPNG, '-q', '-o', '2', '--strip', 'safe', fallback],
                           capture_output=True)
    else:
        run([MAGICK, src, '-auto-orient', '-resize', box, '-strip',
             '-quality', '82', '-sampling-factor', '4:2:0',
             '-interlace', 'Plane', fallback])

    # Re-compressing a small file can make it bigger; keep the original then.
    if os.path.getsize(fallback) >= os.path.getsize(src):
        shutil.copy2(src, fallback)

    for w in IMAGE_WIDTHS:
        dst = os.path.join(OUT_DIR, '%s-%d.webp' % (stem, w))
        run([MAGICK, src, '-auto-orient', '-resize', '%dx%d>' % (w, w),
             '-strip', '-quality', '80', dst])


def encode_video(src, rel):
    stem, _ = os.path.splitext(rel)
    os.makedirs(os.path.dirname(os.path.join(OUT_DIR, rel)), exist_ok=True)
    for cap, dst in ((VIDEO_MAIN, os.path.join(OUT_DIR, rel)),
                     (VIDEO_SMALL, os.path.join(OUT_DIR, stem + '-sm.mp4'))):
        # faststart puts the index at the head so playback can begin before
        # the download finishes; -an drops the silent audio track.
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src,
             '-vf', ("scale=w='min(%d,iw)':h='min(%d,ih)'"
                     ':force_original_aspect_ratio=decrease:force_divisible_by=2'
                     % (cap, cap)),
             '-c:v', 'libx264', '-profile:v', 'high', '-crf', '28',
             '-preset', 'slow', '-pix_fmt', 'yuv420p',
             '-movflags', '+faststart', '-an', dst])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true', help='re-encode everything')
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if anything is out of date, write nothing')
    args = ap.parse_args()

    if not MAGICK:
        raise SystemExit('need ImageMagick (magick or convert) on PATH')
    if not shutil.which('ffmpeg'):
        raise SystemExit('need ffmpeg on PATH')

    if not os.path.isdir(SRC_DIR):
        raise SystemExit('no %s/ directory' % SRC_DIR)

    try:
        manifest = json.load(open(MANIFEST))
    except Exception:
        manifest = {}

    sources = []
    for root, _dirs, files in os.walk(SRC_DIR):
        for name in sorted(files):
            if name.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                full = os.path.join(root, name).replace(os.sep, '/')
                sources.append((full, full[len(SRC_DIR) + 1:]))

    stale, done, skipped = [], 0, 0
    removed_dirs = set()
    for src, rel in sorted(sources):
        digest = sha(src)
        fresh = (manifest.get(rel) == digest
                 and all(os.path.exists(p) for p in outputs_for(rel)))
        if fresh and not args.force:
            skipped += 1
            continue
        stale.append((src, rel, digest))

    orphans = [k for k in manifest if k not in {rel for _s, rel in sources}]

    if args.check:
        for _s, rel, _d in stale:
            print('out of date: ' + rel)
        for rel in orphans:
            print('orphaned:    ' + rel + ' (source deleted)')
        print('%d up to date, %d need encoding, %d to remove'
              % (skipped, len(stale), len(orphans)))
        return 1 if (stale or orphans) else 0

    for src, rel, digest in stale:
        before = os.path.getsize(src)
        if rel.lower().endswith(VIDEO_EXT):
            encode_video(src, rel)
        else:
            encode_image(src, rel)
        after = sum(os.path.getsize(p) for p in outputs_for(rel) if os.path.exists(p))
        manifest[rel] = digest
        done += 1
        print('  %-58s %7.2f MB -> %6.2f MB (all sizes)'
              % (rel, before / 1048576.0, after / 1048576.0))

    # Deleting from _media/ is how you delete from images/.
    #
    # Two passes, because the two kinds of output are not equally safe to
    # identify. The -320/-800/-1600.webp and -sm.mp4 variants can only ever
    # have been generated, so any that no live source claims is swept. The
    # same-name fallback (images/x/photo.png) is indistinguishable from a
    # hand-placed file, so it is only removed when the manifest confirms this
    # script wrote it; anything else is reported rather than deleted.
    live = {rel for _s, rel in sources}
    expected = set()
    for rel in live:
        expected.update(outputs_for(rel))

    for rel in [k for k in manifest if k not in live]:
        for path in outputs_for(rel):
            if os.path.exists(path):
                os.remove(path)
                print('  removed %s (source deleted)' % path)
                removed_dirs.add(os.path.dirname(path))
        del manifest[rel]

    unclaimed = []
    for root, _dirs, files in os.walk(OUT_DIR):
        for name in files:
            path = os.path.join(root, name).replace(os.sep, '/')
            if path in expected:
                continue
            if GENERATED_RE.search(name):
                os.remove(path)
                print('  removed %s (no longer generated)' % path)
                removed_dirs.add(os.path.dirname(path))
            elif name.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                unclaimed.append(path)

    if unclaimed:
        print('  NOTE: no source in %s/ produces these, left in place:' % SRC_DIR)
        for path in sorted(unclaimed):
            print('    ' + path)

    # Tidy up directories the deletions emptied.
    for d in sorted(removed_dirs, key=len, reverse=True):
        while d and d.startswith(OUT_DIR) and os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
            d = os.path.dirname(d)

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, 'w') as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)

    print('encoded %d, skipped %d already current' % (done, skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())

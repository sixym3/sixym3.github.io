# Media toolchain, pinned so local encodes match what CI produces.
#
#   docker build -t site-media:latest tools/
#   docker run --rm -v "$(pwd -W):/work" site-media:latest python3 tools/optimize.py
#
# CI does not use this image: the runner installs ffmpeg and ImageMagick from
# apt, which is much faster than building a container on every push. The
# encoder settings live in tools/optimize.py, so both paths agree.
FROM alpine:3.20

RUN apk add --no-cache \
      python3 \
      ffmpeg \
      imagemagick \
      imagemagick-jpeg \
      imagemagick-webp \
      libwebp-tools \
      oxipng

WORKDIR /work

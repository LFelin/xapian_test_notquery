#!/bin/sh
# Usage: docker/build.sh [XAPIAN_VERSION ...]   (default: 1.4.30 2.0.0 2.1.0)
cd "$(dirname "$0")/.." || exit 1
[ $# -eq 0 ] && set -- 1.4.30 2.0.0 2.1.0
for version in "$@"; do
    docker build -f docker/Dockerfile --build-arg XAPIAN_VERSION="$version" \
        -t xapian_test_notquery:"$version" . || exit 1
    docker run --rm xapian_test_notquery:"$version"
done

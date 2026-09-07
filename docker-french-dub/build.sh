#!/usr/bin/env bash
set -euo pipefail

overlay_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
upstream_ref=$(tr -d '\n' < "$overlay_dir/upstream-ref")
if [[ ! "$upstream_ref" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'upstream-ref must contain a full upstream commit SHA.' >&2
  exit 1
fi
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/seerr-french-dub.XXXXXXXX")
trap 'rm -rf -- "$build_dir"' EXIT

git -C "$build_dir" init -q
git -C "$build_dir" fetch -q --depth=1 https://github.com/seerr-team/seerr.git "$upstream_ref"
git -C "$build_dir" checkout -q --detach FETCH_HEAD
version=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$build_dir/package.json")
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Expected a stable upstream version, got: $version" >&2
  exit 1
fi
image_tag=${1:-seerr-french-dub:$version}
python3 "$overlay_dir/relabel.py" "$build_dir"
source_epoch=$(git -C "$build_dir" show -s --format=%ct HEAD)
docker build --progress=plain \
  --build-arg "COMMIT_TAG=$upstream_ref" \
  --build-arg "SOURCE_DATE_EPOCH=$source_epoch" \
  --label "org.opencontainers.image.revision=$upstream_ref" \
  --label 'org.opencontainers.image.source=https://github.com/libussa/seerr' \
  --label 'fr.libussa.seerr.variant=doublage-francais' \
  -t "$image_tag" "$build_dir"
printf '\nBuilt %s\n' "$image_tag"

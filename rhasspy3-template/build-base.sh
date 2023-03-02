#!/usr/bin/env bash
set -eo pipefail

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

version="$(cat "${this_dir}/VERSION")"

docker buildx build -f "${this_dir}/Dockerfile.base" "${this_dir}" \
    --platform "linux/amd64,linux/arm64" \
    --tag "rhasspy/rhasspy3-addon-base:${version}" "$@"

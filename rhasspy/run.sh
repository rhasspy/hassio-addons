#!/usr/bin/env bash

set -e

if [[ -f "${CONFIG_PATH}" ]]; then
    # Hass.IO configuration
    profile_name="$(jq --raw-output '.profile_name' "${CONFIG_PATH}")"
    if [[ -z "${profile_name}" ]]; then
        echo "No profile name provided!" 1>&2
        exit 1

    profile_dir="$(jq --raw-output '.profile_dir' "${CONFIG_PATH}")"
    if [[ -z "${profile_dir}" ]]; then
        profile_dir='/share/rhasspy/profiles'
    fi
    RHASSPY_ARGS=('--profile' "${profile_name}" '--user-profiles' "${profile_dir}")

    # Copy user-defined asoundrc to root
    asoundrc="$(jq --raw-output '.asoundrc[]' "${CONFIG_PATH}")"
    if [[ ! -z "${asoundrc}" ]]; then
        echo "${asoundrc}" > /root/.asoundrc
    fi

    # Add SSL settings
    ssl="$(jq --raw-output '.ssl' "${CONFIG_PATH}")"
    if [[ "${ssl}" == 'true' ]]; then
        certfile="$(jq --raw-output '.certfile' "${CONFIG_PATH}")"
        if [[ -n "${certfile}" ]]; then
            RHASSPY_ARGS+=('--certfile' "/ssl/${certfile}")
        fi

        keyfile="$(jq --raw-output '.keyfile' "${CONFIG_PATH}")"
        if [[ -n "${keyfile}" ]]; then
            RHASSPY_ARGS+=('--keyfile' "/ssl/${keyfile}")
        fi
    fi

    # Prefix for HTTP UI
    http_root="$(jq --raw-output '.http_root' "${CONFIG_PATH}")"
    if [[ ! -z "${http_root}" ]]; then
        RHASSPY_ARGS+=('--http-root' "${http_root}")
    fi

    if [[ ! -z "${SUPERVISOR_TOKEN}" ]]; then
        # Auto-configure Home Assistant connection
        PROFILE_PATH="${profile_dir}/${profile_name}/profile.json"
        jq \
            '.home_assistant |= {"access_token": "'"${SUPERVISOR_TOKEN}"'", "url": "http://supervisor/core"}' \
            "${PROFILE_PATH}"
    fi
fi

if [[ -z "${RHASSPY_ARGS[*]}" ]]; then
    /usr/lib/rhasspy/bin/rhasspy-voltron "$@"
else
    /usr/lib/rhasspy/bin/rhasspy-voltron "${RHASSPY_ARGS[@]}" "$@"
fi

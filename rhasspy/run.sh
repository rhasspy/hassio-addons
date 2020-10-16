#!/usr/bin/env bash

if [[ -f "${CONFIG_PATH}" ]]; then
    # Hass.IO configuration
    profile_name="$(jq --raw-output '.profile_name' "${CONFIG_PATH}")"
    profile_dir="$(jq --raw-output '.profile_dir' "${CONFIG_PATH}")"
    RHASSPY_ARGS=('--profile' "${profile_name}" '--user-profiles' "${profile_dir}")

    # Copy user-defined asoundrc to root
    asoundrc="$(jq --raw-output '.asoundrc' "${CONFIG_PATH}")"
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
fi

if [[ -z "${RHASSPY_ARGS[*]}" ]]; then
    /usr/lib/rhasspy/bin/rhasspy-voltron "$@"
else
    /usr/lib/rhasspy/bin/rhasspy-voltron "${RHASSPY_ARGS[@]}" "$@"
fi

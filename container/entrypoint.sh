#!/usr/bin/env sh
set -eu

cmd="${1:-gateway}"
if [ "$#" -gt 0 ]; then
    shift
fi

case "$cmd" in
    gateway)
        if [ "${DLM_WAIT:-true}" = "true" ]; then
            timeout="${DLM_WAIT_TIMEOUT:-30}"
            waited=0
            while ! nc -z "${DLM_HOST:-127.0.0.1}" "${DLM_PORT:-37373}" >/dev/null 2>&1; do
                if [ "$waited" -ge "$timeout" ]; then
                    break
                fi
                waited=$((waited + 1))
                sleep 1
            done
        fi
        exec python3 /opt/hermes-crypto/lan_gateway.py \
            --bind "${GATEWAY_BIND:-0.0.0.0}" \
            --port "${GATEWAY_PORT:-8080}" \
            --tcp-port "${RAW_TCP_PORT:-37374}" \
            "$@"
        ;;
    dlm)
        mkdir -p "${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}/Logs" \
            "${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}/Disk" \
            "${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}/Quarantine"
        cd "${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}"
        exec python3 "${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}/JackrabbitDLM" \
            "${DLM_BIND:-0.0.0.0}" \
            "${DLM_PORT:-37373}" \
            "$@"
        ;;
    test|tests)
        exec python3 /opt/hermes-crypto/tests/run_all.py "$@"
        ;;
    sh|shell)
        exec /bin/sh "$@"
        ;;
    *)
        exec "$cmd" "$@"
        ;;
esac

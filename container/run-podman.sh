#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${HERMES_CRYPTO_IMAGE:-localhost/hermes-crypto:wonderland}"
POD="${WONDERLAND_POD:-wonderland}"
BIND="${WONDERLAND_BIND:-127.0.0.1}"
GATEWAY_PORT="${WONDERLAND_GATEWAY_PORT:-18080}"
RAW_TCP_PORT="${WONDERLAND_RAW_TCP_PORT:-17374}"
DLM_PORT="${WONDERLAND_DLM_PORT:-17373}"
GATEWAY_ENV_FILE="${GATEWAY_ENV_FILE:-$ROOT_DIR/container/gateway.env}"

usage() {
    cat <<USAGE
Usage: container/run-podman.sh [build|start|restart|stop|status|logs|print-env|configure-hermes]

Environment:
  HERMES_CRYPTO_IMAGE   $IMAGE
  WONDERLAND_POD        $POD
  WONDERLAND_BIND       $BIND
  WONDERLAND_GATEWAY_PORT $GATEWAY_PORT
  WONDERLAND_RAW_TCP_PORT $RAW_TCP_PORT
  WONDERLAND_DLM_PORT   $DLM_PORT
  GATEWAY_ENV_FILE      $GATEWAY_ENV_FILE
USAGE
}

build_image() {
    podman build \
        -t "$IMAGE" \
        -f "$ROOT_DIR/Containerfile" \
        "$ROOT_DIR"
}

start_stack() {
    if ! podman pod exists "$POD"; then
        podman pod create \
            --name "$POD" \
            -p "${BIND}:${GATEWAY_PORT}:8080" \
            -p "${BIND}:${RAW_TCP_PORT}:37374" \
            -p "${BIND}:${DLM_PORT}:37373" >/dev/null
    fi

    podman run --replace -d \
        --name "${POD}-dlm" \
        --pod "$POD" \
        --env DLM_PORT=37373 \
        "$IMAGE" dlm >/dev/null

    gateway_env=()
    if [ -f "$GATEWAY_ENV_FILE" ]; then
        gateway_env=(--env-file "$GATEWAY_ENV_FILE")
    fi

    podman run --replace -d \
        --name "${POD}-gateway" \
        --pod "$POD" \
        "${gateway_env[@]}" \
        --env GATEWAY_PORT=8080 \
        --env RAW_TCP_PORT=37374 \
        --env DLM_HOST=127.0.0.1 \
        --env DLM_PORT=37373 \
        --env DLM_RETRY="${DLM_RETRY:-1}" \
        --env DLM_RETRY_SLEEP="${DLM_RETRY_SLEEP:-0.2}" \
        --env DLM_TIMEOUT="${DLM_TIMEOUT:-2}" \
        "$IMAGE" gateway >/dev/null

    printf 'Wonderland gateway: http://%s:%s/v1 (model: wonderland)\n' "$BIND" "$GATEWAY_PORT"
}

stop_stack() {
    podman pod stop "$POD" >/dev/null 2>&1 || true
    podman pod rm "$POD" >/dev/null 2>&1 || true
}

status_stack() {
    podman pod ps --filter "name=$POD"
    podman ps --filter "pod=$POD"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "http://${BIND}:${GATEWAY_PORT}/health" || true
        printf '\n'
    fi
}

case "${1:-start}" in
    build)
        build_image
        ;;
    start)
        start_stack
        ;;
    restart)
        stop_stack
        start_stack
        ;;
    stop)
        stop_stack
        ;;
    status)
        status_stack
        ;;
    logs)
        podman logs -f "${POD}-gateway"
        ;;
    print-env)
        cat "$ROOT_DIR/container/wonderland.env"
        ;;
    configure-hermes)
        "$ROOT_DIR/container/configure-hermes.py"
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        usage
        exit 2
        ;;
esac

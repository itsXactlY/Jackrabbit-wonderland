FROM python:3.14-slim

ARG JACKRABBITDLM_REPO=https://github.com/rapmd73/JackrabbitDLM.git
ARG JACKRABBITDLM_REF=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HERMES_CRYPTO_HOME=/opt/hermes-crypto \
    JACKRABBITDLM_HOME=/home/JackrabbitDLM \
    GATEWAY_PORT=8080 \
    RAW_TCP_PORT=37374 \
    DLM_HOST=127.0.0.1 \
    DLM_PORT=37373 \
    DLM_RETRY=1 \
    DLM_RETRY_SLEEP=0.2 \
    DLM_TIMEOUT=2 \
    SESSION_TTL=3000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir pycryptodome psutil \
    && git clone --depth 1 "$JACKRABBITDLM_REPO" "$JACKRABBITDLM_HOME" \
    && if [ -n "$JACKRABBITDLM_REF" ]; then \
        cd "$JACKRABBITDLM_HOME"; \
        git fetch --depth 1 origin "$JACKRABBITDLM_REF"; \
        git checkout FETCH_HEAD; \
    fi

WORKDIR /opt/hermes-crypto
COPY crypto_middleware.py remember_protocol.py dlm_vault.py crypto_plugin.py lan_gateway.py ./
COPY tests ./tests
COPY container/entrypoint.sh /usr/local/bin/hermes-crypto

RUN chmod +x /usr/local/bin/hermes-crypto \
    && mkdir -p "$JACKRABBITDLM_HOME/Logs" "$JACKRABBITDLM_HOME/Disk" "$JACKRABBITDLM_HOME/Quarantine"

EXPOSE 8080 37373 37374

ENTRYPOINT ["/usr/local/bin/hermes-crypto"]
CMD ["gateway"]

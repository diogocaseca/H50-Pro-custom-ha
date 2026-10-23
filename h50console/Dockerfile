# App do Home Assistant: o Supervisor constrói com o contexto restrito a esta pasta. O código do painel vem do projeto
# original (nathanabreu/H50-Pro-custom) num commit fixo (H50_COMMIT em build.yaml) e recebe os patches de patches/.
#
# Na raiz deste repositório:
#   H50_COMMIT=$(sed -n 's/^ *H50_COMMIT: *//p' h50console/build.yaml)
#   docker build --build-arg H50_COMMIT=$H50_COMMIT --target test h50console       # testes do código com patch
#   docker build --build-arg H50_COMMIT=$H50_COMMIT -t h50console-app h50console   # imagem final
# Com uma cópia local do original no lugar do download (os patches continuam sendo aplicados; H50_COMMIT não é usado).
# Exporte sem o .dockerignore do original, que exclui tests/ e quebraria os patches:
#   mkdir /tmp/h50-up && git -C ../H50-Pro-custom archive <commit> | tar -x -C /tmp/h50-up && rm /tmp/h50-up/.dockerignore
#   docker build --build-context upstream=/tmp/h50-up --target test h50console
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.22

# ---- original, sem alterações ----------------------------------------------------------------------------------------
FROM ${BUILD_FROM} AS download
ARG H50_REPO=https://github.com/nathanabreu/H50-Pro-custom
ARG H50_COMMIT
RUN case "${H50_COMMIT}" in \
      *[!0-9a-f]*|"") echo "H50_COMMIT precisa ser o SHA completo (40 caracteres) do original; veja build.yaml" >&2; exit 1 ;; \
    esac \
    && [ "${#H50_COMMIT}" -eq 40 ] || { echo "H50_COMMIT precisa ter 40 caracteres: '${H50_COMMIT}'" >&2; exit 1; } \
    && mkdir /src \
    && curl -fsSL "${H50_REPO}/archive/${H50_COMMIT}.tar.gz" | tar -xz -C /src --strip-components=1

# raiz do original (mesmo layout de --build-context upstream=<pasta>, que substitui este estágio e o download)
FROM scratch AS upstream
COPY --from=download /src/ /

# ---- original + patches --------------------------------------------------------------------------------------------
FROM ${BUILD_FROM} AS src
RUN apk add --no-cache patch
COPY --from=upstream / /src/
COPY patches/ /patches/
WORKDIR /src
# Em ordem; qualquer trecho que não aplique exatamente (sem fuzz) falha o build.
RUN set -e; for p in /patches/*.patch; do \
      echo "aplicando ${p##*/}"; \
      patch -p1 --forward --batch --fuzz=0 --no-backup-if-mismatch < "$p"; \
    done

# ---- testes: docker build --target test ----------------------------------------------------------------------------
FROM ${BUILD_FROM} AS test
ENV PYTHONDONTWRITEBYTECODE=1
COPY --from=src /src /src
WORKDIR /src
RUN python3 -m unittest -v
# ponte MQTT do app (usa o código do painel já com patch; não precisa do paho)
COPY mqtt_bridge.py /app-src/
COPY tests/ /app-src/tests/
RUN PYTHONPATH=/src:/app-src python3 -m unittest discover -v -s /app-src/tests

# ---- imagem final ---------------------------------------------------------------------------------------------------
FROM ${BUILD_FROM}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=src /src/pyproject.toml /src/README.md /src/LICENSE ./
COPY --from=src /src/h50console ./h50console
RUN pip install --no-cache-dir . paho-mqtt==2.1.0 && rm -rf /app/build
COPY run.py mqtt_bridge.py /
ARG BUILD_VERSION
ENV H50_APP_VERSION=${BUILD_VERSION}

# /data é persistente e entra no backup do HA (tokens, bancos, sessão da nuvem, mapas)
CMD ["python3", "/run.py"]

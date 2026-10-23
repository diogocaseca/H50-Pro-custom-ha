# App do Home Assistant: o Supervisor constrói com o contexto restrito a esta pasta, então o código do painel vem
# do GitHub (tag fixa em build.yaml). Para testar com o código local (na raiz do repositório):
#   docker build --build-context src=. --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.22 \
#                -t h50console-app h50console_app
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.22

# ---- código-fonte (substituível por --build-context src=<pasta>) ------------------------------------------------
FROM ${BUILD_FROM} AS download
ARG H50_REPO=https://github.com/diogocaseca/H50-Pro-custom
ARG H50_REF=app-v0.1.0
ADD ${H50_REPO}/archive/${H50_REF}.tar.gz /tmp/src.tar.gz
RUN mkdir /src && tar -xzf /tmp/src.tar.gz -C /src --strip-components=1

# raiz do repositório (mesmo layout de --build-context src=.)
FROM scratch AS src
COPY --from=download /src/ /

# ---- imagem final ---------------------------------------------------------------------------------------------------
FROM ${BUILD_FROM}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=src /pyproject.toml /README.md /LICENSE ./
COPY --from=src /h50console ./h50console
RUN pip install --no-cache-dir . && rm -rf /app/build
COPY run.py /run.py

# /data é persistente e entra no backup do HA (tokens, bancos, sessão da nuvem, mapas)
CMD ["python3", "/run.py"]

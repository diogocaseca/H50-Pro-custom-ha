# H50 Console para o Home Assistant

Repositório de app do Home Assistant (antigo "add-on") com o **H50 Console**, o painel local para aspiradores Xiaomi
**H50 Pro** (`xiaomi.vacuum.ov42gl`) de [nathanabreu/H50-Pro-custom](https://github.com/nathanabreu/H50-Pro-custom).
O painel aparece na barra lateral do HA (Ingress, com o login e o HTTPS do próprio HA) e controla o robô **100% pela
rede local** (UDP 54321). A nuvem Xiaomi só é usada para baixar o mapa e trazer o token ao cadastrar o robô.

Este repositório **não contém cópia do código do painel**: o build baixa o original num commit fixo e aplica pequenos
patches para rodar atrás do Ingress.

## Instalação no Home Assistant

1. **Configurações → Apps → Loja de apps**.
2. Menu **⋮ → Repositórios**, adicione `https://github.com/diogocaseca/H50-Pro-custom-ha` e feche.
3. Procure **H50 Console**, clique em **Instalar** e depois em **Iniciar**. Ative **Mostrar na barra lateral**.

Primeiro uso, opções e segurança: [h50console/DOCS.md](h50console/DOCS.md).

## Como funciona

```
repository.yaml            # descreve o repositório para o Supervisor
h50console/                # o app (slug h50console); é o contexto de build do Supervisor
  config.yaml build.yaml   # build.yaml → args.H50_COMMIT: commit do original usado no build
  Dockerfile  run.py      # run.py lê as opções; com mqtt ligado, sobe o painel e a ponte
  mqtt_bridge.py tests/    # ponte MQTT (discovery) e os testes dela
  patches/0001-…0008-…     # mudanças sobre o original (git format-patch), aplicadas em ordem
tools/update-upstream.sh   # move os patches para um commit novo do original
```

O Supervisor do HA constrói a imagem usando **só** a pasta `h50console/`, por isso os patches ficam dentro dela.
O [Dockerfile](h50console/Dockerfile):

1. baixa `https://github.com/nathanabreu/H50-Pro-custom/archive/<H50_COMMIT>.tar.gz`;
2. aplica `patches/*.patch` em ordem com `patch -p1 --forward --fuzz=0`; se algum trecho não aplicar, **o build falha**
   (nunca sai uma imagem com o código pela metade);
3. instala o pacote na imagem base Python do HA e sobe com `run.py`, que lê as opções do app.

Os patches (todos opt-in: sem as variáveis de ambiente, o painel se comporta exatamente como o original):

| Patch | O quê |
|---|---|
| 0001 | Front com caminhos relativos, para rodar atrás de um prefixo (`/api/hassio_ingress/<token>/`) |
| 0002 | Redirecionamento relativo para a página de login |
| 0003 | Modo Ingress (`H50_INGRESS`, `H50_INGRESS_ONLY`) e `H50_LOG_LEVEL`, com testes |
| 0004 | Servidor da nuvem Xiaomi fixo (`H50_CLOUD_COUNTRY`; opção `cloud_region` do app), com testes |
| 0005 | API local por token (`H50_API_TOKEN`, só de `127.0.0.1`), usada pela ponte MQTT, com testes |
| 0006 | Perfil operador e perfis pelo usuário do HA no Ingress (`H50_INGRESS_ADMINS`, `H50_INGRESS_OTHERS`), com testes |
| 0007 | Rotina personalizada aplica o modo de limpeza da rotina (2/4) antes de limpar os cômodos; recusa rotina com modos diferentes por cômodo, com testes |
| 0008 | Teste da limpeza por zona (ação 2/37, formato do xiaomi-vac nos modelos irmãos) com as zonas capturadas do app Xiaomi Home, com testes |

A **ponte MQTT** ([h50console/mqtt_bridge.py](h50console/mqtt_bridge.py), opção `mqtt` do app) é código deste
repositório, não um patch: ela só usa a API HTTP do painel, então não conflita com atualizações do original. Os testes
dela ficam em `h50console/tests/` e rodam no mesmo `docker build --target test`.

## Testar localmente

Na raiz deste repositório:

```bash
H50_COMMIT=$(sed -n 's/^ *H50_COMMIT: *//p' h50console/build.yaml)
docker build --build-arg H50_COMMIT=$H50_COMMIT --target test h50console       # testes do original, dos patches e da ponte
docker build --build-arg H50_COMMIT=$H50_COMMIT -t h50console-app h50console   # imagem final (amd64)
```

Para usar uma cópia local do original no lugar do download, veja o topo do Dockerfile (`--build-context upstream=`).

## Atualizar quando o original mudar

Para saber se há novidade:

```bash
tools/check-upstream.sh
```

Ele compara o `H50_COMMIT` do `build.yaml` com o último commit do original e, se houver commits novos, lista os
commits e os arquivos alterados (marcando com `*` os que os nossos patches também mexem) e testa, numa cópia temporária,
se os patches aplicam sobre o commit mais novo. Não altera nada aqui. Código de saída: `0` em dia, `10` há atualização e
os patches aplicam, `11` há atualização com conflito, `1` erro. `--quiet` imprime só uma linha (para cron ou CI) e
`--update` já atualiza quando não há conflito.

Para atualizar:

```bash
tools/update-upstream.sh <commit-novo-do-original>
```

O script clona o original, aplica os patches com `git am --3way` sobre o commit novo e, se tudo aplicar, regera
`h50console/patches/` e atualiza `H50_COMMIT` no `build.yaml`. Se houver conflito, ele para, deixa o clone numa pasta
temporária e explica como resolver e concluir (`tools/update-upstream.sh --finish <pasta>`). Depois:

1. rode o `docker build --target test` acima;
2. suba `version` em `h50console/config.yaml` (é o que faz o HA oferecer a atualização) e registre no
   `h50console/CHANGELOG.md`;
3. faça o commit e o push.

## Licença

MIT. Código do painel © Nathan Dame Abreu ([nathanabreu/H50-Pro-custom](https://github.com/nathanabreu/H50-Pro-custom));
patches e app do Home Assistant © Diogo Caseca. Veja [LICENSE](LICENSE).

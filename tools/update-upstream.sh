#!/usr/bin/env bash
# Move os patches de h50console/patches/ para um commit novo do original (nathanabreu/H50-Pro-custom).
#
#   tools/update-upstream.sh <commit>          clona o original, aplica os patches (git am) sobre <commit> e, se
#                                              aplicarem, regera h50console/patches/ e atualiza H50_COMMIT no build.yaml
#   tools/update-upstream.sh --finish <pasta>  depois de resolver um conflito na <pasta> indicada, conclui o passo acima
#
# UPSTREAM_REPO troca a origem do clone (URL ou caminho local). Não faz commit: revise com `git diff` e rode
# `docker build --target test` antes.
set -euo pipefail

UPSTREAM_REPO=${UPSTREAM_REPO:-https://github.com/nathanabreu/H50-Pro-custom}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PATCHES=$ROOT/h50console/patches
BUILD_YAML=$ROOT/h50console/build.yaml

die() { echo "erro: $*" >&2; exit 1; }
usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

# git am precisa de um committer; a autoria dos patches é preservada
GIT_ID=(-c "user.name=$(git -C "$ROOT" config user.name || echo h50)" -c "user.email=$(git -C "$ROOT" config user.email || echo h50@localhost)")

finish() {   # $1 = clone com os patches aplicados em cima do commit-base (gravado em .git/h50-base)
    local work=$1 base
    base=$(cat "$work/.git/h50-base" 2>/dev/null) || die "$work não foi criado por este script"
    [ -d "$work/.git/rebase-apply" ] && die "o git am ainda não terminou em $work (resolva e rode git am --continue)"
    git -C "$work" diff --quiet HEAD || die "há alterações não commitadas em $work"

    local n
    n=$(git -C "$work" rev-list --count "$base..HEAD")
    [ "$n" -gt 0 ] || die "nenhum patch sobre $base em $work"

    rm -f "$PATCHES"/*.patch
    git -C "$work" format-patch "$base..HEAD" -o "$PATCHES" >/dev/null
    sed -i -E "s/^( *H50_COMMIT: *)[0-9a-f]+/\1$base/" "$BUILD_YAML"
    grep -q "H50_COMMIT: $base\$" "$BUILD_YAML" || die "não consegui atualizar H50_COMMIT em $BUILD_YAML"

    rm -rf "$work"
    echo
    echo "ok: $n patch(es) regerados em h50console/patches/ sobre $base; H50_COMMIT atualizado no build.yaml."
    echo "Próximos passos:"
    echo "  git -C '$ROOT' status && git -C '$ROOT' diff --stat"
    echo "  docker build --build-arg H50_COMMIT=$base --target test '$ROOT/h50console'"
    echo "  suba \`version\` em h50console/config.yaml, registre no h50console/CHANGELOG.md e faça o commit."
}

case "${1:-}" in
    ""|-h|--help) usage ;;
    --finish) [ -n "${2:-}" ] || usage; finish "$(cd "$2" && pwd)"; exit ;;
esac

commit=$1
compgen -G "$PATCHES/*.patch" >/dev/null || die "nenhum patch em $PATCHES"

work=$(mktemp -d "${TMPDIR:-/tmp}/h50-upstream.XXXXXX")
echo "clonando $UPSTREAM_REPO em $work ..."
git clone -q "$UPSTREAM_REPO" "$work"
base=$(git -C "$work" rev-parse --verify -q "$commit^{commit}") || { rm -rf "$work"; die "commit '$commit' não existe em $UPSTREAM_REPO"; }
echo "$base" > "$work/.git/h50-base"
git -C "$work" checkout -q -b h50-patches "$base"

echo "aplicando os patches sobre $base ..."
if ! git "${GIT_ID[@]}" -C "$work" am -q --3way "$PATCHES"/*.patch; then
    cat >&2 <<EOF

Conflito: algum patch não aplica sobre $base (veja a mensagem do git acima).
O clone ficou em: $work

Para resolver:
  cd $work
  git status                       # arquivos em conflito
  (edite os arquivos, rode os testes com: python -m unittest)
  git add <arquivos> && git am --continue    # repita até aplicar todos
  # ou: git am --skip (o patch não é mais necessário) / git am --abort (desistir)
Depois:
  $0 --finish $work
EOF
    exit 1
fi
finish "$work"

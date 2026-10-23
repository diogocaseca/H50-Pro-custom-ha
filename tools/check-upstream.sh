#!/usr/bin/env bash
# Verifica se o original (nathanabreu/H50-Pro-custom) tem commits depois do H50_COMMIT do build.yaml e se os nossos
# patches ainda aplicam sobre o commit mais novo. Não altera nada neste repositório (a não ser com --update).
#
#   tools/check-upstream.sh            commits novos, arquivos alterados (os que os patches também mexem em destaque)
#                                      e o teste dos patches sobre o commit mais novo
#   tools/check-upstream.sh --quiet    só uma linha de resumo e o código de saída (para cron ou CI)
#   tools/check-upstream.sh --update   se os patches aplicam, já roda tools/update-upstream.sh <commit novo>
#
# Código de saída: 0 = em dia; 10 = há atualização e os patches aplicam; 11 = há atualização, mas algum patch não
# aplica (use tools/update-upstream.sh e resolva o conflito); 1 = erro.
# UPSTREAM_REPO troca a origem (URL ou caminho local); UPSTREAM_BRANCH, o branch (padrão: o principal do original).
set -euo pipefail

UPSTREAM_REPO=${UPSTREAM_REPO:-https://github.com/nathanabreu/H50-Pro-custom}
UPSTREAM_BRANCH=${UPSTREAM_BRANCH:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PATCHES=$ROOT/h50console/patches
BUILD_YAML=$ROOT/h50console/build.yaml

quiet=0 update=0
for arg in "$@"; do
    case "$arg" in
        --quiet) quiet=1 ;;
        --update) update=1 ;;
        -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "opção desconhecida: $arg (veja --help)" >&2; exit 1 ;;
    esac
done

say() { [ "$quiet" = 1 ] || echo "$@"; }
die() { echo "erro: $*" >&2; exit 1; }

current=$(sed -n 's/^ *H50_COMMIT: *\([0-9a-f]\{40\}\).*/\1/p' "$BUILD_YAML")
[ -n "$current" ] || die "não achei H50_COMMIT (SHA completo) em $BUILD_YAML"

ref=${UPSTREAM_BRANCH:+refs/heads/$UPSTREAM_BRANCH}
latest=$(git ls-remote "$UPSTREAM_REPO" "${ref:-HEAD}" | awk 'NR==1 {print $1}')
[ -n "$latest" ] || die "não consegui ler ${ref:-HEAD} de $UPSTREAM_REPO"

if [ "$latest" = "$current" ]; then
    [ "$quiet" = 1 ] && echo "em dia: ${current:0:7}" || echo "Em dia: o original continua em ${current:0:7} (H50_COMMIT do build.yaml)."
    exit 0
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/h50-check.XXXXXX")
trap 'rm -rf "$work"' EXIT
git clone -q "$UPSTREAM_REPO" "$work/up"
up() { git -C "$work/up" "$@"; }
up cat-file -e "$current^{commit}" 2>/dev/null || die "o commit atual ${current:0:7} não existe mais no original"

n=$(up rev-list --count "$current..$latest")
say "Há atualização no original: ${current:0:7} -> ${latest:0:7} ($n commit(s) novo(s))."
if ! up merge-base --is-ancestor "$current" "$latest"; then
    say "ATENÇÃO: ${current:0:7} não é ancestral de ${latest:0:7} (o histórico do original foi reescrito)."
fi

if [ "$quiet" = 0 ]; then
    echo
    echo "Commits novos:"
    up log --no-merges --format='  %h %ad %an: %s' --date=short "$current..$latest"
    echo
    # arquivos que os nossos patches alteram: mudanças neles são as que podem dar conflito
    ours=$(grep -h '^diff --git a/' "$PATCHES"/*.patch | sed 's#^diff --git a/\([^ ]*\) .*#\1#' | sort -u)
    echo "Arquivos alterados (* = também alterado pelos nossos patches):"
    while IFS= read -r line; do
        file=${line%%|*}; file=${file## }; file=${file%% }
        mark=" "
        grep -qxF "$file" <<<"$ours" && mark="*"
        echo " $mark$line"
    done < <(up diff --stat=200 "$current" "$latest" | sed '$d')
    up diff --shortstat "$current" "$latest" | sed 's/^/  /'
    echo
fi

# teste dos patches sobre o commit mais novo (mesmo git am --3way do update-upstream.sh)
up checkout -q -b h50-check "$latest"
id=(-c "user.name=h50-check" -c "user.email=h50-check@localhost")
if git "${id[@]}" -C "$work/up" am -q --3way "$PATCHES"/*.patch >"$work/am.log" 2>&1; then
    if [ "$quiet" = 1 ]; then
        echo "atualização disponível: ${current:0:7} -> ${latest:0:7} ($n commits); patches aplicam"
    else
        echo "Os $(ls "$PATCHES"/*.patch | wc -l) patches aplicam sobre ${latest:0:7} sem conflito."
    fi
    status=10
else
    failed=$(sed -n 's/^Patch failed at \(.*\)$/\1/p' "$work/am.log" | head -1)
    if [ "$quiet" = 1 ]; then
        echo "atualização disponível: ${current:0:7} -> ${latest:0:7} ($n commits); CONFLITO no patch ${failed:-?}"
    else
        echo "CONFLITO: o patch ${failed:-?} não aplica sobre ${latest:0:7}. Arquivos em conflito:"
        up diff --name-only --diff-filter=U | sed 's/^/  /'
    fi
    status=11
fi

if [ "$update" = 1 ]; then
    if [ "$status" = 10 ]; then
        say
        say "Atualizando (tools/update-upstream.sh $latest)..."
        UPSTREAM_REPO=$UPSTREAM_REPO "$ROOT/tools/update-upstream.sh" "$latest"
        exit 0
    fi
    say "Não atualizei por causa do conflito."
fi

if [ "$quiet" = 0 ]; then
    echo
    if [ "$status" = 10 ]; then
        echo "Para atualizar: tools/check-upstream.sh --update   (ou tools/update-upstream.sh $latest)"
    else
        echo "Para atualizar: tools/update-upstream.sh $latest   (ele para no conflito e explica como resolver)"
    fi
fi
exit "$status"

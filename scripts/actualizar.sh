#!/usr/bin/env bash
# Corre en la VPS (cron): baja los resultados de promiedos y, si cambió algo, sube resultados.json al repo.
# Netlify y Vercel se republican solos con cada push. Usar en un clon dedicado: descarta cambios locales.
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH="${BRANCH:-claude/simulador-clausura-2026}"
exec 9>/tmp/simuladorlpf.lock
flock -n 9 || exit 0 # si la corrida anterior sigue, no se pisan

git fetch -q origin "$BRANCH"
git reset -q --hard "origin/$BRANCH"
python3 scripts/promiedos.py resultados.json

git diff --quiet -- resultados.json && exit 0
git add resultados.json
git -c user.name="Resultados VPS" -c user.email="resultados@simulpf.local" commit -qm "Resultados de promiedos"
for i in 1 2 3; do
  git push -q origin "HEAD:$BRANCH" && exit 0
  sleep 5
  git pull -q --rebase origin "$BRANCH"
done
echo "no se pudo subir resultados.json" >&2
exit 1

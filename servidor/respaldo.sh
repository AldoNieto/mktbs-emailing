#!/usr/bin/env bash
# Respaldo diario de la base de listmonk, pensado para correr DESDE el Mac mini
# (launchd o cron): trae un volcado comprimido del servidor y guarda 30 días.
#
#   SERVIDOR=usuario@ip-del-vps  DESTINO=~/MktBs-Direccion/_respaldos/emailing  ./respaldo.sh
set -euo pipefail
: "${SERVIDOR:?definí SERVIDOR=usuario@host}"
DESTINO="${DESTINO:-$HOME/MktBs-Direccion/_respaldos/emailing}"
CARPETA="${CARPETA_REMOTA:-~/emailing}"
mkdir -p "$DESTINO"
archivo="$DESTINO/listmonk-$(date +%Y-%m-%d).sql.gz"
ssh "$SERVIDOR" "cd $CARPETA && docker compose exec -T db pg_dump -U listmonk listmonk" | gzip > "$archivo"
test -s "$archivo"
find "$DESTINO" -name 'listmonk-*.sql.gz' -mtime +30 -delete
echo "respaldo → $archivo"

#!/usr/bin/env bash
# Backup do banco via mysqldump, contra um endpoint MySQL ALCANÇÁVEL.
#
# Use quando houver um proxy TCP público do Railway habilitado (ou qualquer
# host MySQL acessível). Lê a URL de conexão, nesta ordem de precedência:
#   1) primeiro argumento da linha de comando
#   2) variável de ambiente BACKUP_DATABASE_URL
#   3) variável de ambiente DATABASE_URL
#
# Formato da URL: mysql://usuario:senha@host:porta/nome_do_banco
#
# Gera: backups/observatorio_AAAAMMDD_HHMMSS.sql.gz
# Mantém apenas os últimos KEEP backups (padrão 14).
#
# Exemplos:
#   ./scripts/backup_db.sh "mysql://root:senha@gondola.proxy.rlwy.net:54321/railway"
#   BACKUP_DATABASE_URL="mysql://..." ./scripts/backup_db.sh
set -euo pipefail

KEEP="${KEEP:-14}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"

URL="${1:-${BACKUP_DATABASE_URL:-${DATABASE_URL:-}}}"
if [ -z "$URL" ]; then
    echo "Erro: nenhuma URL de conexão fornecida." >&2
    echo "Passe como argumento ou defina BACKUP_DATABASE_URL / DATABASE_URL." >&2
    exit 1
fi

# Parsing de mysql://user:pass@host:port/db (aceita mysql+pymysql://)
no_proto="${URL#*://}"
creds="${no_proto%@*}"
hostpart="${no_proto#*@}"
user="${creds%%:*}"
pass="${creds#*:}"
hostport="${hostpart%%/*}"
dbname="${hostpart#*/}"; dbname="${dbname%%\?*}"
host="${hostport%%:*}"
port="${hostport#*:}"
[ "$port" = "$host" ] && port=3306

if [ -z "$host" ] || [ -z "$dbname" ]; then
    echo "Erro: não foi possível interpretar a URL de conexão." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
ts="$(date +%Y%m%d_%H%M%S)"
out="$BACKUP_DIR/observatorio_${ts}.sql.gz"

echo "Fazendo backup de '$dbname' em $host:$port ..." >&2
MYSQL_PWD="$pass" mysqldump \
    --host="$host" --port="$port" --user="$user" \
    --single-transaction --routines --triggers --no-tablespaces \
    --column-statistics=0 \
    "$dbname" | gzip -9 > "$out"

size="$(du -h "$out" | cut -f1)"
echo "OK — $out ($size)" >&2

# Retenção: mantém os KEEP mais recentes
mapfile -t old < <(ls -1t "$BACKUP_DIR"/observatorio_*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))")
if [ "${#old[@]}" -gt 0 ]; then
    rm -f "${old[@]}"
    echo "Removidos ${#old[@]} backup(s) antigo(s) (mantendo $KEEP)." >&2
fi

# Upload opcional para o Google Drive (se RCLONE_REMOTE estiver definido e
# rclone disponível). Use, por ex.: RCLONE_REMOTE=gdrive:Backups-Observatorio
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then
    echo "Enviando para $RCLONE_REMOTE ..." >&2
    rclone copy "$out" "$RCLONE_REMOTE" && echo "Enviado ao Drive: $RCLONE_REMOTE" >&2
fi

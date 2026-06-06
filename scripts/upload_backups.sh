#!/usr/bin/env bash
# Envia os backups locais para o Google Drive via rclone.
#
# Usa `rclone copy` (não `sync`): só envia arquivos novos e NUNCA apaga nada
# que já esteja no Drive — assim a retenção local (que remove dumps antigos)
# não afeta o histórico guardado na nuvem.
#
# Pré-requisito: rclone configurado com um remote (ver BACKUP.md).
# Remote padrão: gdrive:Backups-Observatorio (sobrescreva com RCLONE_REMOTE).
set -euo pipefail

REMOTE="${RCLONE_REMOTE:-gdrive:Backups-Observatorio}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups"

if ! command -v rclone >/dev/null 2>&1; then
    echo "Erro: rclone não encontrado no PATH." >&2
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Erro: pasta de backups não existe: $BACKUP_DIR" >&2
    exit 1
fi

echo "Enviando backups para $REMOTE ..." >&2
rclone copy -v "$BACKUP_DIR" "$REMOTE" --include "observatorio_*.sql.gz"
echo "OK — backups sincronizados em $REMOTE" >&2

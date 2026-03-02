#!/bin/bash
# =============================================================================
# NEXUS — Backup PostgreSQL
# =============================================================================
# Uso:
#   ./scripts/backup_postgres.sh                  (backup local)
#   ./scripts/backup_postgres.sh --docker          (backup dentro do docker-compose)
#
# Configuração via variáveis de ambiente:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
#   BACKUP_DIR (padrão: ./backups)
#   BACKUP_RETENTION_DAYS (padrão: 30)
# =============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/nexus_backup_${TIMESTAMP}.sql.gz"

# Defaults para Docker local
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-nexus}"
PGPASSWORD="${PGPASSWORD:-nexus_secret}"
PGDATABASE="${PGDATABASE:-nexus}"

mkdir -p "$BACKUP_DIR"

echo "🔄 Iniciando backup PostgreSQL..."
echo "   Host: ${PGHOST}:${PGPORT}"
echo "   Database: ${PGDATABASE}"
echo "   Destino: ${BACKUP_FILE}"

if [[ "${1:-}" == "--docker" ]]; then
    # Backup via docker-compose
    docker compose exec -T postgres pg_dump \
        -U "$PGUSER" \
        -d "$PGDATABASE" \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists | gzip > "$BACKUP_FILE"
else
    # Backup direto
    PGPASSWORD="$PGPASSWORD" pg_dump \
        -h "$PGHOST" \
        -p "$PGPORT" \
        -U "$PGUSER" \
        -d "$PGDATABASE" \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists | gzip > "$BACKUP_FILE"
fi

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup concluído: ${BACKUP_FILE} (${FILESIZE})"

# Limpeza de backups antigos
DELETED=$(find "$BACKUP_DIR" -name "nexus_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
if [[ "$DELETED" -gt 0 ]]; then
    echo "🧹 Removidos ${DELETED} backups com mais de ${RETENTION_DAYS} dias"
fi

echo "📊 Backups atuais:"
ls -lh "$BACKUP_DIR"/nexus_backup_*.sql.gz 2>/dev/null || echo "   Nenhum backup encontrado"

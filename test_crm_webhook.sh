#!/usr/bin/env bash
set -euo pipefail

# Script para testar o webhook de CRM (SprintHub) localmente ou em produção.
#
# Uso:
#   APP_SECRET=... ./test_crm_webhook.sh <URL_BASE> <NUMERO_LEAD> <CURSO>
#
# Exemplos:
#   APP_SECRET=dev-secret ./test_crm_webhook.sh http://localhost:8000 5511999999999 pos_fisio_neuro
#   APP_SECRET=super-secreto ./test_crm_webhook.sh https://seu-dominio.com 5511999999999 curso_1

URL_BASE="${1:-}"
PHONE="${2:-}"
COURSE="${3:-}"
APP_SECRET="${APP_SECRET:-}"

if [[ -z "$URL_BASE" || -z "$PHONE" || -z "$COURSE" ]]; then
  echo "Uso: APP_SECRET=... $0 <URL_BASE> <NUMERO_LEAD> <CURSO>"
  exit 1
fi

if [[ -z "$APP_SECRET" ]]; then
  echo "Erro: defina APP_SECRET no ambiente (APP_SECRET=...)." >&2
  exit 1
fi

PRODUCT_NAME="$COURSE"

echo "🚀 Testando webhook CRM em: $URL_BASE/webhook/sprinthub"
echo "📱 Lead: $PHONE"
echo "📚 Curso: $COURSE"

curl -sS -X POST "$URL_BASE/webhook/sprinthub" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Key: $APP_SECRET" \
  -d "{
    \"lead\": {
      \"whatsapp\": \"$PHONE\",
      \"nome\": \"Lead Teste\"
    },
    \"campos_customizados\": {
      \"informacao05\": \"$PRODUCT_NAME\"
    }
  }" | cat

echo

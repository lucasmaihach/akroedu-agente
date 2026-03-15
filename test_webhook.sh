#!/bin/bash

# Script para testar o webhook localmente com ngrok ou em produção
# Uso: ./test_webhook.sh <URL_BASE> <NUMERO_LEAD>
# Exemplo: ./test_webhook.sh http://localhost:8000 5511999999999

URL_BASE="${1:-http://localhost:8000}"
PHONE="${2:-5511999999999}"
MESSAGE="${3:-Oi, quero saber sobre o MBA}"

echo "🚀 Testando webhook em: $URL_BASE"
echo "📱 Lead: $PHONE"
echo "💬 Mensagem: $MESSAGE"
echo ""

# Payload do webhook exatamente como a Meta envia
PAYLOAD=$(cat <<EOF
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "123456789",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "554799999999",
              "phone_number_id": "1234567890"
            },
            "contacts": [
              {
                "profile": {
                  "name": "João Silva"
                },
                "wa_id": "$PHONE"
              }
            ],
            "messages": [
              {
                "from": "$PHONE",
                "id": "wamid.HBEUGVFhAhERAhEVJRVS=$(date +%s)",
                "timestamp": "$(date +%s)",
                "type": "text",
                "text": {
                  "body": "$MESSAGE"
                }
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
EOF
)

# Envia a requisição
echo "📤 Enviando webhook..."
echo ""

curl -X POST "$URL_BASE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -v

echo ""
echo ""
echo "✅ Webhook enviado!"
echo "Verifique os logs: docker-compose logs -f api"

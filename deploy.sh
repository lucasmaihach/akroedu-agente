#!/bin/bash
# Script de deploy — executa no servidor (não na sua máquina local)
# Uso: bash deploy.sh

set -e

echo "🚀 Iniciando deploy..."

# Puxa código mais recente
git pull origin main

# Recria a imagem e reinicia o serviço
docker-compose -f docker-compose.prod.yml up -d --build api

echo "✅ Deploy concluído!"
echo "📋 Status dos containers:"
docker-compose -f docker-compose.prod.yml ps

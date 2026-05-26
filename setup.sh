#!/usr/bin/env bash
# setup.sh — Inicialitza l'entorn de desenvolupament per al Smart-Claims Agent
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${GREEN}▶ Smart-Claims Agent — Setup d'entorn${NC}"
echo "────────────────────────────────────────"

# 1. Crea el .env a partir de l'exemple
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠  .env creat des de .env.example — afegeix la teva ANTHROPIC_API_KEY${NC}"
else
    echo "✓ .env ja existeix"
fi

# 2. Crea els __init__.py necessaris
touch backend/app/__init__.py
touch backend/app/agents/__init__.py
touch backend/app/tools/__init__.py
touch backend/app/rag/__init__.py
touch backend/app/db/__init__.py
touch backend/app/routers/__init__.py
echo "✓ Fitxers __init__.py creats"

# 3. Crea directoris de dades
mkdir -p data/synthetic data/policies
echo "✓ Directoris data/ creats"

# 4. Verifica Docker i Docker Compose
if ! command -v docker &> /dev/null; then
    echo "✗ Docker no trobat. Instal·la Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi
echo "✓ Docker disponible ($(docker --version))"

# 5. Build i arrancada
echo ""
echo -e "${GREEN}▶ Construint i arrencant serveis...${NC}"
docker compose build --quiet
docker compose up -d

echo ""
echo -e "${GREEN}✅ Entorn llest!${NC}"
echo "────────────────────────────────────────"
echo "  Backend API:  http://localhost:8000/docs"
echo "  Streamlit UI: http://localhost:8501"
echo "  ChromaDB:     http://localhost:8080"
echo "  Adminer (DB): http://localhost:8082"
echo ""
echo "  Logs:   docker compose logs -f backend"
echo "  Stop:   docker compose down"

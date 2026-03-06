#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Indevolt Dashboard — Setup
# ─────────────────────────────────────────────────────────

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "  ⚡ Indevolt Dashboard — Installation"
echo "  ─────────────────────────────────────"
echo ""

# ── Vérifier Docker ────────────────────────────────────
if ! command -v docker &> /dev/null; then
  echo -e "${RED}✗ Docker non trouvé. Installez Docker : https://docs.docker.com/get-docker/${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Docker$(docker --version | grep -o ' [0-9.]*' | head -1)${NC}"

# ── Vérifier Docker Compose ────────────────────────────
if ! docker compose version &> /dev/null 2>&1; then
  echo -e "${RED}✗ Docker Compose v2 non trouvé.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Docker Compose $(docker compose version --short 2>/dev/null || echo 'v2')${NC}"

# ── Vérifier le port 8480 ──────────────────────────────
if lsof -Pi :8480 -sTCP:LISTEN -t &> /dev/null 2>&1; then
  echo -e "${YELLOW}⚠ Port 8480 déjà utilisé. Modifiez docker-compose.yml (ports: \"XXXX:80\")${NC}"
fi

# ── Créer les dossiers nécessaires ─────────────────────
mkdir -p data/store
echo -e "${GREEN}✓ Dossier data/store/ créé${NC}"

# ── Détecter l'IP locale ───────────────────────────────
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "votre-ip")

# ── Lancer les conteneurs ──────────────────────────────
echo ""
echo "  Démarrage des conteneurs..."
docker compose up -d

# ── Attendre que nginx soit prêt ───────────────────────
echo -n "  En attente du démarrage"
for i in {1..15}; do
  sleep 1
  echo -n "."
  if curl -s -o /dev/null http://localhost:8480; then
    echo ""
    break
  fi
done

echo ""
echo -e "${GREEN}  ✓ Dashboard démarré !${NC}"
echo ""
echo "  ─────────────────────────────────────"
echo -e "  🌐 Accès : ${GREEN}http://${LOCAL_IP}:8480${NC}"
echo "  ─────────────────────────────────────"
echo ""
echo "  Prochaine étape :"
echo "  → Ouvrez le dashboard dans votre navigateur"
echo "  → Onglet ⚙️ Paramètres → renseignez l'IP de votre onduleur"
echo ""

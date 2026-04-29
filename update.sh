#!/bin/bash
# ─── Script de mise à jour — Indevolt Dashboard ───────────────────────────────
set -e

BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"
RED="\033[31m"; RESET="\033[0m"

echo -e "\n${BOLD}🔄 Indevolt Dashboard — Mise à jour${RESET}\n"

# ── 1. Pull ────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}⬇️  Récupération des dernières modifications...${RESET}"
git pull origin main

# ── 2. Redémarrage ────────────────────────────────────────────────────────────
echo -e "${YELLOW}🚀 Redémarrage des conteneurs...${RESET}"
docker compose up -d --force-recreate

# ── 3. Vérification ───────────────────────────────────────────────────────────
echo -e "${YELLOW}⏳ Attente du démarrage (10s)...${RESET}"
sleep 10

DASHBOARD_STATE=$(docker compose ps -q dashboard 2>/dev/null | xargs -I{} docker inspect --format='{{.State.Status}}' {} 2>/dev/null || echo "unknown")
API_STATE=$(docker compose ps -q settings-api 2>/dev/null | xargs -I{} docker inspect --format='{{.State.Status}}' {} 2>/dev/null || echo "unknown")

if [ "$DASHBOARD_STATE" = "running" ] && [ "$API_STATE" = "running" ]; then
  echo -e "\n${GREEN}${BOLD}✅ Mise à jour effectuée avec succès !${RESET}\n"
  echo -e "  dashboard    : ${GREEN}running${RESET}"
  echo -e "  settings-api : ${GREEN}running${RESET}"
else
  echo -e "\n${RED}⚠️  Problème détecté${RESET}"
  echo -e "  dashboard    : ${DASHBOARD_STATE}"
  echo -e "  settings-api : ${API_STATE}"
  echo -e "  Voir les logs : docker compose logs"
fi

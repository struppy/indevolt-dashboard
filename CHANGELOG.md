# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)  
Versioning basé sur [Semantic Versioning](https://semver.org/lang/fr/)

---

## [2.2.2] - 2026-08-03

### Corrigé
- Le compteur de cycles de charge estimés restait bloqué à 0 et n'évoluait jamais : `batCycleUpdate()` contenait la logique de détection de cycle mais n'était jamais appelée depuis `processData()`, la boucle exécutée à chaque poll
- Le suivi de charge en cours (`_batTrack`) vivait uniquement en mémoire JavaScript du navigateur et repartait à zéro à chaque rechargement de page — la progression d'un cycle en cours était donc perdue en permanence, empêchant tout comptage réel. Le calcul (cycles + courbe de dégradation SOC max) tourne désormais en continu dans le sidecar Python `settings-api` (`battery_poll_loop()`, poll direct de l'appareil toutes les 60s), indépendamment de tout onglet ouvert ; le frontend affiche les valeurs via synchronisation périodique (5 min)
- Le compteur de cycles initial ("Cycles au départ") saisi dans les paramètres n'apparaissait jamais dans la vue Cycles : les champs correspondants n'avaient aucun handler `oninput`/`onchange`, la valeur n'était donc jamais sauvegardée

---

## [2.2.1] - 2026-07-07

### Corrigé
- Faille CORS wildcard (`Access-Control-Allow-Origin: *`) combinée à l'absence d'authentification sur `settings_api.py` et les proxys nginx (`/api/`, `/indevolt-api/`, `/opendtu-api/`) : n'importe quel site web pouvait lire/écrire les réglages et piloter l'onduleur (charge/décharge forcée) depuis le navigateur de la victime
- XSS stockée dans le journal d'événements : un registre onduleur non reconnu pouvait injecter du JS persistant, exécuté à chaque ouverture de l'onglet Logs
- XSS dans le visualiseur JSON de l'onglet API tester : clés/valeurs de réponse d'appareil injectées sans échappement
- XSS via le numéro de série des packs batterie (SFA1800) non échappé
- `inv.limit` (OpenDTU) non coercé en nombre avant affichage

---

## [2.2.0] - 2026-05-08

### Ajouté
- Nouveau logo SVG vectoriel : picto composé d'un panneau PV 3×4 cellules (dégradé bleu diagonal), d'un éclair et d'une batterie Indevolt avec bandeau LED bleu
- Wordmark officiel Indevolt intégré (lettres blanches, E en `#3250C3`) en remplacement du texte HTML
- Favicon mis à jour avec le même picto sur fond `#0d1820`
- Clic sur le logo retourne à l'onglet Temps Réel

### Corrigé
- Alignement vertical du logo et du bloc texte dans le header (flex column + `display:block` sur le SVG)
- Hauteur du picto adaptée dynamiquement à la hauteur du bloc wordmark+sous-titre (`align-items:stretch`)

---

## [2.1.1] - 2026-05-08

### Ajouté
- Script `update.sh` : déploiement automatique GitHub → serveur (`git pull` + `docker compose restart`)
- Forçage immédiat mode RTC avec consigne de puissance configurable (registres 47015/47016/47017)
- Console API live dans l'onglet API avec logs de requêtes en temps réel
- Historique multi-sélection de métriques (choix des courbes affichées simultanément)
- Auto-connexion au démarrage si une IP est déjà configurée

### Corrigé
- Failles XSS : échappement HTML systématique sur toutes les données API affichées
- Registres SolidFlex 2000 / SFA1800 mis à jour selon OpenData API V1.4
- Registres RTC forçage immédiat (47015/16/17) + reset veille entre les modes
- Panneau connexion repliable (statusDot nettoyé)
- Corrections graphiques prévision solaire (polling + affichage)
- Suppression de l'onglet Comparatif multi-installations (refonte paramètres installation unique)

---

## [2.1.0] - 2026-03-06

### Ajouté
- Intégration **forecast.solar** pour la prévision de production PV (kWh/jour + courbe horaire)
- Paramètres PV configurables dans l'onglet Solaire : puissance crête, inclinaison, azimuth
- **OpenDTU IP dynamique** : l'IP saisie dans les paramètres est maintenant réellement utilisée par le proxy nginx (captures nommées `(?<dtuip>...)`)
- Boutons de contrôle mode direct restaurés dans l'onglet Batteries (au-dessus du planificateur)
- Labels des nœuds flux colorés selon leur couleur respective (solaire=jaune, réseau=bleu, etc.)

### Corrigé
- Comparatif multi-installations : installations affichées comme "hors ligne" (mauvais format de requête GET→POST)
- Comparatif : SOC incorrect (division /10 erronée supprimée)
- Comparatif : température batterie incorrecte (mauvais registre `6001` → `9012`, valeur directe en °C)
- nginx : erreur `unknown "1" variable` remplacée par captures nommées pour OpenDTU
- Modèles supportés dans la documentation : 4 modèles réels (SolidFlex ECO sans MPPT, + OpenDTU, PowerFlex MPPT, BK1600)

### Infrastructure
- `default.conf` nginx : bloc OpenDTU avec IP dynamique et protection SSRF `192.168.1.x`
- Publication GitHub : `README.md`, `.gitignore`, `setup.sh`, `screenshot_dashboard.png`, `CHANGELOG.md`

---

## [2.0.0] - 2026-03-05

### Ajouté — Planificateur horaire visuel (CTRL-01)
- Timeline 24h interactive avec créneaux glisser-déposer
- 4 modes colorés : Autoconsommation 🟢 · Charge forcée 🔵 · Décharge forcée 🟠 · Programmé 🟣
- Handles de redimensionnement des créneaux, snap automatique 30 minutes
- Ligne rouge "heure actuelle" rafraîchie chaque minute
- SOC cible par créneau avec arrêt automatique quand atteint
- Forçage immédiat charge/décharge avec SOC cible
- `checkScheduler()` multi-créneaux avec surbrillance du créneau actif
- Persistance des créneaux via `serverStore`

### Ajouté — Journal d'événements automatisé (JOURNAL-01/02)
- Détection automatique : coupures réseau, passages bypass, SOC bas/critique, température, changements de mode
- Timeline verticale avec icônes colorées et niveaux de sévérité (info/warning/critical)
- Filtres par type d'événement (8 catégories)
- Export PDF horodaté (`journal-indevolt-YYYY-MM-DD.html`)
- Badge rouge sur l'onglet Logs en cas d'alerte non lue
- Persistance serveur (`indevolt_events`)
- Événement de démarrage du dashboard loggé automatiquement

---

## [1.9.0] - 2026-03-04

### Ajouté — Graphiques historique améliorés
- Zoom temps réel : molette souris, pinch-to-zoom mobile, boutons 5min/10min/15min/30min/1h/2h
- Buffer 6h de données (1 point toutes les 30s)
- Sélecteur plage dates 30j avec presets 7j/14j/30j + dates personnalisées

### Ajouté — Responsive mobile complet
- Bottom navigation fixe sur mobile
- Swipe entre onglets
- Graphiques redimensionnés (140px), boutons scrollables horizontalement

### Ajouté — Onglet Comparatif multi-installations
- Cartes SOC/puissance/température par installation
- Graphique barres comparatif
- Fetch parallèle avec auto-refresh 30s
- Bouton "→ Basculer" pour changer l'installation active

---

## [1.8.0] - 2026-03-04

### Ajouté — Multi-installations
- Sélecteur d'installation dans le header
- Formulaire inline d'édition (nom, IP, port, modèle)
- Système de notifications push unifié 3 niveaux (info/warning/critical)
- Historique des alertes dans l'onglet Logs

### Corrigé
- Accolade manquante dans `sendPushNotif`
- Bloc formulaire dupliqué supprimé

---

## [1.7.0] - 2026-03-04

### Ajouté — Stockage serveur persistant
- Sidecar Python `settings_api.py` avec endpoints `/api/store/<key>`
- Whitelist de clés : `indevolt_7days`, `indevolt_30days`, `indevolt_solar24h`, `indevolt_degrad`, `indevolt_cycles`, `indevolt_hist30`
- Stockage JSON dans `/data/store/` (volume Docker partagé)
- `serverStore.syncFromServer()` au démarrage — restauration automatique
- Fallback localStorage si serveur indisponible

### Supprimé
- Onglet Fiches techniques batteries

---

## [1.6.0] - 2026-03-04

### Ajouté — Historique 30 jours
- Graphique barres 5 métriques : Production / Import / Export / Charge / Décharge
- Comparaison semaine N vs N-1 avec tableau évolution % et flèches colorées
- Export rapport mensuel HTML (imprimable en PDF)
- Accumulation automatique 1x/heure en localStorage

---

## [1.5.0] - 2026-03-03

### Ajouté — Fonctionnalités batterie avancées
- Compteur de cycles (détection début/fin de charge, fraction de cycle)
- Courbe de dégradation SOC max sur 60 jours (canvas)
- Projection durée de vie restante (cycles/jour sur 30j)
- Alerte température avec bannière et notification push (cooldown 10min)
- Notifications push navigateur (3 niveaux)
- Settings : seuil température, date/compteur de départ cycles

---

## [1.4.0] - 2026-03-03

### Ajouté — Onglet Solaire complet
- Supervision micro-onduleurs OpenDTU : HM-400, HM-800×2
- Fetch individuel par serial pour puissance AC réelle, YieldDay, température, RSSI
- Courbe production solaire 24h (localStorage, reset minuit)
- Prévision météo Open-Meteo 3 jours (icônes WMO, temp min/max, précipitations, rayonnement)
- Graphique rayonnement horaire avec zone passée/future et ligne "maintenant"

### Corrigé
- Onglet Solaire invisible (`hasMPPT` → `showSolar`)
- `switchTab` désynchronisé (index hardcodé → matching `data-tab`)
- Onglets vides par déséquilibre de balises HTML (40 ouvertures / 39 fermetures)
- Section MPPT visible en mode ECO+OpenDTU (masquage conditionnel)

---

## [1.3.0] - 2026-03-03

### Ajouté — Mode ECO + OpenDTU
- Option `solidflex_eco_opendtu` avec badge dynamique
- `fetchOpenDTU()` : polling toutes les 30s
- `applyModel()` détecte `isEcoOpenDTU` et adapte les labels
- Section OpenDTU dans Paramètres avec IP configurable et test connexion
- Note nginx dans l'onglet API

### Corrigé
- Nginx 404 : fusion `default-ORI.conf` + `default.conf` avec `server_name localhost`
- Erreurs TDZ (`totalSolar`, `cumProd`) — ordre des déclarations corrigé
- Proxy nginx : captures nommées `(?<devip>...)` pour compatibilité

---

## [1.2.0] - 2026-02-28

### Ajouté
- Diagramme flux 3 colonnes avec positions calculées dynamiquement (`getBoundingClientRect`)
- Hub batterie agrandi (120px → 170px)
- Couleurs flux réseau : bleu `#60b0f0`
- Consommation totale réelle (Sortie AC + Sortie BKP) mise en avant
- Graphique historique 4 courbes avec couleurs distinctes
- Métrique Bypass dédiée
- Nginx sécurisé SSRF (restriction `192.168.1.x`)
- Autonomie basée sur `totalConso`
- Économies avec `yieldDay` OpenDTU

### Corrigé
- Structure HTML : déséquilibres de balises résolus, isolation onglets restaurée

---

## [1.1.0] - 2026-02-27

### Ajouté — 16 améliorations majeures
- Production solaire estimée et journalière calculée
- Responsive mobile (3 breakpoints : 1024/768/480px)
- Tension batterie normalisée
- Feedback connexion et gestion erreur réseau
- Cache `getElementById`
- Alertes hardware
- Badge mode nuit
- Tooltips interactifs sur les graphiques
- Historique 30min persisté en localStorage
- Validation IP
- Notifications push
- Vue comparative packs batterie
- Calcul économies amélioré

### Restructuré
- Onglets : contrôle mode → tab-packs, export CSV → tab-history
- Fiche API Locale → tab-api
- Fiches batteries SolidFlex 2000 et SFA1800 dans tab-specs

---

## [1.0.0] - 2026-02-22

### Initial
- Dashboard single-file HTML (~93KB) avec 8 onglets
- Connexion API locale Indevolt via proxy nginx
- Flux d'énergie animé avec 4 nœuds (Solaire, Sortie AC, Réseau, Sortie BKP)
- Hub batterie central avec SOC en anneau, tendance 5min
- 16 metric-cards (SOC, puissance, température, réseau, etc.)
- Modes de fonctionnement (Autoconsommation, Charge, Décharge, Programmé)
- Historique 7 jours avec graphiques Chart.js
- Export CSV
- Mode nuit automatique
- Settings persistants via sidecar Python Docker
- Icônes C3 Techno SVG
- Docker Compose : nginx + settings-api Python

#!/usr/bin/env python3
"""
Indevolt Settings & Store API

Endpoints :
  GET  /api/settings          -> lire les parametres
  POST /api/settings          -> sauvegarder les parametres
  GET  /api/store/<key>       -> lire une valeur JSON par cle
  POST /api/store/<key>       -> sauvegarder une valeur JSON par cle
  DELETE /api/store/<key>     -> supprimer une cle
  GET  /api/store             -> lister toutes les cles

Stockage dans /data/ :
  /data/settings.json
  /data/store/indevolt_30days.json
  /data/store/indevolt_cycles.json
  etc.
"""

import json, os, re, threading, time, datetime, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

DATA_DIR      = '/data'
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
STORE_DIR     = os.path.join(DATA_DIR, 'store')

ALLOWED_KEYS = {
    'indevolt_7days',
    'indevolt_30days',
    'indevolt_solar24h',
    'indevolt_degrad',
    'indevolt_cycles',
    'indevolt_hist30',
}

DEFAULT_SETTINGS = {
    "socAlert": 20, "socSound": True, "capacity": 3584, "feedLimit": 500,
    "priceImport": 0.2516, "priceExport": 0.13,
    "nightMode": False, "nightStart": "22:00", "nightEnd": "06:00",
    "scheduleEnabled": False, "scheduleStart": "02:00",
    "scheduleEnd": "06:00", "scheduleMode": 1,
    "opendtuEnabled": False, "opendtuIp": "192.168.1.121",
    "weatherLat": "48.5734", "weatherLon": "7.7521",
    "tempAlert": 45, "tempAlertEnabled": True,
    "cycleStartCount": 0, "cycleStartDate": "",
}

# ==================== BATTERIE — SUIVI CYCLES / DÉGRADATION (côté serveur) ====================
# Voir batCycleUpdate() (ex-html/index.html) : logique reprise à l'identique, mais tourne en
# continu ici, indépendamment de tout onglet de navigateur ouvert.

TRACK_STATE_FILE   = os.path.join(DATA_DIR, 'battery_tracker_state.json')  # interne, jamais exposé via /api/store
DEVICE_RPC_PORT    = 8080   # port fixe utilisé par le proxy nginx (nginx/default.conf), seul chemin réellement actif
POLL_INTERVAL_SEC  = 60
POLL_TIMEOUT_SEC   = 5
CHARGE_THRESHOLD_W = 20
SOC_FULL_THRESHOLD = 95
MIN_CYCLE_FRACTION = 0.05
DEFAULT_CAPACITY_WH = 3584
MAX_ACCUM_DT_SEC   = POLL_INTERVAL_SEC * 3   # borne la fenêtre d'intégration Wh après un redémarrage/coupure

_store_lock = threading.Lock()


def ensure_dirs():
    os.makedirs(STORE_DIR, exist_ok=True)


def key_path(key):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', key)
    return os.path.join(STORE_DIR, safe + '.json')


def _atomic_write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


_TIME_RE = re.compile(r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
_SLOT_MODES = {'auto', 'charge', 'discharge', 'schedule'}


def _validate_settings(data):
    cleaned = dict(data)

    slots = cleaned.get('scheduleSlots')
    if slots is not None:
        if not isinstance(slots, list):
            raise ValueError("scheduleSlots doit être une liste")
        validated_slots = []
        for slot in slots:
            if not isinstance(slot, dict):
                raise ValueError("Chaque créneau doit être un objet")
            start = str(slot.get('start', ''))
            end   = str(slot.get('end', ''))
            mode  = str(slot.get('mode', 'auto'))
            if not _TIME_RE.match(start):
                raise ValueError(f"Heure de début invalide : {start!r}")
            if not _TIME_RE.match(end):
                raise ValueError(f"Heure de fin invalide : {end!r}")
            if mode not in _SLOT_MODES:
                raise ValueError(f"Mode de créneau invalide : {mode!r}")
            vs = {'start': start, 'end': end, 'mode': mode}
            if 'socTarget' in slot and slot['socTarget'] is not None:
                soc = int(slot['socTarget'])
                if not (5 <= soc <= 100):
                    raise ValueError(f"socTarget hors limites : {soc}")
                vs['socTarget'] = soc
            validated_slots.append(vs)
        cleaned['scheduleSlots'] = validated_slots

    return cleaned


def _load_settings_for_poller():
    merged = {**DEFAULT_SETTINGS, **_read_json(SETTINGS_FILE, {})}
    return merged.get('ip'), merged.get('capacity') or DEFAULT_CAPACITY_WH


def _fetch_battery_regs(ip):
    config = json.dumps({"t": [6000, 6002, 6109]}, separators=(',', ':'))
    url = f'http://{ip}:{DEVICE_RPC_PORT}/rpc/Indevolt.GetData?config={urllib.parse.quote(config)}'
    req = urllib.request.Request(url, method='POST', data=b'')
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT_SEC) as resp:
        d = json.loads(resp.read())
    soc = d.get('6002')
    bp_raw = d.get('6000')
    if bp_raw is None:
        bp_raw = d.get('6109')
    bat_power = -bp_raw if bp_raw is not None else None  # convention : positif = charge
    return soc, bat_power


def _load_tracker_state():
    return _read_json(TRACK_STATE_FILE, {"wasCharging": False, "cycleAccum": 0.0, "lastCycleSOC": None})


def _today_utc():
    return datetime.datetime.utcnow().date().isoformat()  # même convention que JS toISOString().slice(0,10)


def _degrad_push(soc_max):
    with _store_lock:
        fp = key_path('indevolt_degrad')
        h = _read_json(fp, [])
        today = _today_utc()
        if h and h[-1].get('date') == today:
            h[-1]['socMax'] = max(h[-1]['socMax'], round(soc_max))
        else:
            h.append({"date": today, "socMax": round(soc_max)})
        while len(h) > 60:
            h.pop(0)
        _atomic_write_json(fp, h)


def _cycle_add(fraction):
    with _store_lock:
        fp = key_path('indevolt_cycles')
        d = _read_json(fp, {"total": 0, "log": []})
        d['total'] = (d.get('total') or 0) + fraction
        today = _today_utc()
        log = d.setdefault('log', [])
        if log and log[-1].get('date') == today:
            log[-1]['count'] = (log[-1].get('count') or 0) + fraction
        else:
            log.append({"date": today, "count": fraction})
        while len(log) > 365:
            log.pop(0)
        _atomic_write_json(fp, d)


def _battery_poll_once(state, dt):
    ip, capacity = _load_settings_for_poller()
    if not ip:
        return state, False  # pas encore configuré — no-op silencieux

    soc, bat_power = _fetch_battery_regs(ip)
    if soc is None or bat_power is None:
        return state, False

    is_charging = bat_power > CHARGE_THRESHOLD_W
    if is_charging and not state['wasCharging']:
        state['lastCycleSOC'] = soc
    if is_charging:
        clamped_dt = min(dt, MAX_ACCUM_DT_SEC)
        state['cycleAccum'] = state.get('cycleAccum', 0.0) + bat_power * (clamped_dt / 3600)
    if state['wasCharging'] and (not is_charging or soc >= SOC_FULL_THRESHOLD):
        soc_max = max(soc, state.get('lastCycleSOC') or soc)
        _degrad_push(soc_max)
        cycle_fraction = state.get('cycleAccum', 0.0) / capacity
        if cycle_fraction > MIN_CYCLE_FRACTION:
            _cycle_add(cycle_fraction)
        state['cycleAccum'] = 0.0
    state['wasCharging'] = is_charging
    return state, True


def battery_poll_loop():
    state = _load_tracker_state()
    last_ts = None
    print(f'[settings-api] Battery poller demarre (intervalle {POLL_INTERVAL_SEC}s)')
    while True:
        try:
            now = time.monotonic()
            dt = (now - last_ts) if last_ts is not None else POLL_INTERVAL_SEC
            state, polled = _battery_poll_once(state, dt)
            if polled:
                last_ts = now
                _atomic_write_json(TRACK_STATE_FILE, state)
        except Exception as e:
            print(f'[settings-api] Battery poller erreur: {e}')
        time.sleep(POLL_INTERVAL_SEC)


class Handler(BaseHTTPRequestHandler):

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get('Content-Length', 0)))

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        ensure_dirs()

        if self.path == '/api/settings':
            try:
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, encoding='utf-8') as f:
                        data = json.load(f)
                    self._json(200, {**DEFAULT_SETTINGS, **data})
                else:
                    self._json(200, DEFAULT_SETTINGS)
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        if self.path == '/api/store':
            try:
                keys = [f[:-5] for f in os.listdir(STORE_DIR) if f.endswith('.json')]
                self._json(200, {"keys": sorted(keys)})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        m = re.match(r'^/api/store/([a-zA-Z0-9_]+)$', self.path)
        if m:
            key = m.group(1)
            if key not in ALLOWED_KEYS:
                self._json(403, {"error": "Cle non autorisee"})
                return
            fp = key_path(key)
            try:
                with _store_lock:
                    data = _read_json(fp, None)
                self._json(200, {"ok": True, "data": data})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        self._json(404, {"error": "Route introuvable"})

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        ensure_dirs()

        if self.path == '/api/settings':
            try:
                data = json.loads(self._body())
                validated = _validate_settings(data)
                merged = {**DEFAULT_SETTINGS, **validated}
                _atomic_write_json(SETTINGS_FILE, merged)
                self._json(200, {"ok": True})
            except ValueError as e:
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        m = re.match(r'^/api/store/([a-zA-Z0-9_]+)$', self.path)
        if m:
            key = m.group(1)
            if key not in ALLOWED_KEYS:
                self._json(403, {"error": "Cle non autorisee"})
                return
            try:
                data = json.loads(self._body())
                with _store_lock:
                    _atomic_write_json(key_path(key), data)
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        self._json(404, {"error": "Route introuvable"})

    # --------------------------------------------------------------- DELETE
    def do_DELETE(self):
        ensure_dirs()
        m = re.match(r'^/api/store/([a-zA-Z0-9_]+)$', self.path)
        if m:
            key = m.group(1)
            if key not in ALLOWED_KEYS:
                self._json(403, {"error": "Cle non autorisee"})
                return
            fp = key_path(key)
            try:
                with _store_lock:
                    if os.path.exists(fp):
                        os.remove(fp)
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return
        self._json(404, {"error": "Route introuvable"})

    def log_message(self, fmt, *args):
        print(f"[settings-api] {self.address_string()} {fmt % args}")


if __name__ == '__main__':
    ensure_dirs()
    port = int(os.environ.get('PORT', 8081))
    print(f'[settings-api] Port {port}')
    print(f'[settings-api] Data  : {DATA_DIR}')
    print(f'[settings-api] Store : {STORE_DIR}')
    print(f'[settings-api] Cles  : {", ".join(sorted(ALLOWED_KEYS))}')
    threading.Thread(target=battery_poll_loop, daemon=True).start()
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

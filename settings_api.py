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

import json, os, re
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


def ensure_dirs():
    os.makedirs(STORE_DIR, exist_ok=True)


def key_path(key):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', key)
    return os.path.join(STORE_DIR, safe + '.json')


class Handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get('Content-Length', 0)))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
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
                if os.path.exists(fp):
                    with open(fp, encoding='utf-8') as f:
                        data = json.load(f)
                    self._json(200, {"ok": True, "data": data})
                else:
                    self._json(200, {"ok": True, "data": None})
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
                merged = {**DEFAULT_SETTINGS, **data}
                with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(merged, f, indent=2, ensure_ascii=False)
                self._json(200, {"ok": True})
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
                with open(key_path(key), 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
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
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

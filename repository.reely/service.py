"""Serve bundled repository files on this device's loopback interface only."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import xbmc

ROOT = Path(__file__).resolve().parent / 'packages'
FILES = {'/' + p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob('*') if p.is_file()}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = FILES.get(urlsplit(self.path).path)
        if path is None:
            self.send_error(404)
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Content-Type', 'application/zip' if path.suffix == '.zip' else 'text/plain')
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass

monitor = xbmc.Monitor()
try:
    server = HTTPServer(('127.0.0.1', 18764), Handler)
except OSError:
    xbmc.log('Reely repository: cannot bind loopback port 18764.', xbmc.LOGERROR)
else:
    server.timeout = 0.5
    xbmc.executebuiltin('UpdateAddonRepos')
    try:
        while not monitor.abortRequested():
            server.handle_request()
    finally:
        server.server_close()

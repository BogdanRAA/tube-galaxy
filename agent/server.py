#!/usr/bin/env python3
"""Local host for Tube Galaxy + its search agent.

Serves public/ (the normal dashboard) and adds a tiny API the Findings tab uses:
  GET    /api/status          agent, LLM and index state
  POST   /api/find            {"query": "..."}  -> runs the agent, saves a finding
  DELETE /api/findings/<id>   removes a finding tab

Binds to 127.0.0.1 only: your index, keys and findings never leave the machine.
Run:  npm run agent   then open http://localhost:8787/findings.html
"""

import json
import os
import sys
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

PUBLIC = Path(__file__).resolve().parent.parent / 'public'
PORT = int(os.environ.get('PORT', '8787'))


class Handler(SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if self.path.startswith('/data/'):
            self.send_header('Cache-Control', 'no-store')  # findings change under you
        super().end_headers()

    def do_GET(self):
        if self.path == '/api/status':
            return self._json(200, core.status())
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        if self.path != '/api/find':
            return self._json(404, {'error': 'not found'})
        try:
            n = int(self.headers.get('Content-Length', 0))
            query = json.loads(self.rfile.read(n) or b'{}').get('query', '')
            print(f'[agent] find: {query!r}')
            finding = core.run(query)
            print(f'[agent] -> {finding["verdict"]}: {finding["summary"]} ({finding["elapsed_s"]}s)')
            return self._json(200, finding)
        except (ValueError, FileNotFoundError) as e:
            return self._json(400, {'error': str(e)})
        except Exception as e:  # surface the reason in the UI instead of a silent 500
            traceback.print_exc()
            return self._json(500, {'error': str(e)})

    def do_DELETE(self):
        if self.path.startswith('/api/findings/'):
            ok = core.delete_finding(self.path.rsplit('/', 1)[-1])
            return self._json(200 if ok else 404, {'deleted': ok})
        return self._json(404, {'error': 'not found'})

    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else ''):
            super().log_message(fmt, *args)


def main():
    st = core.status()
    print('=== Tube Galaxy agent ===')
    if st['index']:
        print(f"Index: {st['index']['videos']:,} videos / {st['index']['channels']:,} channels (built {st['index']['built_at']})")
    else:
        print(f"Index: missing. {st['index_error']}")
    print(f"LLM:   {st['provider'] + ' / ' + st['model'] if st['llm'] else 'off (set OPENROUTER_API_KEY for decomposition + verification)'}")
    print(f'Open:  http://localhost:{PORT}/findings.html\n')
    ThreadingHTTPServer(('127.0.0.1', PORT), partial(Handler, directory=str(PUBLIC))).serve_forever()


if __name__ == '__main__':
    main()

"""Serve the AUT (index.html) locally for harness runs."""
import argparse, http.server, os, socketserver, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    Handler = http.server.SimpleHTTPRequestHandler
    Handler.log_message = lambda *a: None  # silence request logs
    with socketserver.TCPServer((args.bind, args.port), Handler) as httpd:
        print(f"AUT serving on http://{args.bind}:{args.port}", flush=True)
        httpd.serve_forever()

if __name__ == "__main__":
    main()

# Acceptance: python preflight/aut/serve.py --port 9000  -> HTTP 200 on /
# Acceptance: expected_structure.yaml parses and validates against the schema
# Acceptance: fixtures/golden_spec/login.md parses as a two-case consolidated spec

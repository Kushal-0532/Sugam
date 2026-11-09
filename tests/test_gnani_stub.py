"""STUB: a local fake HTTP server stands in for Gnani to test the 429 retry and 402 paths. No real API calls."""
import http.server, threading
import pytest
from src import gnani


def _serve(codes):
    hits = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            hits.append(self.headers.get("X-API-Key-ID"))
            code = codes[min(len(hits), len(codes)) - 1]
            body = b'{"transcript": "ok"}' if code == 200 else b'{"detail": {"error_code": "RATE_LIMITED"}}'
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


@pytest.fixture
def stub(monkeypatch, tmp_path):
    monkeypatch.setenv("GNANI_API_KEY", "stub-key")
    monkeypatch.setattr(gnani, "_BACKOFF", (0, 0, 0))
    monkeypatch.setattr(gnani, "_log", lambda **kw: None)  # keep the real usage log clean
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")

    def go(codes):
        srv, hits = _serve(codes)
        monkeypatch.setattr(gnani, "STT_URL", f"http://127.0.0.1:{srv.server_port}/stt")
        return wav, hits
    return go


def test_429_then_ok(stub):
    wav, hits = stub([429, 429, 200])
    assert gnani.stt(wav)["transcript"] == "ok"
    assert hits == ["stub-key"] * 3


def test_429_gives_up_after_4(stub):
    wav, hits = stub([429])
    with pytest.raises(RuntimeError, match="429"):
        gnani.stt(wav)
    assert len(hits) == 4


def test_402_out_of_credits(stub):
    wav, hits = stub([402])
    with pytest.raises(gnani.OutOfCredits):
        gnani.stt(wav)
    assert len(hits) == 1

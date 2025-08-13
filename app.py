import os, json, uuid, datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
os.makedirs("uploads", exist_ok=True)

# Optional: simple shared-secret via query string (?token=XYZ). Set in Render env.
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")

def _maybe_json(s):
    if not s or not isinstance(s, str):
        return s
    t = s.strip()
    if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):
        try:
            return json.loads(t)
        except Exception:
            return s
    return s

@app.get("/health")
def health():
    return "OK", 200

@app.post("/geopal/data-exchange")
def data_exchange():
    # Optional token check
    if WEBHOOK_TOKEN and request.args.get("token") != WEBHOOK_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    from datetime import datetime, UTC
ts = datetime.now(UTC).isoformat()

    # 1) Headers
    headers = {k: v for k, v in request.headers.items()}

    # 2) Parse form FIRST (don’t consume stream)
    fields = {k: request.form.get(k) for k in request.form} if request.form else {}
    # Optionally JSON-decode common fields
    fields = {k: _maybe_json(v) for k, v in fields.items()}

    # 3) Raw body (safe because cache=True by default)
    raw_body = request.get_data(cache=True, as_text=False)
    try:
        preview = raw_body[:2000].decode("utf-8", errors="replace") if raw_body else ""
    except Exception:
        preview = ""

    # 4) Files (e.g., file2upload)
    files_meta = []
    for name, f in request.files.items():
        filename = secure_filename(f.filename or name)
        dest = os.path.join("uploads", f"{uuid.uuid4().hex}-{filename}")
        f.save(dest)
        files_meta.append({
            "fieldname": name,
            "filename": filename,
            "mimetype": f.mimetype,
            "size": os.path.getsize(dest),
            "path": dest
        })

    # 5) Persist snapshot and raw body
    snap_id = ts.replace(":", "-").replace(".", "-")
    meta_path = os.path.join("uploads", f"{snap_id}.json")
    raw_path  = os.path.join("uploads", f"{snap_id}.raw")
    snapshot = {"ts": ts, "headers": headers, "fields": fields, "files": files_meta, "preview": preview}
    with open(meta_path, "w") as fh:
        json.dump(snapshot, fh, indent=2)
    if raw_body:
        with open(raw_path, "wb") as fh:
            fh.write(raw_body)

    # Log to Render
    print("=== GeoPal Data Exchange Event ===")
    print(json.dumps(snapshot, indent=2))
    print("Saved meta:", meta_path, "raw:", raw_path if raw_body else "(none)")

    # Fast ACK
    return jsonify({"status": "ok"}), 200

# Optional: catch-all for POST to "/"
@app.post("/")
def root_post():
    # forward to main handler (with same token rule)
    return data_exchange()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

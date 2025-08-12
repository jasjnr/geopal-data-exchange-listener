import os, json, uuid, datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
os.makedirs("uploads", exist_ok=True)

# Optional: simple shared-secret via query string (?token=XYZ)
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")  # set later in Render

@app.get("/health")
def health():
    return "OK", 200

@app.post("/geopal/data-exchange")
def data_exchange():
    # Optional token check
    if WEBHOOK_TOKEN:
        if request.args.get("token") != WEBHOOK_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

    ts = datetime.datetime.utcnow().isoformat() + "Z"

    # Capture all headers (case-insensitive mapping)
    headers = {k: v for k, v in request.headers.items()}

    # Raw body (helps later if we need to verify signatures)
    try:
        raw_body = request.get_data(cache=False, as_text=False)
    except Exception:
        raw_body = None

    # Form fields (e.g., job, job_field, job_workflow, job_workflow_file)
    fields = {}
    if request.form:
        fields = {k: request.form.get(k) for k in request.form}

    # Files (e.g., file2upload)
    files_meta = []
    for name, f in request.files.items():
        filename = secure_filename(f.filename or name)
        dest = os.path.join("uploads", f"{uuid.uuid4().hex}-{filename}")
        f.save(dest)
        files_meta.append({
            "fieldname": name, "filename": filename,
            "mimetype": f.mimetype, "size": os.path.getsize(dest),
            "path": dest
        })

    # Persist a snapshot (for local inspection) and log to console (Render Logs)
    snap_id = ts.replace(":", "-").replace(".", "-")
    meta_path = os.path.join("uploads", f"{snap_id}.json")
    raw_path  = os.path.join("uploads", f"{snap_id}.raw")
    snapshot = {"ts": ts, "headers": headers, "fields": fields, "files": files_meta}
    with open(meta_path, "w") as fh:
        json.dump(snapshot, fh, indent=2)
    if raw_body:
        with open(raw_path, "wb") as fh:
            fh.write(raw_body)

    print("=== GeoPal Data Exchange Event ===")
    print(json.dumps(snapshot, indent=2))
    print("Saved meta:", meta_path, "raw:", raw_path if raw_body else "(none)")

    # Fast ACK so GeoPal doesn't retry
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

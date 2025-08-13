@app.post("/geopal/data-exchange")
def data_exchange():
    # Optional token check
    if WEBHOOK_TOKEN:
        if request.args.get("token") != WEBHOOK_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

    ts = datetime.datetime.utcnow().isoformat() + "Z"

    # 1) Capture headers
    headers = {k: v for k, v in request.headers.items()}

    # 2) Parse form FIRST (so the stream isn't consumed)
    fields = {k: request.form.get(k) for k in request.form} if request.form else {}

    # 3) Now safely capture raw body with cache=True (default)
    raw_body = request.get_data(cache=True, as_text=False)

    # Optional: short preview to logs for debugging (won't exceed logs)
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
            "fieldname": name, "filename": filename,
            "mimetype": f.mimetype, "size": os.path.getsize(dest),
            "path": dest
        })

    # 5) Persist snapshot
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

    return jsonify({"status": "ok"}), 200

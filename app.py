"""
Resume Matcher — Flask backend (no database; everything lives in memory)

  GET  /                              frontend
  POST /api/parse                     upload one resume -> fields + ATS score + recommendations
  POST /api/match                     resume vs job description -> score, gaps, what-if, learning plan
  POST /api/batch-upload              upload many resumes (recruiter mode)
  POST /api/recruiter-rank            rank uploaded candidates against a job description
  GET  /api/download-report/<id>      PDF report for one resume
"""
import os
import uuid
from collections import OrderedDict

from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename

from parser_utils import extract_text, extract_fields, calculate_quality_score
from matcher import analyze_match, interview_focus
from report import build_report
from skills_data import SKILLS_DB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_EXT = {".pdf", ".docx", ".txt"}
MAX_BATCH = 25
STORE_LIMIT = 300  # oldest resumes are dropped so memory can't grow forever

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # batch uploads
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

RESUME_STORE = OrderedDict()


def process_upload(file) -> dict:
    """Save -> extract -> parse -> score -> store. Raises ValueError with a friendly message."""
    original = file.filename or ""
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"“{original}” is not supported. Use PDF, DOCX or TXT.")
    if file.content_length and file.content_length > 5 * 1024 * 1024:
        raise ValueError(f"“{original}” is larger than 5 MB.")

    safe = secure_filename(original) or f"resume{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4().hex}_{safe}")
    file.save(path)
    try:
        raw_text = extract_text(path)
    except ValueError:
        raise
    except Exception:
        raise ValueError(f"“{original}” could not be read. The file may be corrupted or password protected.")
    finally:
        if os.path.exists(path):
            os.remove(path)

    if len(raw_text.split()) < 20:
        raise ValueError(f"No readable text found in “{original}”. Scanned or image-only files aren't supported.")

    fields = extract_fields(raw_text, SKILLS_DB)
    entry = {
        "resume_id": uuid.uuid4().hex,
        "filename": original,
        "raw_text": raw_text,
        "fields": fields,
        "quality": calculate_quality_score(raw_text, fields),
        "last_match": None,
    }
    RESUME_STORE[entry["resume_id"]] = entry
    while len(RESUME_STORE) > STORE_LIMIT:
        RESUME_STORE.popitem(last=False)
    return entry


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Upload is too large. Keep each resume under 5 MB."}), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/parse", methods=["POST"])
def parse_resume():
    file = request.files.get("resume")
    if not file or file.filename == "":
        return jsonify({"error": "Choose a resume file to upload."}), 400
    try:
        entry = process_upload(file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "resume_id": entry["resume_id"],
        "filename": entry["filename"],
        "fields": entry["fields"],
        "quality": entry["quality"],
    })


@app.route("/api/match", methods=["POST"])
def match_job():
    data = request.get_json(silent=True) or {}
    entry = RESUME_STORE.get(data.get("resume_id"))
    jd = (data.get("job_description") or "").strip()
    if not entry:
        return jsonify({"error": "Upload a resume first (it may have expired — upload it again)."}), 400
    if len(jd.split()) < 8:
        return jsonify({"error": "Paste a fuller job description (at least a couple of sentences)."}), 400

    result = analyze_match(entry, jd)
    entry["last_match"] = result
    return jsonify(result)


@app.route("/api/batch-upload", methods=["POST"])
def batch_upload():
    files = request.files.getlist("resumes")
    if not files:
        return jsonify({"error": "Select at least one resume."}), 400
    if len(files) > MAX_BATCH:
        return jsonify({"error": f"Upload at most {MAX_BATCH} resumes at a time."}), 400

    candidates, errors = [], []
    for f in files:
        try:
            e = process_upload(f)
            candidates.append({
                "resume_id": e["resume_id"], "filename": e["filename"],
                "name": e["fields"]["name"], "ats_score": e["quality"]["score"],
                "skill_count": len(e["fields"]["skills"]),
            })
        except ValueError as exc:
            errors.append(str(exc))

    if not candidates:
        return jsonify({"error": errors[0] if errors else "No resumes could be parsed.", "errors": errors}), 400
    return jsonify({"candidates": candidates, "errors": errors})


@app.route("/api/recruiter-rank", methods=["POST"])
def recruiter_rank():
    data = request.get_json(silent=True) or {}
    jd = (data.get("job_description") or "").strip()
    ids = [i for i in data.get("resume_ids", []) if i in RESUME_STORE]
    if not ids:
        return jsonify({"error": "Upload candidate resumes first."}), 400
    if len(jd.split()) < 8:
        return jsonify({"error": "Paste a fuller job description (at least a couple of sentences)."}), 400

    rows = []
    for rid in ids:
        e = RESUME_STORE[rid]
        m = analyze_match(e, jd)
        e["last_match"] = m
        ats = e["quality"]["score"]
        overall = round(0.75 * m["score"] + 0.25 * ats, 1)
        rows.append({
            "resume_id": rid, "name": e["fields"]["name"], "filename": e["filename"],
            "score": m["score"], "ats_score": ats, "overall": overall,
            "verdict": "Strong fit" if overall >= 70 else "Possible fit" if overall >= 45 else "Weak fit",
            "years": e["fields"]["years_experience"], "education": e["fields"]["education_level"],
            "matched_skills": [x["skill"] for x in m["matched_skills"]],
            "missing_skills": [x["skill"] for x in m["missing_skills"]],
            "top_recommendation": (e["quality"]["feedback"] or [{"text": ""}])[0]["text"],
            "interview_focus": interview_focus(m, e["quality"]["unproven_skills"]),
        })
    rows.sort(key=lambda r: -r["overall"])

    # skill matrix + scarcity insight use the JD skills (same for every candidate)
    first = analyze_match(RESUME_STORE[ids[0]], jd)
    jd_skills = [{"skill": x["skill"], "level": x["level"]} for x in first["matched_skills"]] + \
                [{"skill": x["skill"], "level": x["level"]} for x in first["missing_skills"]]
    order = {"Critical": 0, "Important": 1, "Nice to have": 2}
    jd_skills.sort(key=lambda s: order[s["level"]])
    jd_skills = jd_skills[:12]
    for r in rows:
        have = set(r["matched_skills"])
        r["has"] = [s["skill"] in have for s in jd_skills]
    pool = [{"skill": s["skill"], "level": s["level"],
             "pct": round(100 * sum(r["has"][i] for r in rows) / len(rows))}
            for i, s in enumerate(jd_skills)]

    return jsonify({"total_candidates": len(rows), "rankings": rows, "jd_skills": jd_skills,
                    "pool_coverage": sorted(pool, key=lambda p: p["pct"])})


@app.route("/api/download-report/<resume_id>")
def download_report(resume_id):
    entry = RESUME_STORE.get(resume_id)
    if not entry:
        return jsonify({"error": "Report expired. Upload the resume again."}), 404
    base = os.path.splitext(secure_filename(entry["filename"]) or "resume")[0]
    return send_file(build_report(entry), mimetype="application/pdf", as_attachment=True,
                     download_name=f"{base}-report.pdf")


if __name__ == "__main__":
    app.run(debug=True)

/* Resume Matcher frontend. Plain JS, no build step. */
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let currentResumeId = null;
let pool = [];            // candidates uploaded in recruiter mode
let lastRank = null;      // last ranking response, so the blind toggle can re-render

async function api(url, options) {
  let res;
  try { res = await fetch(url, options); }
  catch { throw new Error("Can't reach the server. Is `python app.py` still running?"); }
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  if (!isJson) throw new Error(`Unexpected server response (${res.status}).`);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || "Something went wrong.");
  return data;
}

function showStatus(el, msg, type) { el.textContent = msg; el.className = `status ${type}`; }
const scoreColor = (v) => (v >= 75 ? "var(--mint)" : v >= 50 ? "var(--amber)" : "var(--coral)");

/* ---------- visual helpers ---------- */
function ringHTML(value, label, size = 132) {
  const r = size / 2 - 10, c = 2 * Math.PI * r, color = scoreColor(value);
  return `<div class="ring" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle class="ring-bg" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="11"/>
      <circle class="ring-fg" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="11"
        stroke="${color}" stroke-dasharray="${c}" stroke-dashoffset="${c}" data-target="${c * (1 - Math.min(value, 100) / 100)}"/>
    </svg>
    <div class="ring-num"><b>${Math.round(value)}</b><small>${esc(label)}</small></div></div>`;
}

function barRow(label, pct, color, text) {
  return `<div class="bar-row"><span>${esc(label)}</span>
    <div class="bar"><i style="background:${color}" data-w="${Math.max(0, Math.min(pct, 100))}"></i></div>
    <span>${esc(text)}</span></div>`;
}

function animate(root) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.querySelectorAll(".ring-fg").forEach((el) => (el.style.strokeDashoffset = el.dataset.target));
    root.querySelectorAll(".bar i").forEach((el) => (el.style.width = el.dataset.w + "%"));
  }));
}

const tags = (items, cls = "") => items.map((s) => `<span class="tag ${cls}">${esc(s)}</span>`).join("");

/* ---------- tabs ---------- */
document.querySelectorAll(".tab-btn").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.tab).classList.add("active");
  })
);

function wireDrop(zone, onFiles) {
  ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.remove("over"); }));
  zone.addEventListener("drop", (ev) => { if (ev.dataTransfer.files.length) onFiles(ev.dataTransfer.files); });
}

/* =========================================================
   TAB 1: single resume
   ========================================================= */
const resumeInput = $("resume-input");
const matchBtn = $("match-btn");

resumeInput.addEventListener("change", () => resumeInput.files.length && handleUpload(resumeInput.files[0]));
wireDrop($("dropzone"), (files) => handleUpload(files[0]));

async function handleUpload(file) {
  showStatus($("upload-status"), "Reading your resume and scoring it…", "info");
  const fd = new FormData();
  fd.append("resume", file);
  try {
    const data = await api("/api/parse", { method: "POST", body: fd });
    currentResumeId = data.resume_id;
    showStatus($("upload-status"), `Loaded ${data.filename}`, "success");
    renderParsed(data);
    matchBtn.disabled = false;
    $("match-hint").textContent = "Paste a job description and check your fit.";
    $("download-pdf-btn").href = `/api/download-report/${currentResumeId}`;
    $("match-results").hidden = true; // old match belongs to the previous resume
  } catch (err) {
    showStatus($("upload-status"), err.message, "error");
  }
}

function renderParsed(data) {
  const q = data.quality, f = data.fields;
  $("parsed-results").hidden = false;

  $("ats-ring").innerHTML = ringHTML(q.score, "out of 100");
  $("ats-grade").textContent = q.grade;
  $("ats-summary").textContent =
    q.score >= 85 ? "Excellent. This resume should parse cleanly and read well."
    : q.score >= 70 ? "Good, with a few fixes that will make a visible difference."
    : q.score >= 55 ? "Average. Work through the high priority fixes below."
    : "Needs work. Start with the red items below.";

  $("ats-breakdown").innerHTML = q.breakdown
    .map((b) => barRow(b.label, (b.score / b.max) * 100, scoreColor((b.score / b.max) * 100), `${b.score}/${b.max}`)).join("");

  $("quality-feedback").innerHTML = q.feedback.length
    ? q.feedback.map((r) => `<li><span class="prio ${r.priority}">${r.priority}</span><span>${esc(r.text)}</span></li>`).join("")
    : `<li class="ok">Nothing major to fix. Nice resume.</li>`;

  const coach = q.bullet_coaching || [];
  $("coach-panel").hidden = !coach.length;
  if (coach.length) {
    $("coach-sub").textContent = `${q.bullets.with_metrics} of ${q.bullets.total} bullets have numbers, ${q.bullets.strong_verbs} start with a strong verb. Rewrite these first:`;
    $("coach-list").innerHTML = coach.map((c) =>
      `<div class="coach"><q>“${esc(c.original)}”</q><div class="issue">${esc(c.issue)}</div><div class="tip">${esc(c.tip)}</div></div>`).join("");
  }

  const groups = f.skills_by_category || {};
  $("resume-skills").innerHTML = Object.keys(groups).length
    ? Object.entries(groups).map(([cat, list]) => `<div class="group-label">${esc(cat)}</div><div class="tags">${tags(list)}</div>`).join("")
    : `<p class="muted">No known skills detected. Add a Skills section with standard names.</p>`;

  const un = q.unproven_skills || [];
  $("unproven").hidden = !un.length;
  if (un.length) $("unproven").innerHTML = `<b>Listed but not proven:</b> ${esc(un.join(", "))}. Recruiters trust skills that appear in a project or job bullet.`;

  const row = (k, v) => (v ? `<dt>${k}</dt><dd>${esc(v)}</dd>` : "");
  $("field-list").innerHTML =
    row("Name", f.name) + row("Email", f.email) + row("Phone", f.phone) + row("LinkedIn", f.linkedin) +
    row("GitHub", f.github) + row("Portfolio", f.portfolio) +
    row("Experience", f.years_experience ? `${f.years_experience} years (estimated)` : "Not detected") +
    row("Education", f.education_level) + row("Length", `${f.word_count} words`);

  animate($("parsed-results"));
}

matchBtn.addEventListener("click", async () => {
  const jd = $("job-description").value.trim();
  if (!jd || !currentResumeId) return;
  matchBtn.disabled = true;
  matchBtn.textContent = "Checking…";
  try {
    renderMatch(await api("/api/match", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_id: currentResumeId, job_description: jd }),
    }));
  } catch (err) {
    alert(err.message);
  } finally {
    matchBtn.disabled = false;
    matchBtn.textContent = "Check my fit";
  }
});

function renderMatch(d) {
  $("match-results").hidden = false;
  $("match-ring").innerHTML = ringHTML(d.score, "% fit");
  $("match-explanation").textContent = d.explanation;
  $("match-breakdown").innerHTML = d.breakdown.map((b) => barRow(b.label, b.value, scoreColor(b.value), b.value + "%")).join("");

  const w = d.what_if;
  $("whatif").hidden = !w;
  if (w) {
    $("whatif").className = "panel whatif";
    $("whatif").innerHTML = `<div class="gain">+${w.gain}</div><div><b>Quickest way to improve</b>
      <p>Adding ${w.skills.map(esc).join(", ")} to your resume (if you genuinely have them) could lift your fit to about ${w.new_score}%.</p></div>`;
  }

  const lvl = (s) => `<span class="tag ${s.cls}">${esc(s.skill)}<em>${esc(s.level)}</em></span>`;
  $("matched-skills").innerHTML = d.matched_skills.length
    ? `<div class="tags">${d.matched_skills.map((s) => lvl({ ...s, cls: "match" })).join("")}</div>`
    : `<p class="muted">No overlap with the skills this job names.</p>`;
  $("missing-skills").innerHTML = d.missing_skills.length
    ? `<div class="tags">${d.missing_skills.map((s) => lvl({ ...s, cls: "miss" })).join("")}</div>`
    : `<p class="muted">No gaps found. You cover every skill named in the posting.</p>`;
  $("bonus-wrap").hidden = !d.bonus_skills.length;
  $("bonus-skills").innerHTML = `<div class="tags">${tags(d.bonus_skills, "bonus")}</div>`;

  $("resource-links").innerHTML = d.missing_skills.length
    ? d.missing_skills.map((m) => `<li><div>${esc(m.skill)}<small>${esc(m.level)}</small></div>
        <a href="${esc(m.resource.url)}" target="_blank" rel="noopener">${m.resource.curated ? "Open guide" : "Find courses"}</a></li>`).join("")
    : `<li>Nothing to learn for this role. Time to apply.</li>`;

  animate($("match-results"));
  $("match-results").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* =========================================================
   TAB 2: recruiter mode
   ========================================================= */
const batchInput = $("batch-resume-input");
let pendingFiles = [];

function setPending(files) {
  pendingFiles = Array.from(files);
  $("batch-file-label").innerHTML = pendingFiles.length
    ? `<b>${pendingFiles.length} file${pendingFiles.length > 1 ? "s" : ""} ready</b> (click to change)`
    : "Drop resumes here or <u>browse</u>";
}
batchInput.addEventListener("change", () => setPending(batchInput.files));
wireDrop($("batch-dropzone"), setPending);

$("batch-upload-btn").addEventListener("click", async () => {
  if (!pendingFiles.length) return showStatus($("batch-status"), "Select candidate resumes first.", "error");
  showStatus($("batch-status"), `Parsing ${pendingFiles.length} resume(s)…`, "info");
  const fd = new FormData();
  pendingFiles.forEach((f) => fd.append("resumes", f));
  try {
    const data = await api("/api/batch-upload", { method: "POST", body: fd });
    pool.push(...data.candidates);
    const skipped = data.errors.length ? ` Skipped ${data.errors.length}: ${data.errors.join(" ")}` : "";
    showStatus($("batch-status"), `Added ${data.candidates.length} candidate(s).${skipped}`, data.errors.length ? "info" : "success");
    batchInput.value = "";
    setPending([]);
    renderPool();
  } catch (err) {
    showStatus($("batch-status"), err.message, "error");
  }
});

function renderPool() {
  $("pool").hidden = !pool.length;
  $("pool-count").textContent = `${pool.length} candidate${pool.length === 1 ? "" : "s"}`;
  $("pool-list").innerHTML = pool.map((c, i) =>
    `<li><span>${esc(c.name)} <span class="muted">· ATS ${c.ats_score}</span></span><button data-i="${i}" aria-label="Remove ${esc(c.name)}">×</button></li>`).join("");
}
$("pool-list").addEventListener("click", (e) => {
  const i = e.target.dataset && e.target.dataset.i;
  if (i !== undefined) { pool.splice(+i, 1); renderPool(); }
});
$("pool-clear").addEventListener("click", () => { pool = []; renderPool(); });

$("rank-btn").addEventListener("click", async () => {
  const jd = $("recruiter-jd").value.trim();
  if (!pool.length) return alert("Upload candidate resumes first.");
  if (!jd) return alert("Paste the job description.");
  const btn = $("rank-btn");
  btn.disabled = true;
  btn.textContent = "Ranking…";
  try {
    lastRank = await api("/api/recruiter-rank", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: jd, resume_ids: pool.map((c) => c.resume_id) }),
    });
    renderRanking();
    $("ranking-results").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Rank candidates";
  }
});

$("blind-toggle").addEventListener("change", () => lastRank && renderRanking());

function displayName(r, i) {
  if (!$("blind-toggle").checked) return r.name;
  const idx = pool.findIndex((c) => c.resume_id === r.resume_id);
  return `Candidate ${String.fromCharCode(65 + ((idx >= 0 ? idx : i) % 26))}`;
}

function renderRanking() {
  const d = lastRank, blind = $("blind-toggle").checked;
  $("ranking-results").hidden = false;
  $("candidate-count-tag").textContent = d.total_candidates;

  $("rank-cards").innerHTML = d.rankings.map((r, i) => {
    const vcls = r.overall >= 70 ? "v1" : r.overall >= 45 ? "v2" : "v3";
    const exp = r.years ? `${r.years} yrs experience` : "Experience not detected";
    const meta = [exp, r.education !== "Not detected" ? r.education : null, blind ? null : r.filename].filter(Boolean).map(esc).join(" · ");
    return `<article class="cand ${i === 0 ? "first" : ""}">
      <div class="rank-no">${i + 1}</div>
      <div>
        <h3>${esc(displayName(r, i))}<span class="verdict ${vcls}">${esc(r.verdict)}</span></h3>
        <div class="meta">${meta}</div>
        <div class="tags">${tags(r.matched_skills.slice(0, 8), "match") || '<span class="muted small">No matching skills</span>'}</div>
        ${r.missing_skills.length ? `<div class="tags">${tags(r.missing_skills.slice(0, 8), "miss")}</div>` : ""}
      </div>
      <div class="scores"><span class="big">${r.overall}</span><small>overall</small><small>${r.score}% match · ATS ${r.ats_score}</small></div>
      <details class="iv"><summary>Questions to ask in the interview</summary>
        <ul>${r.interview_focus.map((q) => `<li>${esc(q)}</li>`).join("") || "<li>No specific gaps found. Ask about their strongest project.</li>"}</ul>
        ${r.top_recommendation ? `<p class="muted small" style="margin-top:8px">Resume note: ${esc(r.top_recommendation)}</p>` : ""}
      </details></article>`;
  }).join("");

  const head = d.jd_skills.map((s) => `<th class="${s.level === "Critical" ? "crit" : ""}" title="${esc(s.level)}">${esc(s.skill)}</th>`).join("");
  $("matrix").innerHTML = `<thead><tr><th>Candidate</th>${head}</tr></thead><tbody>${d.rankings.map((r, i) =>
    `<tr><td>${esc(displayName(r, i))}</td>${r.has.map((h) => `<td class="${h ? "cell-y" : "cell-n"}">${h ? "✓" : "–"}</td>`).join("")}</tr>`).join("")}</tbody>`;

  $("pool-coverage").innerHTML = d.pool_coverage.length
    ? d.pool_coverage.map((p) => barRow(p.skill, p.pct, p.pct < 34 ? "var(--coral)" : p.pct < 67 ? "var(--amber)" : "var(--mint)", p.pct + "%")).join("")
    : '<p class="muted">The job description names no recognised skills.</p>';
  animate($("ranking-results"));
}

$("csv-btn").addEventListener("click", () => {
  if (!lastRank) return;
  const blind = $("blind-toggle").checked;
  const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = [["Rank", "Candidate", "File", "Overall", "Match %", "ATS", "Verdict", "Years", "Matched skills", "Missing skills"]];
  lastRank.rankings.forEach((r, i) => rows.push([i + 1, displayName(r, i), blind ? "" : r.filename, r.overall, r.score, r.ats_score,
    r.verdict, r.years, r.matched_skills.join("; "), r.missing_skills.join("; ")]));
  const blob = new Blob([rows.map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "candidate-ranking.csv" });
  a.click();
  URL.revokeObjectURL(a.href);
});

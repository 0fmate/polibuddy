/* PoliBuddy · demo interface (no frameworks; KaTeX renders every formula). */

const $ = (sel) => document.querySelector(sel);
const state = {
  session: null, phase: "awaiting_plan", boardDirty: false, status: { mode: "offline" },
  exercise: null, files: [], teacherCourse: "calculus1",
};

const MOODS = {
  default: "Ready to try your idea",
  studying: "Studying your plan…",
  thinking: "Hmm… something doesn't add up",
  retry: "Try again, you're close",
  idea: "I've got a hint for you",
  success: "You did it!",
};
const TOPIC_STATUS = {
  todo: { img: "default", text: "to do" },
  in_progress: { img: "retry", text: "in progress" },
  with_help: { img: "idea", text: "solved with help" },
  alone: { img: "success", text: "solved on your own" },
};

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    err.status = r.status;
    throw err;
  }
  return r.json();
}

/* ---------------- Formulas: LaTeX everywhere ---------------- */
function renderMath(el) {
  if (!window.renderMathInElement) return;
  try {
    window.renderMathInElement(el, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      throwOnError: false,
    });
  } catch (_) { /* text stays readable */ }
}

// Turns plain maths typed by the student (x^2, sin 3x, v0/g, ≈) into LaTeX, so nothing shows unformatted.
const FUNCTIONS = /^(sin|cos|tan|sqrt|exp|ln|lim)(\(|$)/i;
function strongToken(w) {
  if (/^(m\/s\^?2?|km\/h|m\/s²)$/i.test(w)) return false; // units stay text
  return /[\^\/=≈*·]/.test(w) || FUNCTIONS.test(w) || /^\d+[xtvghn]$/.test(w) || /^[a-z]0$/.test(w) || /^[=≈+\-−*·\/^]+$/.test(w);
}
function weakToken(w) {
  return /^\(?-?\d+(\.\d+)?\)?$/.test(w) || /^[xtvghns]$/.test(w) || /^[()+\-−]$/.test(w) || /^\(?\d*[xtvghn]\)?$/.test(w);
}
function toLatex(span) {
  let s = span.replace(/≈/g, " \\approx ").replace(/[·*]/g, " \\cdot ").replace(/−/g, "-");
  s = s.replace(/\bsqrt\s*\(([^()]*)\)/gi, "\\sqrt{$1}");
  s = s.replace(/\b(sin|cos|tan|ln|exp)\b\s*/gi, (m, f) => `\\${f.toLowerCase()} `);
  // fractions first, so that (3x)^3/6 becomes \frac{(3x)^3}{6}
  const unwrap = (t) => (/^\([^()]*\)$/.test(t) ? t.slice(1, -1) : t);
  s = s.replace(/((?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?)\s*\/\s*((?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?)/g,
    (m, a, b) => `\\frac{${unwrap(a)}}{${unwrap(b)}}`);
  s = s.replace(/\b([a-z])0\b/g, "$1_0");
  s = s.replace(/\^\(([^()]*)\)/g, "^{$1}").replace(/\^(-?[0-9a-z]+)/g, "^{$1}");
  return s;
}
function mathify(text) {
  if (text.includes("$")) return text;
  text = text.replace(/²/g, "^2").replace(/³/g, "^3");
  const words = text.split(/(\s+)/);
  const clean = (w) => w.replace(/[,.;:?!]+$/, "");
  const strong = words.map((w) => w.trim() && strongToken(clean(w)));
  const weak = words.map((w) => w.trim() && weakToken(clean(w)));
  const inside = strong.slice();
  for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i < words.length; i++) {
      if (!words[i].trim() || inside[i] || !weak[i]) continue;
      const near = (j) => j >= 0 && j < words.length && inside[j];
      let k = i - 1; while (k >= 0 && !words[k].trim()) k--;
      let h = i + 1; while (h < words.length && !words[h].trim()) h++;
      const endBefore = k >= 0 && /[,.;:?!]$/.test(words[k]);
      if ((near(k) && !endBefore) || (near(h) && !/[,.;:?!]$/.test(words[i]))) inside[i] = true;
    }
  }
  let out = "", buf = [];
  const flush = () => {
    if (!buf.length) return;
    let span = buf.join("").trim();
    const tail = (span.match(/[,.;:?!]+$/) || [""])[0];
    span = span.slice(0, span.length - tail.length);
    // a formula cut in half ("v =") or a lone number stays plain text
    out += /^[a-z]?\s*[=≈]$|^-?\d+(\.\d+)?$/.test(span.trim()) ? span + tail : `$${toLatex(span)}$${tail}`;
    buf = [];
  };
  for (let i = 0; i < words.length; i++) {
    if (inside[i]) {
      buf.push(words[i]);
      if (/[,.;:?!]$/.test(words[i])) flush();
    } else if (!words[i].trim() && buf.length) {
      let h = i + 1; while (h < words.length && !words[h].trim()) h++;
      if (h < words.length && inside[h]) buf.push(words[i]); else { flush(); out += words[i]; }
    } else { flush(); out += words[i]; }
  }
  flush();
  return out;
}

/* ---------------- Views ---------------- */
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  const view = t.dataset.view;
  $("#view-student").hidden = view !== "student";
  $("#view-teacher").hidden = view !== "teacher";
  if (view === "teacher") loadTeacher($("#course").value);
  else prepareBoard();
}));

/* ---------------- Student: exercise, mascot, progress ---------------- */
function renderExercise(ex) {
  state.exercise = ex;
  $("#ex-course").textContent = ex.course_name;
  $("#ex-topic").textContent = ex.topic;
  $("#ex-level").textContent = `Level ${ex.level}`;
  const box = $("#ex-formula");
  box.classList.toggle("text-mode", !ex.latex);
  if (ex.latex && window.katex) {
    try { window.katex.render(ex.latex, box, { displayMode: true, throwOnError: false }); }
    catch (_) { box.textContent = ex.text; }
  } else {
    box.textContent = ex.text;
    renderMath(box);
  }
  $("#ex-code").hidden = !ex.code;
  $("#ex-code").textContent = ex.code || "";
  $("#course").value = ex.course;
  $("#progress-course").textContent = ex.course_name;
}

function renderMascot(mood) {
  const img = $("#mascot");
  const src = `/brand/mascot/${mood}.svg`;
  if (!img.src.endsWith(src)) {
    img.src = src;
    img.classList.remove("swap");
    void img.offsetWidth;
    img.classList.add("swap");
  }
  $("#mood").textContent = MOODS[mood] || "";
  $("#voice-mascot").src = src;
}

function renderProgress(list) {
  const box = $("#progress");
  box.innerHTML = "";
  list.forEach((p) => {
    const info = TOPIC_STATUS[p.status];
    const b = document.createElement("button");
    b.type = "button";
    b.className = `prog ${p.status}${state.exercise && state.exercise.id === p.id ? " current" : ""}`;
    b.innerHTML = `<img alt=""><div><div class="prog-name"></div><div class="prog-status"></div></div>`;
    b.querySelector("img").src = `/brand/mascot/${info.img}.svg`;
    b.querySelector(".prog-name").textContent = p.title;
    b.querySelector(".prog-status").textContent = `L${p.level} · ${info.text}`;
    b.title = `${p.title}: ${info.text}`;
    b.addEventListener("click", () => startSession(p.id));
    box.appendChild(b);
  });
}

function addMessage(text, role, files = [], options = {}) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  if (options.voice) {
    const tag = document.createElement("span");
    tag.className = "voice-tag";
    tag.textContent = "🎙 voice";
    div.appendChild(tag);
  }
  const body = document.createElement("span");
  body.textContent = role.startsWith("student") ? mathify(text) : text;
  div.appendChild(body);
  if (files.length) {
    const chips = document.createElement("div");
    chips.className = "file-chips";
    files.forEach((f) => chips.appendChild(fileChip(f, false)));
    div.appendChild(chips);
  }
  $("#messages").appendChild(div);
  if (!role.includes("pending")) renderMath(body);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}

function renderRope(level, max) {
  const box = $("#rope");
  box.innerHTML = "";
  for (let i = 1; i <= max; i++) {
    const d = document.createElement("i");
    if (i <= level) d.className = "on";
    box.appendChild(d);
  }
}

function renderQuick() {
  const box = $("#quick");
  box.innerHTML = "";
  let choices = [];
  if (state.phase === "awaiting_confirmation") choices = ["Yes, exactly", "No, wait"];
  else if (state.phase === "awaiting_plan") {
    if (state.exercise?.demo_plan) choices.push(state.exercise.demo_plan);
    choices.push("Just tell me the solution");
  }
  choices.forEach((c) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = mathify(c);
    b.addEventListener("click", () => send(c));
    box.appendChild(b);
    renderMath(b);
  });
}

function resetResults() {
  $("#results-empty").hidden = false;
  $("#results-body").hidden = true;
  $("#verdict").hidden = true;
  $("#next").hidden = true;
}

function applyReply(r) {
  state.session = r.session;
  state.phase = r.state;
  if (r.whiteboard_text) addMessage(`I read on the whiteboard: ${r.whiteboard_text}`, "read");
  (r.attachments || []).forEach((a) => {
    const div = addMessage(a.ok ? `I read ${a.name}: ${a.summary}` : `${a.name}: ${a.note}`, "read");
    if (!a.ok) div.classList.add("failed");
  });
  r.messages.forEach((m) => addMessage(m, "buddy"));
  renderMascot(r.mood);
  renderRope(r.help_level, r.max_help_level);
  renderProgress(r.progress || []);
  renderQuick();
  if (r.run) showResults(r.run);
  $("#next").hidden = r.state !== "solved";
}

async function startSession(exercise, course) {
  const r = await api("/api/session", { student: $("#student").value || "demo", exercise, course });
  $("#messages").innerHTML = "";
  resetResults();
  renderExercise(r.exercise);
  applyReply(r);
}

/* ---------------- Attachments (photos and documents) ---------------- */
const MAX_FILE = 8 * 1024 * 1024;

function fileChip(f, removable) {
  const c = document.createElement("span");
  c.className = "file-chip";
  if (f.type.startsWith("image/")) {
    const img = document.createElement("img");
    img.src = f.data;
    img.alt = "";
    c.appendChild(img);
  } else {
    c.append(f.name.toLowerCase().endsWith(".pdf") ? "📄" : "📎");
  }
  const s = document.createElement("span");
  s.textContent = f.name;
  c.appendChild(s);
  if (removable) {
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.title = "Remove";
    x.addEventListener("click", () => {
      state.files = state.files.filter((a) => a !== f);
      renderPreview();
    });
    c.appendChild(x);
  }
  return c;
}

function renderPreview() {
  const box = $("#preview");
  box.innerHTML = "";
  state.files.forEach((f) => box.appendChild(fileChip(f, true)));
  box.hidden = state.files.length === 0;
}

const readAsDataURL = (blob) => new Promise((ok) => {
  const fr = new FileReader();
  fr.onload = () => ok(fr.result);
  fr.readAsDataURL(blob);
});

$("#clip").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", async (e) => {
  for (const file of [...e.target.files].slice(0, 5)) {
    if (file.size > MAX_FILE) { addMessage(`${file.name} is too large (8 MB max).`, "read failed"); continue; }
    state.files.push({ name: file.name, type: file.type || "", data: await readAsDataURL(file) });
  }
  e.target.value = "";
  renderPreview();
});

/* ---------------- Sending ---------------- */
async function send(text, options = {}) {
  text = (text ?? $("#input").value).trim();
  // the whiteboard explains the plan; it is not needed to confirm it
  const attachBoard = $("#attach-board").checked && state.boardDirty && state.phase !== "awaiting_confirmation";
  const files = options.voice ? [] : state.files;
  if (!text && !attachBoard && !files.length) return null;
  addMessage(text || (files.length ? "(sending you these files)" : "(sending you the whiteboard)"), "student", files, options);
  if (!options.voice) {
    $("#input").value = "";
    state.files = [];
    renderPreview();
  }
  const reading = (attachBoard || files.length) && state.status.vision;
  const wait = addMessage(reading ? "PoliBuddy is reading…" : "PoliBuddy is thinking…", "buddy pending");
  renderMascot("studying");
  $("#send").disabled = true;
  try {
    const r = await api("/api/message", {
      session: state.session, text,
      whiteboard: attachBoard ? $("#whiteboard").toDataURL("image/png") : null,
      files,
    });
    wait.remove();
    applyReply(r);
    return r;
  } catch (e) {
    wait.remove();
    if (e.status === 429) addMessage("Lots of people are trying the demo right now: wait a minute and send it again.", "buddy");
    else if (e.status === 404) addMessage("This session expired (the demo server restarted). Reload the page to start again.", "buddy");
    else addMessage(`Connection problem: ${e.message}`, "buddy");
    renderMascot("default");
    return null;
  } finally {
    $("#send").disabled = false;
    if (!options.voice) $("#input").focus();
  }
}

$("#composer").addEventListener("submit", (e) => { e.preventDefault(); send(); });
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("#next").addEventListener("click", async () => {
  const r = await api("/api/next", { session: state.session });
  $("#messages").innerHTML = "";
  resetResults();
  renderExercise(r.exercise);
  applyReply(r);
});
$("#student").addEventListener("change", () => startSession(null, $("#course").value));
$("#course").addEventListener("change", (e) => {
  if (!$("#view-teacher").hidden) loadTeacher(e.target.value);
  startSession(null, e.target.value);
});

/* ---------------- Voice conversation ---------------- */
// Speech-to-text: the server (e.g. Whisper on Groq) when available, otherwise the browser's recognition.
// Text-to-speech: the server when a TTS model is configured, otherwise the browser's speechSynthesis.
const voice = {
  active: false, stream: null, recorder: null, ctx: null, analyser: null, chunks: [],
  turns: [], start: 0, timer: null, recognizer: null, audio: null, serverStt: false,
};

function voiceStatus(text, speaking = false) {
  $("#voice-status").textContent = text;
  $("#voice").classList.toggle("speaking", speaking);
}

function animateWaves(level) {
  document.querySelectorAll("#voice-waves i").forEach((b, i) => {
    const h = 6 + Math.min(1, level * (0.6 + 0.4 * Math.sin(Date.now() / 120 + i))) * 20;
    b.style.height = `${h}px`;
  });
}

function addTurn(who, text) {
  voice.turns.push({ who, text, t: Math.round((Date.now() - voice.start) / 1000) });
  $("#voice-last").textContent = `${who === "you" ? "You" : "PoliBuddy"}: ${text.replace(/\$/g, "")}`;
}

async function startVoice() {
  if (voice.active) return;
  const serverStt = state.status.stt && navigator.mediaDevices && window.MediaRecorder;
  const Recognizer = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!serverStt && !Recognizer) {
    addMessage("Voice is not available here: it needs a browser with speech recognition (Chrome, Edge) or a speech-to-text model on the server.", "read failed");
    return;
  }
  voice.active = true;
  voice.turns = [];
  voice.start = Date.now();
  voice.serverStt = Boolean(serverStt);
  $("#voice").hidden = false;
  $("#mic").classList.add("recording");
  try {
    if (voice.serverStt) {
      voice.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      voice.ctx = new (window.AudioContext || window.webkitAudioContext)();
      voice.analyser = voice.ctx.createAnalyser();
      voice.analyser.fftSize = 1024;
      voice.ctx.createMediaStreamSource(voice.stream).connect(voice.analyser);
    }
    listen();
  } catch (e) {
    addMessage(`I can't use the microphone: ${e.message}`, "read failed");
    closeVoice(false);
  }
}

function listen() {
  if (!voice.active) return;
  voiceStatus("Listening… explain your idea");
  if (!voice.serverStt) return listenInBrowser();

  voice.chunks = [];
  const type = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  voice.recorder = new MediaRecorder(voice.stream, type ? { mimeType: type } : {});
  voice.recorder.ondataavailable = (e) => { if (e.data.size) voice.chunks.push(e.data); };
  voice.recorder.onstop = () => processAudio();
  voice.recorder.start(250);

  // simple voice-activity detection: stop after ~1.3 s of silence once the student has spoken
  const buf = new Uint8Array(voice.analyser.fftSize);
  let spoke = false, silentSince = Date.now();
  const started = Date.now();
  clearInterval(voice.timer);
  voice.timer = setInterval(() => {
    voice.analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) sum += ((v - 128) / 128) ** 2;
    const rms = Math.sqrt(sum / buf.length);
    animateWaves(rms * 12);
    if (rms > 0.035) { spoke = true; silentSince = Date.now(); }
    if ((spoke && Date.now() - silentSince > 1300) || Date.now() - started > 30000) endTurn();
  }, 80);
}

function endTurn() {
  clearInterval(voice.timer);
  animateWaves(0);
  if (voice.recorder && voice.recorder.state === "recording") voice.recorder.stop();
  if (voice.recognizer) voice.recognizer.stop();
}

async function processAudio() {
  if (!voice.active) return;
  const blob = new Blob(voice.chunks, { type: voice.recorder.mimeType || "audio/webm" });
  if (blob.size < 2500) return listen();
  voiceStatus("Transcribing…");
  try {
    const { text } = await api("/api/voice/transcribe", { audio: await readAsDataURL(blob), type: blob.type });
    await studentTurn(text);
  } catch (e) {
    voiceStatus(e.status === 429 ? "Too many requests, wait a moment" : "I didn't catch that, try again");
    setTimeout(listen, e.status === 429 ? 5000 : 900);
  }
}

function listenInBrowser() {
  const Recognizer = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Recognizer();
  voice.recognizer = rec;
  rec.lang = "en-US";
  rec.interimResults = false;
  let said = "";
  rec.onresult = (e) => { said = [...e.results].map((r) => r[0].transcript).join(" "); };
  rec.onerror = () => {};
  rec.onend = () => {
    voice.recognizer = null;
    if (!voice.active) return;
    if (said.trim()) studentTurn(said.trim()); else listen();
  };
  clearInterval(voice.timer);
  voice.timer = setInterval(() => animateWaves(Math.random() * 0.6), 120);
  rec.start();
}

async function studentTurn(text) {
  if (!voice.active) return;
  addTurn("you", text);
  voiceStatus("PoliBuddy is thinking…");
  const r = await send(text, { voice: true });
  if (!r || !voice.active) return voice.active && listen();
  const reply = r.messages.join(" ");
  addTurn("buddy", reply);
  await speak(reply);
  if (voice.active) listen();
}

function spokenText(text) {
  return text.replace(/\$/g, "").replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "$1 over $2").replace(/\\[a-z]+/g, " ").replace(/[{}^_]/g, " ");
}

function speakInBrowser(text) {
  if (!window.speechSynthesis) return Promise.resolve();
  return new Promise((ok) => {
    const u = new SpeechSynthesisUtterance(spokenText(text));
    u.lang = "en-US";
    u.onend = ok;
    u.onerror = ok;
    speechSynthesis.speak(u);
  });
}

async function speak(text) {
  voiceStatus("PoliBuddy is speaking…", true);
  clearInterval(voice.timer);
  voice.timer = setInterval(() => animateWaves(0.35 + Math.random() * 0.5), 110);
  try {
    let played = false;
    if (state.status.tts) {
      const res = await fetch("/api/voice/speak", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
      });
      if (res.ok) {
        const url = URL.createObjectURL(await res.blob());
        await new Promise((ok) => {
          voice.audio = new Audio(url);
          voice.audio.onended = ok;
          voice.audio.onerror = ok;
          voice.audio.play().catch(ok);
        });
        URL.revokeObjectURL(url);
        played = true;
      }
    }
    if (!played) await speakInBrowser(text);
  } catch (_) { /* the text is in the chat anyway */ }
  clearInterval(voice.timer);
  animateWaves(0);
}

function closeVoice(withTranscript = true) {
  voice.active = false;
  clearInterval(voice.timer);
  if (voice.recorder && voice.recorder.state === "recording") { voice.recorder.onstop = null; voice.recorder.stop(); }
  if (voice.recognizer) { voice.recognizer.onend = null; voice.recognizer.abort(); }
  if (voice.audio) voice.audio.pause();
  if (window.speechSynthesis) speechSynthesis.cancel();
  if (voice.stream) voice.stream.getTracks().forEach((t) => t.stop());
  if (voice.ctx) voice.ctx.close();
  voice.stream = voice.ctx = voice.recorder = null;
  $("#voice").hidden = true;
  $("#mic").classList.remove("recording");
  if (withTranscript && voice.turns.length) showTranscript();
}

function showTranscript() {
  const duration = Math.max(1, Math.round((Date.now() - voice.start) / 1000));
  const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const card = document.createElement("div");
  card.className = "transcript";
  card.innerHTML = `<div class="transcript-head"><div><strong>Voice conversation transcript</strong>
    <div class="muted small"></div></div><button type="button" class="link-btn">Download .txt</button></div><ol></ol>`;
  card.querySelector(".muted").textContent = `${mmss(duration)} · ${voice.turns.length} turns · ${state.exercise?.title || ""}`;
  const ol = card.querySelector("ol");
  voice.turns.forEach((t) => {
    const li = document.createElement("li");
    li.className = t.who === "you" ? "you" : "buddy";
    li.innerHTML = `<time></time><b></b> <span></span>`;
    li.querySelector("time").textContent = mmss(t.t);
    li.querySelector("b").textContent = t.who === "you" ? "You:" : "PoliBuddy:";
    li.querySelector("span").textContent = t.who === "you" ? mathify(t.text) : t.text;
    ol.appendChild(li);
  });
  const lines = ["PoliBuddy · voice conversation transcript", `Exercise: ${state.exercise?.title || ""}`, `Duration: ${mmss(duration)}`, ""]
    .concat(voice.turns.map((t) => `[${mmss(t.t)}] ${t.who === "you" ? "You" : "PoliBuddy"}: ${t.text}`));
  card.querySelector("button").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain" }));
    a.download = `polibuddy-transcript-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.txt`;
    a.click();
  });
  $("#messages").appendChild(card);
  renderMath(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

$("#mic").addEventListener("click", () => (voice.active ? closeVoice() : startVoice()));
$("#voice-end-turn").addEventListener("click", endTurn);
$("#voice-close").addEventListener("click", () => closeVoice());

/* ---------------- Results: table and chart ---------------- */
function showResults(run) {
  $("#results-empty").hidden = true;
  $("#results-body").hidden = false;
  const v = $("#verdict");
  v.hidden = false;
  v.className = `verdict ${run.works ? "yes" : "no"}`;
  v.textContent = run.works ? "It works!" : "Doesn't add up";
  $("#predicted-label").textContent = run.predicted_label;
  $("#observed-label").textContent = run.observed_label;
  $("#predicted-value").textContent = run.predicted;
  $("#observed-value").textContent = "…";

  const thead = $("#results-table thead");
  thead.innerHTML = "";
  const trh = document.createElement("tr");
  run.columns.forEach((c) => { const th = document.createElement("th"); th.textContent = c; trh.appendChild(th); });
  thead.appendChild(trh);

  const tbody = $("#results-table tbody");
  tbody.innerHTML = "";
  const step = Math.max(90, Math.min(380, 1600 / Math.max(run.rows.length, 1)));
  run.rows.forEach((row, i) => {
    setTimeout(() => {
      const tr = document.createElement("tr");
      tr.className = `enter${i === run.highlight ? " highlight" : ""}`;
      row.forEach((c) => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
      tbody.appendChild(tr);
      tr.scrollIntoView({ block: "nearest" });
      if (i === run.rows.length - 1) $("#observed-value").textContent = run.observed;
    }, step * i + 150);
  });
  if (!run.rows.length) $("#observed-value").textContent = run.observed;
  drawChart(run.chart, true);
}

const COLOR = { true: "#073766", yours: "#ff8a18", target: "#00a99b" };

function drawChart(g, animate) {
  const svg = $("#chart");
  const W = 440, H = 270, m = { l: 48, r: 18, t: 18, b: 34 };
  const css = getComputedStyle(document.documentElement);
  const cLine = css.getPropertyValue("--line").trim();
  const cMuted = css.getPropertyValue("--muted").trim();
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const ys = [];
  g.series.forEach((s) => s.points.forEach((p) => { if (p[1] !== null) ys.push(p[1]); }));
  g.lines.forEach((l) => ys.push(l.y));
  if (g.marker && g.marker.y !== null) ys.push(g.marker.y);
  ys.push(0);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  const pad = (yMax - yMin) * 0.12 || 1;
  yMin -= pad; yMax += pad;
  const X = (x) => m.l + ((x - g.x_min) / (g.x_max - g.x_min)) * (W - m.l - m.r);
  const Y = (y) => m.t + (1 - (y - yMin) / (yMax - yMin)) * (H - m.t - m.b);
  const num = (v) => v.toLocaleString("en-US", { maximumFractionDigits: 2 });

  const path = (points) => {
    let d = "", open = false;
    points.forEach(([x, y]) => {
      if (y === null || y < yMin || y > yMax) { open = false; return; }
      d += `${open ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)} `;
      open = true;
    });
    return d;
  };

  let s = "";
  s += `<line x1="${m.l}" y1="${Y(0)}" x2="${W - m.r}" y2="${Y(0)}" stroke="${cLine}" stroke-width="1.2"/>`;
  if (g.x_min < 0 && g.x_max > 0) {
    s += `<line x1="${X(0)}" y1="${m.t}" x2="${X(0)}" y2="${H - m.b}" stroke="${cLine}" stroke-dasharray="3 4"/>`;
  }
  [yMin + pad, yMax - pad].forEach((y) => {
    s += `<text x="${m.l - 6}" y="${Y(y) + 4}" text-anchor="end" font-size="13" fill="${cMuted}">${num(y)}</text>`;
  });
  s += `<text x="${m.l}" y="${H - 10}" font-size="13" fill="${cMuted}">${num(g.x_min)}</text>`;
  s += `<text x="${W - m.r}" y="${H - 10}" text-anchor="end" font-size="13" fill="${cMuted}">${num(g.x_max)}</text>`;
  s += `<text x="${(m.l + W - m.r) / 2}" y="${H - 10}" text-anchor="middle" font-size="13" fill="${cMuted}">${esc(g.x_label)}</text>`;

  g.lines.forEach((l) => {
    s += `<line x1="${m.l}" y1="${Y(l.y)}" x2="${W - m.r}" y2="${Y(l.y)}" stroke="${COLOR[l.role]}" stroke-width="2.6" stroke-dasharray="7 6"/>`;
    s += `<text x="${W - m.r - 4}" y="${Y(l.y) - 7}" text-anchor="end" font-size="12.5" font-weight="700" fill="${COLOR[l.role]}">${esc(l.label)}</text>`;
  });
  g.series.forEach((serie) => {
    const dashed = serie.role === "yours" ? ' stroke-dasharray="7 6"' : "";
    s += `<path class="curve ${serie.role}" d="${path(serie.points)}" fill="none" stroke="${COLOR[serie.role]}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"${dashed}/>`;
    if (serie.show_points) {
      serie.points.forEach(([x, y]) => {
        if (y !== null) s += `<circle cx="${X(x)}" cy="${Y(y)}" r="3.6" fill="${COLOR[serie.role]}"/>`;
      });
    }
  });
  const mk = g.marker;
  if (mk && mk.y !== null && mk.y >= yMin && mk.y <= yMax) {
    const c = COLOR[mk.role];
    const right = X(mk.x) > W * 0.62;
    s += `<circle cx="${X(mk.x)}" cy="${Y(mk.y)}" r="6.5" fill="#fff" stroke="${c}" stroke-width="3.2"/>`;
    s += `<text x="${X(mk.x) + (right ? -12 : 12)}" y="${Y(mk.y) - 12}" text-anchor="${right ? "end" : "start"}" font-size="15" font-weight="800" fill="${c}">${esc(mk.text)}</text>`;
  }
  svg.innerHTML = s;

  const legend = $("#legend");
  legend.innerHTML = "";
  [...g.series, ...g.lines].forEach((el) => {
    if (!el.label) return;
    const span = document.createElement("span");
    span.innerHTML = `<i style="background:${COLOR[el.role]}"></i>`;
    span.append(el.label);
    legend.appendChild(span);
  });

  if (animate) {
    svg.querySelectorAll("path.curve.true").forEach((p) => {
      const L = p.getTotalLength();
      p.style.strokeDasharray = `${L}`;
      p.style.strokeDashoffset = `${L}`;
      p.getBoundingClientRect();
      p.style.transition = "stroke-dashoffset 1.4s ease";
      p.style.strokeDashoffset = "0";
    });
  }
}

/* ---------------- Whiteboard ---------------- */
const canvas = $("#whiteboard");
const ctx = canvas.getContext("2d");
let pen = "ink", drawing = false;

function prepareBoard() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  const copy = state.boardDirty ? canvas.toDataURL() : null;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  if (copy) { const img = new Image(); img.onload = () => ctx.drawImage(img, 0, 0, w, h); img.src = copy; }
}
function position(e) {
  const r = canvas.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}
canvas.addEventListener("pointerdown", (e) => {
  drawing = true;
  canvas.setPointerCapture(e.pointerId);
  const [x, y] = position(e);
  ctx.beginPath(); ctx.moveTo(x, y);
});
canvas.addEventListener("pointermove", (e) => {
  if (!drawing) return;
  const [x, y] = position(e);
  ctx.lineCap = "round"; ctx.lineJoin = "round";
  if (pen === "eraser") { ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 22; }
  else { ctx.strokeStyle = pen === "accent" ? "#ff8a18" : "#073766"; ctx.lineWidth = 3; }
  ctx.lineTo(x, y); ctx.stroke();
  if (!state.boardDirty) { state.boardDirty = true; $("#attach-board").checked = true; }
});
["pointerup", "pointerleave", "pointercancel"].forEach((ev) => canvas.addEventListener(ev, () => { drawing = false; }));
document.querySelectorAll("[data-pen]").forEach((b) => b.addEventListener("click", () => {
  pen = b.dataset.pen;
  document.querySelectorAll("[data-pen]").forEach((x) => x.classList.toggle("active", x === b));
}));
$("#clear-board").addEventListener("click", () => {
  state.boardDirty = false;
  $("#attach-board").checked = false;
  prepareBoard();
});
window.addEventListener("resize", prepareBoard);

/* ---------------- Teacher ---------------- */
const OUTCOME_NAMES = {
  alone: "found alone", after_question: "after a question", after_slide: "after the slide",
  with_hint: "with a hint", unsolved: "not solved",
};
const PILL = { ok: "on track", attention: "attention", no_data: "no data", not_enough: "not enough data" };

async function loadTeacher(course) {
  state.teacherCourse = course || state.teacherCourse;
  const d = await api(`/api/radar?course=${encodeURIComponent(state.teacherCourse)}`);

  const seg = $("#t-courses");
  seg.innerHTML = "";
  d.courses.forEach((c) => {
    const b = document.createElement("button");
    b.textContent = c.name;
    b.className = c.id === d.course ? "on" : "";
    b.addEventListener("click", () => loadTeacher(c.id));
    seg.appendChild(b);
  });

  $("#t-course").textContent = d.course_name;
  const real = d.real_sessions === 1 ? "1 real session" : `${d.real_sessions} real sessions`;
  $("#teacher-note").textContent = `Anonymous, aggregated data · for the demo it includes simulated sessions (${real} from this demo).`;
  $("#privacy-text").textContent =
    `The teacher only sees anonymous, aggregated data, never an individual student. Below ${d.min_sessions} sessions the data is not shown.`;
  $("#k-sessions").textContent = d.total_sessions;
  $("#k-first").textContent = `${d.first_try_pct}%`;
  $("#k-alone").textContent = `${d.alone_pct}%`;
  $("#k-critical").textContent = d.critical ? `${d.critical.title} · ${d.critical.alone_pct}% alone` : "—";

  const gaps = $("#gaps");
  gaps.innerHTML = "";
  d.gaps.forEach((g) => {
    const div = document.createElement("div");
    div.className = "gap";
    div.innerHTML = `<div class="gap-name"></div><div class="muted small"></div><div class="gap-bar"><span style="width:0%"></span></div>`;
    div.querySelector(".gap-name").textContent = g.mistake || g.title;
    div.querySelector(".muted").textContent = `${g.title}: found alone in ${g.alone_pct}% of ${g.n} sessions with a mistake`;
    gaps.appendChild(div);
    renderMath(div);
    setTimeout(() => { div.querySelector(".gap-bar span").style.width = `${g.alone_pct}%`; }, 80);
  });

  const legend = $("#outcome-legend");
  legend.innerHTML = "";
  d.outcomes.forEach((o, i) => {
    const s = document.createElement("span");
    s.innerHTML = `<i style="background:var(--s${i + 1})"></i>`;
    s.append(OUTCOME_NAMES[o]);
    legend.appendChild(s);
  });

  const bars = $("#bars");
  bars.innerHTML = "";
  d.exercises.forEach((ex) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    const name = document.createElement("div");
    name.className = "bar-name";
    name.textContent = ex.title;
    const sub = document.createElement("div");
    sub.className = "muted small";
    sub.textContent = ex.enough ? `${ex.topic} · first try ${ex.first_try_pct}%` : ex.topic;
    name.appendChild(sub);
    row.appendChild(name);

    const center = document.createElement("div");
    if (ex.enough) {
      center.className = "bar";
      d.outcomes.forEach((o, i) => {
        const span = document.createElement("span");
        span.style.width = "0%";
        span.style.background = `var(--s${i + 1})`;
        span.title = `${OUTCOME_NAMES[o]}: ${ex.outcomes_pct[o]}%`;
        center.appendChild(span);
        setTimeout(() => { span.style.width = `${ex.outcomes_pct[o]}%`; }, 80);
      });
    } else {
      center.className = "hidden-data";
      center.textContent = `not enough data (fewer than ${d.min_sessions} sessions): hidden`;
    }
    row.appendChild(center);
    const n = document.createElement("div");
    n.className = "bar-n";
    n.textContent = `${ex.n} sessions`;
    row.appendChild(n);
    bars.appendChild(row);
  });

  const demo = await api(`/api/crash-test/demo?course=${encodeURIComponent(d.course)}`);
  $("#questions").value = demo.questions.join("\n");
  $("#crash-report").innerHTML = "";
}

$("#crash-btn").addEventListener("click", async () => {
  const { report } = await api("/api/crash-test", { questions: $("#questions").value.split("\n") });
  const box = $("#crash-report");
  box.innerHTML = "";
  report.forEach((item) => {
    const div = document.createElement("div");
    div.className = "crash-item";
    div.innerHTML = `<div class="q"><span class="pill"></span><span class="t"></span></div><div class="muted small c"></div><div class="small r"></div>`;
    div.querySelector(".pill").className = `pill ${item.status}`;
    div.querySelector(".pill").textContent = PILL[item.status] || item.status;
    div.querySelector(".t").textContent = `${item.number}. ${mathify(item.question)}`;
    div.querySelector(".c").textContent = item.concepts.length ? `Concepts: ${item.concepts.join(", ")}` : "";
    div.querySelector(".r").textContent = item.text;
    box.appendChild(div);
    renderMath(div);
  });
});

/* ---------------- Start ---------------- */
async function boot() {
  prepareBoard();
  try {
    const s = await api("/api/status");
    state.status = s;
    const badge = $("#mode-badge");
    badge.textContent = s.mode === "model" ? `AI · ${s.model}` : "Offline · rules";
    badge.title = s.mode === "model"
      ? "Plans are understood by a language model; numbers are always computed by code."
      : "No model available right now: plans are matched against the catalog rules.";
    badge.classList.toggle("live", s.mode === "model");
    if (!s.vision) {
      $("#whiteboard-note").textContent = s.mode === "model"
        ? "Image reading is off on this server: draw to think, then type your plan in the chat."
        : "Offline mode: the whiteboard and photos are not read. Type your plan in the chat.";
    }
    const sel = $("#course");
    s.courses.forEach((c) => {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = c.name;
      sel.appendChild(o);
    });
    await startSession("lim-sine");
  } catch (e) {
    addMessage(`The server is not responding: ${e.message}`, "buddy");
  }
}
// KaTeX is loaded with "defer": start once it is ready
document.addEventListener("DOMContentLoaded", boot);

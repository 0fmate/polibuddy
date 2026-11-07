/* PoliBuddy · demo interface (no frameworks; KaTeX renders every formula). */

const $ = (sel) => document.querySelector(sel);
const stato = {
  sessione: null, fase: "attesa_piano", lavagnaSporca: false, modalita: "offline",
  esercizio: null, allegati: [], corsoDocente: "analisi1", ultimaEsecuzione: null,
};

const UMORE = {
  default: "Ready to try your idea",
  studio: "Studying your plan…",
  riflessione: "Hmm… something doesn't add up",
  riprova: "Try again, you're close",
  idea: "I've got a hint for you",
  successo: "You did it!",
};
const STATO_ARGOMENTO = {
  da_fare: { img: "default", testo: "to do" },
  in_corso: { img: "riprova", testo: "in progress" },
  con_aiuto: { img: "idea", testo: "solved with help" },
  da_solo: { img: "successo", testo: "solved on your own" },
};

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
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
const FUNZ = /^(sin|cos|tan|sqrt|exp|ln|lim)(\(|$)/i;
function tokenForte(w) {
  if (/^(m\/s\^?2?|km\/h|m\/s²)$/i.test(w)) return false; // units stay text
  return /[\^\/=≈*·]/.test(w) || FUNZ.test(w) || /^\d+[xtvghn]$/.test(w) || /^[a-z]0$/.test(w) || /^[=≈+\-−*·\/^]+$/.test(w);
}
function tokenDebole(w) {
  return /^\(?-?\d+(\.\d+)?\)?$/.test(w) || /^[xtvghns]$/.test(w) || /^[()+\-−]$/.test(w) || /^\(?\d*[xtvghn]\)?$/.test(w);
}
function inLatex(span) {
  let s = span.replace(/≈/g, " \\approx ").replace(/[·*]/g, " \\cdot ").replace(/−/g, "-");
  s = s.replace(/\bsqrt\s*\(([^()]*)\)/gi, "\\sqrt{$1}");
  s = s.replace(/\b(sin|cos|tan|ln|exp)\b\s*/gi, (m, f) => `\\${f.toLowerCase()} `);
  // fractions first, so that (3x)^3/6 becomes \frac{(3x)^3}{6}
  const togli = (t) => (/^\([^()]*\)$/.test(t) ? t.slice(1, -1) : t);
  s = s.replace(/((?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?)\s*\/\s*((?:\([^()]*\)|[A-Za-z0-9_.]+)(?:\^(?:\([^()]*\)|-?[0-9a-z]+))?)/g,
    (m, a, b) => `\\frac{${togli(a)}}{${togli(b)}}`);
  s = s.replace(/\b([a-z])0\b/g, "$1_0");
  s = s.replace(/\^\(([^()]*)\)/g, "^{$1}").replace(/\^(-?[0-9a-z]+)/g, "^{$1}");
  return s;
}
function mathify(testo) {
  if (testo.includes("$")) return testo;
  testo = testo.replace(/²/g, "^2").replace(/³/g, "^3");
  const parole = testo.split(/(\s+)/);
  const pulisci = (w) => w.replace(/[,.;:?!]+$/, "");
  const forte = parole.map((w) => w.trim() && tokenForte(pulisci(w)));
  const debole = parole.map((w) => w.trim() && tokenDebole(pulisci(w)));
  const dentro = forte.slice();
  for (let giro = 0; giro < 2; giro++) {
    for (let i = 0; i < parole.length; i++) {
      if (!parole[i].trim() || dentro[i] || !debole[i]) continue;
      const vicino = (j) => j >= 0 && j < parole.length && dentro[j];
      let k = i - 1; while (k >= 0 && !parole[k].trim()) k--;
      let h = i + 1; while (h < parole.length && !parole[h].trim()) h++;
      const finePrima = k >= 0 && /[,.;:?!]$/.test(parole[k]);
      if ((vicino(k) && !finePrima) || (vicino(h) && !/[,.;:?!]$/.test(parole[i]))) dentro[i] = true;
    }
  }
  let out = "", buf = [];
  const svuota = () => {
    if (!buf.length) return;
    let span = buf.join("").trim();
    const coda = (span.match(/[,.;:?!]+$/) || [""])[0];
    span = span.slice(0, span.length - coda.length);
    // a formula cut in half ("v =") or a lone number stays plain text
    out += /^[a-z]?\s*[=≈]$|^-?\d+(\.\d+)?$/.test(span.trim()) ? span + coda : `$${inLatex(span)}$${coda}`;
    buf = [];
  };
  for (let i = 0; i < parole.length; i++) {
    if (dentro[i]) {
      buf.push(parole[i]);
      if (/[,.;:?!]$/.test(parole[i])) svuota();
    } else if (!parole[i].trim() && buf.length) {
      let h = i + 1; while (h < parole.length && !parole[h].trim()) h++;
      if (h < parole.length && dentro[h]) buf.push(parole[i]); else { svuota(); out += parole[i]; }
    } else { svuota(); out += parole[i]; }
  }
  svuota();
  return out;
}

/* ---------------- Views ---------------- */
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  const vista = t.dataset.view;
  $("#view-studente").hidden = vista !== "studente";
  $("#view-docente").hidden = vista !== "docente";
  if (vista === "docente") caricaDocente($("#corso").value);
  else preparaLavagna();
}));

/* ---------------- Student: exercise, mascot, progress ---------------- */
function renderEsercizio(es) {
  stato.esercizio = es;
  $("#es-corso").textContent = es.corso_nome;
  $("#es-tipo").textContent = es.tipo;
  $("#es-livello").textContent = `Level ${es.livello}`;
  const box = $("#es-formula");
  box.classList.toggle("testo", !es.latex);
  if (es.latex && window.katex) {
    try { window.katex.render(es.latex, box, { displayMode: true, throwOnError: false }); }
    catch (_) { box.textContent = es.testo; }
  } else {
    box.textContent = es.testo;
    renderMath(box);
  }
  $("#es-codice").hidden = !es.codice;
  $("#es-codice").textContent = es.codice || "";
  $("#corso").value = es.corso;
  $("#prog-corso").textContent = es.corso_nome;
}

function renderMascotte(umore) {
  const img = $("#mascotte");
  const src = `/brand/mascotte/${umore}.svg`;
  if (!img.src.endsWith(src)) {
    img.src = src;
    img.classList.remove("cambia");
    void img.offsetWidth;
    img.classList.add("cambia");
  }
  $("#umore").textContent = UMORE[umore] || "";
  $("#voce-mascotte").src = src;
}

function renderProgressi(lista) {
  const box = $("#progressi");
  box.innerHTML = "";
  lista.forEach((p) => {
    const info = STATO_ARGOMENTO[p.stato];
    const b = document.createElement("button");
    b.type = "button";
    b.className = `prog ${p.stato}${stato.esercizio && stato.esercizio.id === p.id ? " corrente" : ""}`;
    b.innerHTML = `<img alt=""><div><div class="prog-nome"></div><div class="prog-stato"></div></div>`;
    b.querySelector("img").src = `/brand/mascotte/${info.img}.svg`;
    b.querySelector(".prog-nome").textContent = p.titolo;
    b.querySelector(".prog-stato").textContent = `L${p.livello} · ${info.testo}`;
    b.title = `${p.titolo}: ${info.testo}`;
    b.addEventListener("click", () => avviaSessione(p.id));
    box.appendChild(b);
  });
}

function aggiungiMsg(testo, ruolo, file = [], opzioni = {}) {
  const div = document.createElement("div");
  div.className = `msg ${ruolo}`;
  if (opzioni.voce) {
    const tag = document.createElement("span");
    tag.className = "voce-tag";
    tag.textContent = "🎙 voice";
    div.appendChild(tag);
  }
  const corpo = document.createElement("span");
  corpo.textContent = ruolo.startsWith("studente") ? mathify(testo) : testo;
  div.appendChild(corpo);
  if (file.length) {
    const chips = document.createElement("div");
    chips.className = "file-chips";
    file.forEach((f) => chips.appendChild(chipFile(f, false)));
    div.appendChild(chips);
  }
  $("#messages").appendChild(div);
  if (!ruolo.includes("pensa")) renderMath(corpo);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}

function renderCorda(livello, max) {
  const box = $("#corda");
  box.innerHTML = "";
  for (let i = 1; i <= max; i++) {
    const d = document.createElement("i");
    if (i <= livello) d.className = "on";
    box.appendChild(d);
  }
}

function renderQuick() {
  const box = $("#quick");
  box.innerHTML = "";
  let scelte = [];
  if (stato.fase === "attesa_conferma") scelte = ["Yes, exactly", "No, wait"];
  else if (stato.fase === "attesa_piano") {
    if (stato.esercizio?.piano_demo) scelte.push(stato.esercizio.piano_demo);
    scelte.push("Just tell me the solution");
  }
  scelte.forEach((s) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = mathify(s);
    b.addEventListener("click", () => invia(s));
    box.appendChild(b);
    renderMath(b);
  });
}

function resetRisultati() {
  stato.ultimaEsecuzione = null;
  $("#risultati-vuoti").hidden = false;
  $("#risultati-body").hidden = true;
  $("#verdetto").hidden = true;
  $("#prossimo").hidden = true;
}

function applicaRisposta(r) {
  stato.sessione = r.sessione;
  stato.fase = r.stato;
  if (r.lavagna_letta) aggiungiMsg(`I read on the whiteboard: ${r.lavagna_letta}`, "letto");
  (r.allegati_letti || []).forEach((a) => {
    const div = aggiungiMsg(a.ok ? `I read ${a.nome}: ${a.sintesi}` : `${a.nome}: ${a.nota}`, "letto");
    if (!a.ok) div.classList.add("ko");
  });
  r.messaggi.forEach((m) => aggiungiMsg(m, "buddy"));
  renderMascotte(r.umore);
  renderCorda(r.livello_aiuto, r.livello_aiuto_max);
  renderProgressi(r.progressi || []);
  renderQuick();
  if (r.esecuzione) mostraRisultati(r.esecuzione);
  $("#prossimo").hidden = r.stato !== "risolto";
}

async function avviaSessione(esercizio, corso) {
  const r = await api("/api/sessione", { studente: $("#studente").value || "demo", esercizio, corso });
  $("#messages").innerHTML = "";
  resetRisultati();
  renderEsercizio(r.esercizio);
  applicaRisposta(r);
}

/* ---------------- Attachments (photos and documents) ---------------- */
const MAX_FILE = 8 * 1024 * 1024;

function chipFile(f, rimovibile) {
  const c = document.createElement("span");
  c.className = "file-chip";
  if (f.tipo.startsWith("image/")) {
    const img = document.createElement("img");
    img.src = f.dati;
    img.alt = "";
    c.appendChild(img);
  } else {
    c.append(f.nome.toLowerCase().endsWith(".pdf") ? "📄" : "📎");
  }
  const s = document.createElement("span");
  s.textContent = f.nome;
  c.appendChild(s);
  if (rimovibile) {
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.title = "Remove";
    x.addEventListener("click", () => {
      stato.allegati = stato.allegati.filter((a) => a !== f);
      renderAnteprima();
    });
    c.appendChild(x);
  }
  return c;
}

function renderAnteprima() {
  const box = $("#anteprima");
  box.innerHTML = "";
  stato.allegati.forEach((f) => box.appendChild(chipFile(f, true)));
  box.hidden = stato.allegati.length === 0;
}

$("#clip").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", async (e) => {
  for (const file of [...e.target.files].slice(0, 5)) {
    if (file.size > MAX_FILE) { aggiungiMsg(`${file.name} is too large (8 MB max).`, "letto ko"); continue; }
    const dati = await new Promise((ok) => {
      const fr = new FileReader();
      fr.onload = () => ok(fr.result);
      fr.readAsDataURL(file);
    });
    stato.allegati.push({ nome: file.name, tipo: file.type || "", dati });
  }
  e.target.value = "";
  renderAnteprima();
});

/* ---------------- Sending ---------------- */
async function invia(testo, opzioni = {}) {
  testo = (testo ?? $("#input").value).trim();
  // the whiteboard explains the plan; it is not needed to confirm it
  const allegaLavagna = $("#allega").checked && stato.lavagnaSporca && stato.fase !== "attesa_conferma";
  const file = opzioni.voce ? [] : stato.allegati;
  if (!testo && !allegaLavagna && !file.length) return null;
  aggiungiMsg(testo || (file.length ? "(sending you these files)" : "(sending you the whiteboard)"), "studente", file, opzioni);
  if (!opzioni.voce) {
    $("#input").value = "";
    stato.allegati = [];
    renderAnteprima();
  }
  const legge = (allegaLavagna || file.length) && stato.modalita === "modello";
  const attesa = aggiungiMsg(legge ? "PoliBuddy is reading…" : "PoliBuddy is thinking…", "buddy pensa");
  renderMascotte("studio");
  $("#invia").disabled = true;
  try {
    const r = await api("/api/messaggio", {
      sessione: stato.sessione, testo,
      lavagna: allegaLavagna ? $("#lavagna").toDataURL("image/png") : null,
      allegati: file,
    });
    attesa.remove();
    applicaRisposta(r);
    return r;
  } catch (e) {
    attesa.remove();
    aggiungiMsg(`Connection problem: ${e.message}`, "buddy");
    return null;
  } finally {
    $("#invia").disabled = false;
    if (!opzioni.voce) $("#input").focus();
  }
}

$("#composer").addEventListener("submit", (e) => { e.preventDefault(); invia(); });
$("#input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); invia(); }
});
$("#prossimo").addEventListener("click", async () => {
  const r = await api("/api/prossimo", { sessione: stato.sessione });
  $("#messages").innerHTML = "";
  resetRisultati();
  renderEsercizio(r.esercizio);
  applicaRisposta(r);
});
$("#studente").addEventListener("change", () => avviaSessione(null, $("#corso").value));
$("#corso").addEventListener("change", (e) => {
  if (!$("#view-docente").hidden) caricaDocente(e.target.value);
  avviaSessione(null, e.target.value);
});

/* ---------------- Voice conversation ---------------- */
const voce = {
  attiva: false, stream: null, recorder: null, ctx: null, analyser: null, pezzi: [],
  turni: [], inizio: 0, timer: null, riconoscitore: null, audio: null,
};

function voceStato(testo, parla = false) {
  $("#voce-stato").textContent = testo;
  $("#voce").classList.toggle("parla", parla);
}

function animaOnde(livello) {
  document.querySelectorAll("#voce-onde i").forEach((b, i) => {
    const h = 6 + Math.min(1, livello * (0.6 + 0.4 * Math.sin(Date.now() / 120 + i))) * 20;
    b.style.height = `${h}px`;
  });
}

function aggiungiTurno(chi, testo) {
  voce.turni.push({ chi, testo, t: Math.round((Date.now() - voce.inizio) / 1000) });
  $("#voce-ultimo").textContent = `${chi === "you" ? "You" : "PoliBuddy"}: ${testo.replace(/\$/g, "")}`;
}

async function avviaVoce() {
  if (voce.attiva) return;
  const usaServer = stato.modalita === "modello" && navigator.mediaDevices && window.MediaRecorder;
  const Riconoscitore = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!usaServer && !Riconoscitore) {
    aggiungiMsg("Voice is not available here: it needs the OpenAI key or a browser with speech recognition (Chrome, Edge).", "letto ko");
    return;
  }
  voce.attiva = true;
  voce.turni = [];
  voce.inizio = Date.now();
  voce.usaServer = usaServer;
  $("#voce").hidden = false;
  $("#mic").classList.add("attivo");
  try {
    if (usaServer) {
      voce.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      voce.ctx = new (window.AudioContext || window.webkitAudioContext)();
      voce.analyser = voce.ctx.createAnalyser();
      voce.analyser.fftSize = 1024;
      voce.ctx.createMediaStreamSource(voce.stream).connect(voce.analyser);
    }
    ascolta();
  } catch (e) {
    aggiungiMsg(`I can't use the microphone: ${e.message}`, "letto ko");
    chiudiVoce(false);
  }
}

function ascolta() {
  if (!voce.attiva) return;
  voceStato("Listening… explain your idea");
  if (!voce.usaServer) return ascoltaBrowser();

  voce.pezzi = [];
  const tipo = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  voce.recorder = new MediaRecorder(voce.stream, tipo ? { mimeType: tipo } : {});
  voce.recorder.ondataavailable = (e) => { if (e.data.size) voce.pezzi.push(e.data); };
  voce.recorder.onstop = () => elaboraAudio();
  voce.recorder.start(250);

  // simple voice-activity detection: stop after ~1.3 s of silence once the student has spoken
  const buf = new Uint8Array(voce.analyser.fftSize);
  let parlato = false, silenzioDa = Date.now();
  const inizio = Date.now();
  clearInterval(voce.timer);
  voce.timer = setInterval(() => {
    voce.analyser.getByteTimeDomainData(buf);
    let somma = 0;
    for (const v of buf) somma += ((v - 128) / 128) ** 2;
    const rms = Math.sqrt(somma / buf.length);
    animaOnde(rms * 12);
    if (rms > 0.035) { parlato = true; silenzioDa = Date.now(); }
    const fermo = Date.now() - silenzioDa;
    if ((parlato && fermo > 1300) || Date.now() - inizio > 30000) fineTurno();
  }, 80);
}

function fineTurno() {
  clearInterval(voce.timer);
  animaOnde(0);
  if (voce.recorder && voce.recorder.state === "recording") voce.recorder.stop();
  if (voce.riconoscitore) voce.riconoscitore.stop();
}

async function elaboraAudio() {
  if (!voce.attiva) return;
  const blob = new Blob(voce.pezzi, { type: voce.recorder.mimeType || "audio/webm" });
  if (blob.size < 2500) return ascolta();
  voceStato("Transcribing…");
  const dati = await new Promise((ok) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.readAsDataURL(blob); });
  try {
    const { testo } = await api("/api/voce/trascrivi", { audio: dati, tipo: blob.type });
    await turnoStudente(testo);
  } catch (e) {
    voceStato("I didn't catch that, try again");
    setTimeout(ascolta, 900);
  }
}

function ascoltaBrowser() {
  const Riconoscitore = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Riconoscitore();
  voce.riconoscitore = rec;
  rec.lang = "en-US";
  rec.interimResults = false;
  let detto = "";
  rec.onresult = (e) => { detto = [...e.results].map((r) => r[0].transcript).join(" "); };
  rec.onerror = () => {};
  rec.onend = () => {
    voce.riconoscitore = null;
    if (!voce.attiva) return;
    if (detto.trim()) turnoStudente(detto.trim()); else ascolta();
  };
  clearInterval(voce.timer);
  voce.timer = setInterval(() => animaOnde(Math.random() * 0.6), 120);
  rec.start();
}

async function turnoStudente(testo) {
  if (!voce.attiva) return;
  aggiungiTurno("you", testo);
  voceStato("PoliBuddy is thinking…");
  const r = await invia(testo, { voce: true });
  if (!r || !voce.attiva) return voce.attiva && ascolta();
  const risposta = r.messaggi.join(" ");
  aggiungiTurno("buddy", risposta);
  await parla(risposta);
  if (voce.attiva) ascolta();
}

function parlato(testo) {
  return testo.replace(/\$/g, "").replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "$1 over $2").replace(/\\[a-z]+/g, " ").replace(/[{}^_]/g, " ");
}

async function parla(testo) {
  voceStato("PoliBuddy is speaking…", true);
  clearInterval(voce.timer);
  voce.timer = setInterval(() => animaOnde(0.35 + Math.random() * 0.5), 110);
  try {
    if (voce.usaServer) {
      const res = await fetch("/api/voce/parla", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ testo }),
      });
      if (!res.ok) throw new Error("tts");
      const url = URL.createObjectURL(await res.blob());
      await new Promise((ok) => {
        voce.audio = new Audio(url);
        voce.audio.onended = ok;
        voce.audio.onerror = ok;
        voce.audio.play().catch(ok);
      });
      URL.revokeObjectURL(url);
    } else if (window.speechSynthesis) {
      await new Promise((ok) => {
        const u = new SpeechSynthesisUtterance(parlato(testo));
        u.lang = "en-US";
        u.onend = ok;
        u.onerror = ok;
        speechSynthesis.speak(u);
      });
    }
  } catch (_) { /* the text is in the chat anyway */ }
  clearInterval(voce.timer);
  animaOnde(0);
}

function chiudiVoce(conTrascrizione = true) {
  voce.attiva = false;
  clearInterval(voce.timer);
  if (voce.recorder && voce.recorder.state === "recording") { voce.recorder.onstop = null; voce.recorder.stop(); }
  if (voce.riconoscitore) { voce.riconoscitore.onend = null; voce.riconoscitore.abort(); }
  if (voce.audio) voce.audio.pause();
  if (window.speechSynthesis) speechSynthesis.cancel();
  if (voce.stream) voce.stream.getTracks().forEach((t) => t.stop());
  if (voce.ctx) voce.ctx.close();
  voce.stream = voce.ctx = voce.recorder = null;
  $("#voce").hidden = true;
  $("#mic").classList.remove("attivo");
  if (conTrascrizione && voce.turni.length) mostraTrascrizione();
}

function mostraTrascrizione() {
  const durata = Math.max(1, Math.round((Date.now() - voce.inizio) / 1000));
  const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const card = document.createElement("div");
  card.className = "trascrizione";
  card.innerHTML = `<div class="trascrizione-head"><div><strong>Voice conversation transcript</strong>
    <div class="muted small"></div></div><button type="button" class="link-btn">Download .txt</button></div><ol></ol>`;
  card.querySelector(".muted").textContent = `${mmss(durata)} · ${voce.turni.length} turns · ${stato.esercizio?.titolo || ""}`;
  const ol = card.querySelector("ol");
  voce.turni.forEach((t) => {
    const li = document.createElement("li");
    li.className = t.chi === "you" ? "tu" : "buddy";
    li.innerHTML = `<time></time><b></b> <span></span>`;
    li.querySelector("time").textContent = mmss(t.t);
    li.querySelector("b").textContent = t.chi === "you" ? "You:" : "PoliBuddy:";
    li.querySelector("span").textContent = t.chi === "you" ? mathify(t.testo) : t.testo;
    ol.appendChild(li);
  });
  const righe = [`PoliBuddy · voice conversation transcript`, `Exercise: ${stato.esercizio?.titolo || ""}`, `Duration: ${mmss(durata)}`, ""]
    .concat(voce.turni.map((t) => `[${mmss(t.t)}] ${t.chi === "you" ? "You" : "PoliBuddy"}: ${t.testo}`));
  card.querySelector("button").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([righe.join("\n")], { type: "text/plain" }));
    a.download = `polibuddy-transcript-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-")}.txt`;
    a.click();
  });
  $("#messages").appendChild(card);
  renderMath(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

$("#mic").addEventListener("click", () => (voce.attiva ? chiudiVoce() : avviaVoce()));
$("#voce-fine-turno").addEventListener("click", fineTurno);
$("#voce-chiudi").addEventListener("click", () => chiudiVoce());

/* ---------------- Results: table and chart ---------------- */
function mostraRisultati(ex) {
  stato.ultimaEsecuzione = ex;
  $("#risultati-vuoti").hidden = true;
  $("#risultati-body").hidden = false;
  const v = $("#verdetto");
  v.hidden = false;
  v.className = `verdict ${ex.torna ? "si" : "no"}`;
  v.textContent = ex.torna ? "It works!" : "Doesn't add up";
  $("#lab-previsto").textContent = ex.etichetta_previsto;
  $("#lab-tendenza").textContent = ex.etichetta_tendenza;
  $("#val-previsto").textContent = ex.previsto;
  $("#val-tendenza").textContent = "…";

  const thead = $("#tabella thead");
  thead.innerHTML = "";
  const trh = document.createElement("tr");
  ex.colonne.forEach((c) => { const th = document.createElement("th"); th.textContent = c; trh.appendChild(th); });
  thead.appendChild(trh);

  const tbody = $("#tabella tbody");
  tbody.innerHTML = "";
  const passo = Math.max(90, Math.min(380, 1600 / Math.max(ex.righe.length, 1)));
  ex.righe.forEach((riga, i) => {
    setTimeout(() => {
      const tr = document.createElement("tr");
      tr.className = `entra${i === ex.evidenzia ? " evidenzia" : ""}`;
      riga.forEach((c) => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
      tbody.appendChild(tr);
      tr.scrollIntoView({ block: "nearest" });
      if (i === ex.righe.length - 1) $("#val-tendenza").textContent = ex.tendenza;
    }, passo * i + 150);
  });
  if (!ex.righe.length) $("#val-tendenza").textContent = ex.tendenza;
  disegnaGrafico(ex.grafico, true);
}

const COLORE = { vero: "#073766", tuo: "#ff8a18", obiettivo: "#00a99b" };

function disegnaGrafico(g, anima) {
  const svg = $("#grafico");
  const W = 440, H = 270, m = { l: 48, r: 18, t: 18, b: 34 };
  const css = getComputedStyle(document.documentElement);
  const cLine = css.getPropertyValue("--line").trim();
  const cMuted = css.getPropertyValue("--muted").trim();

  const ys = [];
  g.serie.forEach((s) => s.punti.forEach((p) => { if (p[1] !== null) ys.push(p[1]); }));
  g.linee.forEach((l) => ys.push(l.y));
  if (g.marcatore && g.marcatore.y !== null) ys.push(g.marcatore.y);
  ys.push(0);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  const pad = (yMax - yMin) * 0.12 || 1;
  yMin -= pad; yMax += pad;
  const X = (x) => m.l + ((x - g.x_min) / (g.x_max - g.x_min)) * (W - m.l - m.r);
  const Y = (y) => m.t + (1 - (y - yMin) / (yMax - yMin)) * (H - m.t - m.b);
  const num = (v) => v.toLocaleString("en-US", { maximumFractionDigits: 2 });

  const percorso = (punti) => {
    let d = "", aperto = false;
    punti.forEach(([x, y]) => {
      if (y === null || y < yMin || y > yMax) { aperto = false; return; }
      d += `${aperto ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)} `;
      aperto = true;
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
  s += `<text x="${(m.l + W - m.r) / 2}" y="${H - 10}" text-anchor="middle" font-size="13" fill="${cMuted}">${g.asse_x}</text>`;

  g.linee.forEach((l) => {
    s += `<line x1="${m.l}" y1="${Y(l.y)}" x2="${W - m.r}" y2="${Y(l.y)}" stroke="${COLORE[l.ruolo]}" stroke-width="2.6" stroke-dasharray="7 6"/>`;
    s += `<text x="${W - m.r - 4}" y="${Y(l.y) - 7}" text-anchor="end" font-size="12.5" font-weight="700" fill="${COLORE[l.ruolo]}">${l.etichetta}</text>`;
  });
  g.serie.forEach((serie) => {
    const tratteggio = serie.ruolo === "tuo" ? ' stroke-dasharray="7 6"' : "";
    s += `<path class="curva ${serie.ruolo}" d="${percorso(serie.punti)}" fill="none" stroke="${COLORE[serie.ruolo]}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"${tratteggio}/>`;
    if (serie.punti_visibili) {
      serie.punti.forEach(([x, y]) => {
        if (y !== null) s += `<circle cx="${X(x)}" cy="${Y(y)}" r="3.6" fill="${COLORE[serie.ruolo]}"/>`;
      });
    }
  });
  const mk = g.marcatore;
  if (mk && mk.y !== null && mk.y >= yMin && mk.y <= yMax) {
    const c = COLORE[mk.ruolo];
    const destra = X(mk.x) > W * 0.62;
    s += `<circle cx="${X(mk.x)}" cy="${Y(mk.y)}" r="6.5" fill="#fff" stroke="${c}" stroke-width="3.2"/>`;
    s += `<text x="${X(mk.x) + (destra ? -12 : 12)}" y="${Y(mk.y) - 12}" text-anchor="${destra ? "end" : "start"}" font-size="15" font-weight="800" fill="${c}">${mk.testo}</text>`;
  }
  svg.innerHTML = s;

  const leg = $("#legenda");
  leg.innerHTML = "";
  [...g.serie, ...g.linee].forEach((el) => {
    if (!el.etichetta) return;
    const span = document.createElement("span");
    span.innerHTML = `<i style="background:${COLORE[el.ruolo]}"></i>`;
    span.append(el.etichetta);
    leg.appendChild(span);
  });

  if (anima) {
    svg.querySelectorAll("path.curva.vero").forEach((p) => {
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
const canvas = $("#lavagna");
const ctx = canvas.getContext("2d");
let penna = "ink", disegnando = false;

function preparaLavagna() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  const copia = stato.lavagnaSporca ? canvas.toDataURL() : null;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  if (copia) { const img = new Image(); img.onload = () => ctx.drawImage(img, 0, 0, w, h); img.src = copia; }
}
function posizione(e) {
  const r = canvas.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}
canvas.addEventListener("pointerdown", (e) => {
  disegnando = true;
  canvas.setPointerCapture(e.pointerId);
  const [x, y] = posizione(e);
  ctx.beginPath(); ctx.moveTo(x, y);
});
canvas.addEventListener("pointermove", (e) => {
  if (!disegnando) return;
  const [x, y] = posizione(e);
  ctx.lineCap = "round"; ctx.lineJoin = "round";
  if (penna === "eraser") { ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 22; }
  else { ctx.strokeStyle = penna === "accent" ? "#ff8a18" : "#073766"; ctx.lineWidth = 3; }
  ctx.lineTo(x, y); ctx.stroke();
  if (!stato.lavagnaSporca) { stato.lavagnaSporca = true; $("#allega").checked = true; }
});
["pointerup", "pointerleave", "pointercancel"].forEach((ev) => canvas.addEventListener(ev, () => { disegnando = false; }));
document.querySelectorAll("[data-pen]").forEach((b) => b.addEventListener("click", () => {
  penna = b.dataset.pen;
  document.querySelectorAll("[data-pen]").forEach((x) => x.classList.toggle("active", x === b));
}));
$("#pulisci").addEventListener("click", () => {
  stato.lavagnaSporca = false;
  $("#allega").checked = false;
  preparaLavagna();
});
window.addEventListener("resize", preparaLavagna);

/* ---------------- Teacher ---------------- */
const NOMI_ESITI = {
  da_solo: "found alone", dopo_domanda: "after a question", dopo_slide: "after the slide",
  con_spunto: "with a hint", non_risolto: "not solved",
};
const PILL = { ok: "on track", attenzione: "attention", nessun_dato: "no data", insufficiente: "not enough data" };

async function caricaDocente(corso) {
  stato.corsoDocente = corso || stato.corsoDocente;
  const d = await api(`/api/radar?corso=${encodeURIComponent(stato.corsoDocente)}`);

  const seg = $("#d-corsi");
  seg.innerHTML = "";
  d.corsi.forEach((c) => {
    const b = document.createElement("button");
    b.textContent = c.nome;
    b.className = c.id === d.corso ? "on" : "";
    b.addEventListener("click", () => caricaDocente(c.id));
    seg.appendChild(b);
  });

  $("#d-corso").textContent = d.corso_nome;
  const reali = d.sessioni_reali === 1 ? "1 real session" : `${d.sessioni_reali} real sessions`;
  $("#docente-nota").textContent = `Anonymous, aggregated data · for the demo it includes simulated sessions (${reali} from this demo).`;
  $("#privacy-testo").textContent =
    `The teacher only sees anonymous, aggregated data, never an individual student. Below ${d.soglia} sessions the data is not shown.`;
  $("#k-sessioni").textContent = d.sessioni_totali;
  $("#k-primo").textContent = `${d.primo_colpo_pct}%`;
  $("#k-solo").textContent = `${d.da_solo_pct}%`;
  $("#k-critico").textContent = d.critico ? `${d.critico.titolo} · ${d.critico.da_solo_pct}% alone` : "—";

  const lac = $("#lacune");
  lac.innerHTML = "";
  d.lacune.forEach((l) => {
    const div = document.createElement("div");
    div.className = "lacuna";
    div.innerHTML = `<div class="lacuna-nome"></div><div class="muted small"></div><div class="lacuna-barra"><span style="width:0%"></span></div>`;
    div.querySelector(".lacuna-nome").textContent = l.errore || l.titolo;
    div.querySelector(".muted").textContent = `${l.titolo}: found alone in ${l.da_solo_pct}% of ${l.n} sessions with a mistake`;
    lac.appendChild(div);
    renderMath(div);
    setTimeout(() => { div.querySelector(".lacuna-barra span").style.width = `${l.da_solo_pct}%`; }, 80);
  });

  const leg = $("#legenda-esiti");
  leg.innerHTML = "";
  d.esiti.forEach((e, i) => {
    const s = document.createElement("span");
    s.innerHTML = `<i style="background:var(--s${i + 1})"></i>`;
    s.append(NOMI_ESITI[e]);
    leg.appendChild(s);
  });

  const barre = $("#barre");
  barre.innerHTML = "";
  d.esercizi.forEach((es) => {
    const riga = document.createElement("div");
    riga.className = "barra-riga";
    const nome = document.createElement("div");
    nome.className = "barra-nome";
    nome.textContent = es.titolo;
    const sotto = document.createElement("div");
    sotto.className = "muted small";
    sotto.textContent = es.sufficiente ? `${es.tipo} · first try ${es.primo_colpo_pct}%` : es.tipo;
    nome.appendChild(sotto);
    riga.appendChild(nome);

    const centro = document.createElement("div");
    if (es.sufficiente) {
      centro.className = "barra";
      d.esiti.forEach((e, i) => {
        const span = document.createElement("span");
        span.style.width = "0%";
        span.style.background = `var(--s${i + 1})`;
        span.title = `${NOMI_ESITI[e]}: ${es.esiti_pct[e]}%`;
        centro.appendChild(span);
        setTimeout(() => { span.style.width = `${es.esiti_pct[e]}%`; }, 80);
      });
    } else {
      centro.className = "insuff";
      centro.textContent = `not enough data (fewer than ${d.soglia} sessions): hidden`;
    }
    riga.appendChild(centro);
    const n = document.createElement("div");
    n.className = "barra-n";
    n.textContent = `${es.n} sessions`;
    riga.appendChild(n);
    barre.appendChild(riga);
  });

  const demo = await api(`/api/crash-test/demo?corso=${encodeURIComponent(d.corso)}`);
  $("#domande").value = demo.domande.join("\n");
  $("#crash-report").innerHTML = "";
}

$("#crash-btn").addEventListener("click", async () => {
  const { report } = await api("/api/crash-test", { domande: $("#domande").value.split("\n") });
  const box = $("#crash-report");
  box.innerHTML = "";
  report.forEach((v) => {
    const div = document.createElement("div");
    div.className = "crash-voce";
    div.innerHTML = `<div class="q"><span class="pill"></span><span class="t"></span></div><div class="muted small c"></div><div class="small r"></div>`;
    div.querySelector(".pill").className = `pill ${v.stato}`;
    div.querySelector(".pill").textContent = PILL[v.stato] || v.stato;
    div.querySelector(".t").textContent = `${v.numero}. ${mathify(v.domanda)}`;
    div.querySelector(".c").textContent = v.concetti.length ? `Concepts: ${v.concetti.join(", ")}` : "";
    div.querySelector(".r").textContent = v.testo;
    box.appendChild(div);
    renderMath(div);
  });
});

/* ---------------- Start ---------------- */
async function avvio() {
  preparaLavagna();
  try {
    const s = await api("/api/stato");
    stato.modalita = s.modalita;
    const badge = $("#badge-modo");
    badge.textContent = s.modalita === "modello" ? `OpenAI · ${s.modello}` : "Offline · rules";
    badge.classList.toggle("live", s.modalita === "modello");
    if (s.modalita !== "modello") {
      $("#lavagna-nota").textContent =
        "Offline mode: the whiteboard and photos are not read. Add the OpenAI key to the .env file to enable them.";
    }
    const sel = $("#corso");
    s.corsi.forEach((c) => {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = c.nome;
      sel.appendChild(o);
    });
    await avviaSessione("lim-seno");
  } catch (e) {
    aggiungiMsg(`The server is not responding: ${e.message}`, "buddy");
  }
}
// KaTeX is loaded with "defer": start once it is ready
document.addEventListener("DOMContentLoaded", avvio);

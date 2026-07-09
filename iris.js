/* ============================================================================
   Iris · Asistente virtual de BrickBit
   Widget flotante autocontenido: avatar animado + chat + voz (navegador).
   Habla con el Worker de Cloudflare (/api/iris), que guarda la llave de
   Anthropic y puede buscar en la web. Se incluye en todas las páginas
   EXCEPTO BrickBit Financial. Uso: <script defer src="/iris.js"></script>
   ============================================================================ */
(function () {
  "use strict";
  if (window.__irisCargada) return;               // no duplicar
  window.__irisCargada = true;

  var API = "https://brickbit-api.jose-delgado-enp.workers.dev/api/iris";
  var AVATAR = "/assets/iris-avatar.png";          // sube esta imagen a assets/
  var MAX_TURNOS = 40;                             // tope suave por sesión (costo)
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- estilos ---------- */
  var css = `
  #iris-fab{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:62px;height:62px;border:none;
    border-radius:50%;cursor:grab;background:radial-gradient(circle at 35% 30%,#57c389,#1a7d50 70%);
    box-shadow:0 12px 30px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;padding:0;
    transition:transform .2s;touch-action:none}
  #iris-fab.iris-dragging{cursor:grabbing;transition:none}
  #iris-fab:hover{transform:scale(1.06)}
  #iris-fab .ring{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(205,242,90,.7);
    animation:iris-pulse 2.4s ease-out infinite}
  @keyframes iris-pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.7);opacity:0}}
  #iris-fab .lbl{position:absolute;right:70px;background:#1d1713;color:#f5ede3;font:600 12px/1 'Hanken Grotesk',system-ui,sans-serif;
    padding:8px 12px;border-radius:999px;white-space:nowrap;box-shadow:0 8px 20px rgba(0,0,0,.4);opacity:0;transform:translateX(8px);
    transition:.2s;pointer-events:none;border:1px solid rgba(245,237,227,.15)}
  #iris-fab:hover .lbl{opacity:1;transform:translateX(0)}
  .iris-orb{width:100%;height:100%}
  .iris-eye{transform-origin:center;animation:iris-blink 5s infinite}
  @keyframes iris-blink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
  .iris-av-img{width:100%;height:100%;object-fit:cover;border-radius:50%;display:block}

  #iris-panel{position:fixed;right:20px;bottom:20px;z-index:2147483001;width:370px;max-width:calc(100vw - 24px);
    height:560px;max-height:calc(100vh - 24px);background:#14100c;border:1px solid rgba(245,237,227,.14);
    border-radius:20px;box-shadow:0 24px 60px rgba(0,0,0,.55);display:none;flex-direction:column;overflow:hidden;
    font-family:'Hanken Grotesk',system-ui,-apple-system,sans-serif;color:#f5ede3}
  #iris-panel.on{display:flex;animation:iris-in .22s ease}
  @keyframes iris-in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
  .iris-head{display:flex;align-items:center;gap:11px;padding:14px 14px;background:rgba(26,125,80,.14);
    border-bottom:1px solid rgba(245,237,227,.12)}
  .iris-head .av{width:38px;height:38px;flex:none}
  .iris-head h4{margin:0;font-family:'Fraunces',Georgia,serif;font-weight:600;font-size:16px}
  .iris-head .st{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#a89a8c}
  .iris-head .sp{flex:1}
  .iris-icon{background:none;border:none;color:#a89a8c;cursor:pointer;font-size:17px;padding:6px;border-radius:8px;line-height:1}
  .iris-icon:hover{color:#f5ede3;background:rgba(245,237,227,.08)}
  .iris-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
  .iris-msg{max-width:85%;padding:10px 13px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}
  .iris-msg.u{align-self:flex-end;background:#1a7d50;color:#fff;border-bottom-right-radius:4px}
  .iris-msg.a{align-self:flex-start;background:#241c17;border:1px solid rgba(245,237,227,.1);border-bottom-left-radius:4px}
  .iris-msg.a a{color:#cdf25a}
  .iris-typing{align-self:flex-start;display:flex;gap:4px;padding:12px 14px;background:#241c17;border-radius:14px}
  .iris-typing i{width:7px;height:7px;border-radius:50%;background:#57c389;animation:iris-dot 1.2s infinite}
  .iris-typing i:nth-child(2){animation-delay:.2s}.iris-typing i:nth-child(3){animation-delay:.4s}
  @keyframes iris-dot{0%,60%,100%{opacity:.3;transform:translateY(0)}30%{opacity:1;transform:translateY(-4px)}}
  .iris-sug{display:flex;flex-wrap:wrap;gap:7px;padding:0 16px 6px}
  .iris-sug button{background:rgba(245,237,227,.05);border:1px solid rgba(245,237,227,.15);color:#d8ccbd;
    font:500 12px/1.2 inherit;padding:8px 11px;border-radius:999px;cursor:pointer;text-align:left}
  .iris-sug button:hover{border-color:#57c389;color:#f5ede3}
  .iris-foot{display:flex;align-items:center;gap:8px;padding:11px 12px;border-top:1px solid rgba(245,237,227,.12)}
  .iris-foot input{flex:1;background:#1d1713;border:1px solid rgba(245,237,227,.16);color:#f5ede3;border-radius:999px;
    padding:11px 14px;font:14px inherit;outline:none}
  .iris-foot input:focus{border-color:#57c389}
  .iris-foot button{flex:none;width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;font-size:16px;
    display:flex;align-items:center;justify-content:center}
  .iris-mic{background:#241c17;color:#f5ede3;border:1px solid rgba(245,237,227,.16)!important}
  .iris-mic.rec{background:#e06d5a;color:#fff;animation:iris-rec 1s infinite}
  @keyframes iris-rec{50%{opacity:.6}}
  .iris-send{background:#1a7d50;color:#fff}
  .iris-send:hover{background:#57c389}
  .iris-disc{font-size:10px;color:#7d7266;text-align:center;padding:0 12px 10px}
  ${reduce ? "#iris-fab .ring,.iris-eye,.iris-typing i{animation:none!important}" : ""}
  `;
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  /* ---------- avatar ----------
     Usa la imagen de Iris (/assets/iris-avatar.png). Si aún no existe,
     onerror cambia al orbe SVG animado como respaldo. */
  function orb(cls) {
    return '<svg class="' + cls + '" viewBox="0 0 48 48" aria-hidden="true">' +
      '<defs><radialGradient id="ig" cx="35%" cy="30%"><stop offset="0" stop-color="#cdf25a"/>' +
      '<stop offset="55%" stop-color="#57c389"/><stop offset="100%" stop-color="#0c4a30"/></radialGradient></defs>' +
      '<circle cx="24" cy="24" r="21" fill="url(#ig)"/>' +
      '<g fill="#0f130a"><ellipse class="iris-eye" cx="18" cy="22" rx="2.4" ry="3.2"/>' +
      '<ellipse class="iris-eye" cx="30" cy="22" rx="2.4" ry="3.2"/></g>' +
      '<path d="M17 30 Q24 35 31 30" fill="none" stroke="#0f130a" stroke-width="2" stroke-linecap="round"/></svg>';
  }
  function avatar(cls) {
    return '<img class="' + cls + ' iris-av-img" src="' + AVATAR + '" alt="Iris" ' +
      'onerror="this.outerHTML=window.__irisOrb(\'' + cls + '\')">';
  }
  window.__irisOrb = orb;   // accesible desde el onerror del <img>

  /* ---------- FAB ---------- */
  var fab = document.createElement("button");
  fab.id = "iris-fab";
  fab.setAttribute("aria-label", "Abrir a Iris, asistente de BrickBit");
  fab.innerHTML = (reduce ? "" : '<span class="ring"></span>') + avatar("iris-orb") +
    '<span class="lbl">Pregúntale a Iris</span>';
  document.body.appendChild(fab);

  /* ---------- panel ---------- */
  var panel = document.createElement("div");
  panel.id = "iris-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Iris, asistente de BrickBit");
  panel.innerHTML =
    '<div class="iris-head">' + avatar("av") +
      '<div><h4>Iris</h4><div class="st">Asistente de BrickBit</div></div><div class="sp"></div>' +
      '<button class="iris-icon" id="iris-mute" title="Activar/silenciar voz" aria-label="Voz">🔊</button>' +
      '<button class="iris-icon" id="iris-close" title="Cerrar" aria-label="Cerrar">✕</button>' +
    '</div>' +
    '<div class="iris-body" id="iris-body"></div>' +
    '<div class="iris-sug" id="iris-sug"></div>' +
    '<div class="iris-foot">' +
      '<button class="iris-mic" id="iris-mic" title="Hablar" aria-label="Hablar por voz">🎤</button>' +
      '<input id="iris-in" type="text" autocomplete="off" placeholder="Escribe o pulsa el micrófono…" aria-label="Tu mensaje">' +
      '<button class="iris-send" id="iris-send" title="Enviar" aria-label="Enviar">➤</button>' +
    '</div>' +
    '<div class="iris-disc">Iris puede equivocarse. Las proyecciones de BrickBit son simuladas, no asesoría.</div>';
  document.body.appendChild(panel);

  var body = panel.querySelector("#iris-body");
  var input = panel.querySelector("#iris-in");
  var sug = panel.querySelector("#iris-sug");
  var micBtn = panel.querySelector("#iris-mic");
  var muteBtn = panel.querySelector("#iris-mute");

  var historial = [];          // {role, content} para el backend
  var pensando = false;
  var vozActiva = true;        // Iris habla las respuestas
  var abierto = false;

  var SUGERENCIAS = [
    "¿Qué es BrickBit?",
    "¿Qué herramienta uso para analizar una inversión?",
    "¿Qué significan los colores del mapa de morfogénesis?",
    "¿En qué ciudades hay datos a nivel calle?"
  ];

  function pintarSugerencias() {
    sug.innerHTML = "";
    if (historial.length) return;                 // solo al inicio
    SUGERENCIAS.forEach(function (s) {
      var b = document.createElement("button");
      b.textContent = s;
      b.addEventListener("click", function () { enviar(s); });
      sug.appendChild(b);
    });
  }

  function escapar(t) {
    return t.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // enlaces markdown [txt](url) y URLs sueltas → <a>
  function formato(t) {
    var h = escapar(t);
    h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    h = h.replace(/(^|[\s(])(https?:\/\/[^\s)]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    return h;
  }

  function agregar(role, texto) {
    var d = document.createElement("div");
    d.className = "iris-msg " + (role === "user" ? "u" : "a");
    d.innerHTML = role === "user" ? escapar(texto) : formato(texto);
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
    return d;
  }

  function typing(on) {
    var ex = body.querySelector(".iris-typing");
    if (on && !ex) {
      var t = document.createElement("div");
      t.className = "iris-typing"; t.innerHTML = "<i></i><i></i><i></i>";
      body.appendChild(t); body.scrollTop = body.scrollHeight;
    } else if (!on && ex) { ex.remove(); }
  }

  // Limpia el texto para leerlo en voz alta: quita emojis, emoticonos y
  // símbolos que los motores TTS verbalizan feo (asterisco, almohadilla…).
  function limpiarParaVoz(t) {
    return t
      .replace(/\bhttps?:\/\/\S+/gi, " el enlace ")               // no deletrear URLs
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}\u{1F1E6}-\u{1F1FF}]/gu, "") // emojis/símbolos pictográficos
      .replace(/[:;=8x][-~^']?[)\](d p o 3 < > | \\ /]/gi, " ")   // emoticonos ASCII :) ;) :D :P
      .replace(/<3/g, " ")
      .replace(/[*_#`~|•·▪◦→←⟶⟵»«▸●■◆✓✕↗↘⌄–—]+/g, " ")           // markdown/símbolos
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  var vozIris = null;
  function elegirVoz() {
    if (!("speechSynthesis" in window)) return null;
    var vs = speechSynthesis.getVoices() || [];
    if (!vs.length) return null;
    var fem = /paulina|m[oó]nica|female|mujer|helena|laura|elena|sabina|marisol|luciana|camila|valentina|catalina|isabel|ang[eé]lica|google espa/i;
    var masc = /jorge|diego|carlos|juan|miguel|male|hombre|pablo|enrique|roberto/i;
    function puntua(v) {
      var s = 0, L = (v.lang || "").toLowerCase(), N = (v.name || "").toLowerCase();
      if (L.indexOf("es-mx") === 0 || L.indexOf("es_mx") === 0) s += 4;
      else if (L.indexOf("es-us") === 0) s += 3;
      else if (L.indexOf("es") === 0) s += 2;
      if (fem.test(N)) s += 3;
      if (masc.test(N)) s -= 6;                    // evita voces masculinas
      return s;
    }
    var cands = vs.filter(function (v) { return /^es/i.test(v.lang); });
    if (!cands.length) cands = vs;
    cands.sort(function (a, b) { return puntua(b) - puntua(a); });
    return cands[0] || null;
  }

  function hablar(texto) {
    if (!vozActiva || !("speechSynthesis" in window)) return;
    var limpio = limpiarParaVoz(texto);
    if (!limpio) return;
    try {
      speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(limpio.slice(0, 600));
      u.lang = "es-MX"; u.rate = 1.0; u.pitch = 1.15;     // pitch alto = timbre más femenino
      if (!vozIris) vozIris = elegirVoz();
      if (vozIris) u.voice = vozIris;
      speechSynthesis.speak(u);
    } catch (e) { /* silencioso */ }
  }

  async function enviar(texto) {
    texto = (texto || input.value || "").trim();
    if (!texto || pensando) return;
    if (historial.filter(function (m) { return m.role === "user"; }).length >= MAX_TURNOS) {
      agregar("assistant", "Hemos platicado bastante 😊. Recarga la página para seguir conversando con Iris.");
      return;
    }
    input.value = "";
    sug.innerHTML = "";
    agregar("user", texto);
    historial.push({ role: "user", content: texto });
    pensando = true; typing(true);
    try {
      var r = await fetch(API, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: historial })
      });
      var data = await r.json().catch(function () { return {}; });
      typing(false);
      var resp = (data && data.text) ? data.text
        : "Ahora mismo no puedo responder. Intenta de nuevo en un momento.";
      agregar("assistant", resp);
      historial.push({ role: "assistant", content: resp });
      hablar(resp);
    } catch (e) {
      typing(false);
      agregar("assistant", "No pude conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.");
    } finally {
      pensando = false;
    }
  }

  /* ---------- voz: reconocimiento (hablar) ---------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec = null;
  if (SR) {
    rec = new SR(); rec.lang = "es-MX"; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.addEventListener("result", function (e) {
      var t = e.results[0][0].transcript;
      input.value = t; enviar(t);
    });
    rec.addEventListener("end", function () { micBtn.classList.remove("rec"); });
    rec.addEventListener("error", function () { micBtn.classList.remove("rec"); });
    micBtn.addEventListener("click", function () {
      if (micBtn.classList.contains("rec")) { rec.stop(); return; }
      try { speechSynthesis && speechSynthesis.cancel(); micBtn.classList.add("rec"); rec.start(); }
      catch (e) { micBtn.classList.remove("rec"); }
    });
  } else {
    micBtn.style.display = "none";                 // navegador sin reconocimiento de voz
  }

  /* ---------- controles ---------- */
  function abrir() {
    abierto = true; panel.classList.add("on"); fab.style.display = "none";
    if (!historial.length && !body.children.length) {
      agregar("assistant", "¡Hola! Soy Iris, tu asistente de BrickBit 🧬. Puedo explicarte las herramientas, ayudarte a entender los mapas o buscar información. ¿En qué te ayudo?");
      pintarSugerencias();
    }
    setTimeout(function () { input.focus(); }, 100);
  }
  function cerrar() { abierto = false; panel.classList.remove("on"); fab.style.display = "flex";
    if ("speechSynthesis" in window) speechSynthesis.cancel(); }

  /* ---- Iris arrastrable (para que no estorbe la navegación) ---- */
  (function () {
    var dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;
    try {
      var saved = JSON.parse(localStorage.getItem("iris_fab_pos") || "null");
      if (saved && typeof saved.left === "number") {
        fab.style.left = saved.left + "px"; fab.style.top = saved.top + "px";
        fab.style.right = "auto"; fab.style.bottom = "auto";
      }
    } catch (e) {}
    function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
    fab.addEventListener("pointerdown", function (e) {
      dragging = true; moved = false;
      var r = fab.getBoundingClientRect(); ox = r.left; oy = r.top; sx = e.clientX; sy = e.clientY;
      try { fab.setPointerCapture(e.pointerId); } catch (er) {}
    });
    fab.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 5) return;
      moved = true; fab.classList.add("iris-dragging");
      var w = fab.offsetWidth, h = fab.offsetHeight;
      fab.style.left = clamp(ox + dx, 4, window.innerWidth - w - 4) + "px";
      fab.style.top = clamp(oy + dy, 4, window.innerHeight - h - 4) + "px";
      fab.style.right = "auto"; fab.style.bottom = "auto";
    });
    function end() {
      if (!dragging) return; dragging = false; fab.classList.remove("iris-dragging");
      if (moved) {
        var r = fab.getBoundingClientRect();
        try { localStorage.setItem("iris_fab_pos", JSON.stringify({ left: Math.round(r.left), top: Math.round(r.top) })); } catch (e) {}
      }
    }
    fab.addEventListener("pointerup", end);
    fab.addEventListener("pointercancel", end);
    // abrir SÓLO si fue clic (no arrastre)
    fab.addEventListener("click", function (e) {
      if (moved) { e.preventDefault(); e.stopPropagation(); return; }
      abrir();
    });
  })();
  panel.querySelector("#iris-close").addEventListener("click", cerrar);
  panel.querySelector("#iris-send").addEventListener("click", function () { enviar(); });
  input.addEventListener("keydown", function (e) { if (e.key === "Enter") enviar(); });
  muteBtn.addEventListener("click", function () {
    vozActiva = !vozActiva; muteBtn.textContent = vozActiva ? "🔊" : "🔇";
    if (!vozActiva && "speechSynthesis" in window) speechSynthesis.cancel();
  });
  // precargar voces y refrescar la elección cuando el navegador las tenga
  if ("speechSynthesis" in window) {
    try {
      vozIris = elegirVoz();
      speechSynthesis.onvoiceschanged = function () { vozIris = elegirVoz(); };
    } catch (e) {}
  }
})();

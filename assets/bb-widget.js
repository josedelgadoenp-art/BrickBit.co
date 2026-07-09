/**
 * BrickBit Score — widget embebible para socios (portales, inmobiliarias, medios).
 * Uso: coloca donde quieras el badge:
 *   <script src="https://brickbit.co/assets/bb-widget.js" data-zona="Querétaro"></script>
 * Lee la zona de data-zona, consulta la API pública y pinta un badge con marca.
 */
(function () {
  var API = "https://brickbit-api.jose-delgado-enp.workers.dev";
  var me = document.currentScript;
  var zona = me && me.getAttribute("data-zona");
  var mount = document.createElement("span");
  if (me && me.parentNode) me.parentNode.insertBefore(mount, me.nextSibling);
  if (!zona) return;
  fetch(API + "/api/score?zona=" + encodeURIComponent(zona))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d || d.error) { mount.style.display = "none"; return; }
      var col = d.score >= 80 ? "#57c389" : d.score >= 65 ? "#a9d23f" : d.score >= 50 ? "#F5C277" : "#e06d5a";
      mount.innerHTML =
        '<a href="https://brickbit.co/mapa.html" target="_blank" rel="noopener" ' +
        'style="display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-family:system-ui,-apple-system,sans-serif;' +
        'background:#100c0a;color:#f5ede3;border:1px solid rgba(245,237,227,.18);border-radius:12px;padding:9px 13px;line-height:1.25">' +
          '<span style="font-family:Georgia,serif;font-weight:700;color:' + col + ';font-size:20px">' + d.score + '</span>' +
          '<span style="font-size:13px;font-weight:700">BrickBit Score <span style="color:' + col + '">' + d.grade + '</span>' +
            '<span style="display:block;font-size:11px;font-weight:400;color:#a89a8c">' + d.zona + ' · +' + d.valorFuturo3a + '% a 3 años</span></span>' +
          '<span style="margin-left:4px;font-size:10px;color:#a89a8c">brickbit.co ↗</span>' +
        '</a>';
    })
    .catch(function () { mount.style.display = "none"; });
})();

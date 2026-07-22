/* =============================================================================
   BrickBit · edificio3d.js — Constructor 3D COMPARTIDO del edificio
   Una sola implementación para el Creador de planos, el Gemelo Digital (visor
   y simulador 4D) y el Comparador. Antes vivían 4 copias del mismo código y un
   bug (muros espejeados respecto a la losa) tuvo que corregirse 4 veces.

   Convención de ejes (¡respetarla!): la losa se extruye en XY y se gira con
   rotateX(-π/2), lo que mapea y_plano → Z_mundo = -(y - cy). Por eso muros,
   columnas y muebles usan Z = cy - y (negado) y rotación +atan2(dy, dx).
   Norte del plano = -Z del mundo (lo usa el estudio solar).

   Uso (desde un <script type="module"> que ya importó THREE):
     const group = window.bbEdificio(THREE, geometria, {
       mats: { slab, wallP, wallC, col, edge },   // materiales del sitio
       group,                                     // opcional: THREE.Group destino
       tagWalls: true,                            // opcional: userData.wall (texturizar)
     });
============================================================================= */
window.bbEdificio = function (THREE, g, opts) {
  opts = opts || {};
  const M = opts.mats;
  const group = opts.group || new THREE.Group();
  const h = g.alturaEntrepisoM, slabT = 0.15, wallT = 0.15;
  const cx = g.anchoM / 2, cy = g.fondoM / 2;

  const shape = new THREE.Shape();
  (g.footprint || []).forEach((p, i) =>
    i === 0 ? shape.moveTo(p.x - cx, p.y - cy) : shape.lineTo(p.x - cx, p.y - cy));
  shape.closePath();

  for (let lvl = 0; lvl <= g.niveles; lvl++) {
    const slabGeo = new THREE.ExtrudeGeometry(shape, { depth: slabT, bevelEnabled: false });
    slabGeo.rotateX(-Math.PI / 2);
    const slab = new THREE.Mesh(slabGeo, M.slab);
    slab.position.y = lvl * h;
    slab.castShadow = slab.receiveShadow = true;
    group.add(slab);
    group.add(new THREE.LineSegments(new THREE.EdgesGeometry(slabGeo), M.edge).translateY(lvl * h));
    if (lvl === g.niveles) break;

    for (const w of (g.muros || [])) {
      const dx = w.x2 - w.x1, dy = w.y2 - w.y1;
      const len = Math.hypot(dx, dy);
      if (len < 0.05) continue;
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(len, h - slabT, wallT), w.carga ? M.wallC : M.wallP);
      mesh.position.set((w.x1 + w.x2) / 2 - cx, lvl * h + slabT + (h - slabT) / 2, cy - (w.y1 + w.y2) / 2);
      mesh.rotation.y = Math.atan2(dy, dx);
      mesh.castShadow = mesh.receiveShadow = true;
      if (opts.tagWalls) { mesh.userData.wall = true; mesh.userData.wlen = len; mesh.userData.wh = h - slabT; }
      group.add(mesh);
    }
    for (const c of (g.columnas || [])) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.3, h, 0.3), M.col);
      mesh.position.set(c.x - cx, lvl * h + h / 2, cy - c.y);
      mesh.castShadow = true;
      group.add(mesh);
    }
  }
  return group;
};

/* =============================================================================
   Corte de sección SÓLIDO (tapa con stencil): al rebanar el edificio, la cara
   del corte se rellena con un plano de "concreto" en vez de ver cascarones
   huecos — el look casa de muñecas real (patrón webgl_clipping_stencil).

   Uso:
     const cap = window.bbSeccionCap(THREE, scene, buildingGroup, plane, color);
     // al mover el corte: cap.update(plane)   ·   al quitarlo: cap.dispose()
============================================================================= */
window.bbSeccionCap = function (THREE, scene, target, plane, color) {
  const grupo = new THREE.Group(); grupo.name = 'bbCapGroup';
  // Máscara de stencil: caras traseras incrementan, delanteras decrementan.
  const back = new THREE.MeshBasicMaterial({
    depthWrite: false, depthTest: false, colorWrite: false,
    stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc,
    side: THREE.BackSide, stencilFail: THREE.IncrementWrapStencilOp,
    stencilZFail: THREE.IncrementWrapStencilOp, stencilZPass: THREE.IncrementWrapStencilOp,
    clippingPlanes: [plane],
  });
  const front = new THREE.MeshBasicMaterial({
    depthWrite: false, depthTest: false, colorWrite: false,
    stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc,
    side: THREE.FrontSide, stencilFail: THREE.DecrementWrapStencilOp,
    stencilZFail: THREE.DecrementWrapStencilOp, stencilZPass: THREE.DecrementWrapStencilOp,
    clippingPlanes: [plane],
  });
  target.updateMatrixWorld(true);
  target.traverse((o) => {
    if (!o.isMesh || o.userData.env) return;
    const a = new THREE.Mesh(o.geometry, back);
    const b = new THREE.Mesh(o.geometry, front);
    a.matrixAutoUpdate = b.matrixAutoUpdate = false;
    a.matrix.copy(o.matrixWorld); b.matrix.copy(o.matrixWorld);
    a.renderOrder = b.renderOrder = 1;
    grupo.add(a); grupo.add(b);
  });
  // La tapa: se pinta solo donde el stencil quedó ≠ 0 (interior cortado).
  const capMat = new THREE.MeshStandardMaterial({
    color: color || 0x8f8779, metalness: 0.05, roughness: 0.9,
    stencilWrite: true, stencilRef: 0, stencilFunc: THREE.NotEqualStencilFunc,
    stencilFail: THREE.ReplaceStencilOp, stencilZFail: THREE.ReplaceStencilOp,
    stencilZPass: THREE.ReplaceStencilOp,
  });
  const cap = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), capMat);
  cap.renderOrder = 2;
  cap.onAfterRender = (renderer) => renderer.clearStencil();
  grupo.add(cap);
  scene.add(grupo);

  function update(pl) {
    // orienta la tapa sobre el plano de corte (normal hacia el lado visible)
    const n = pl.normal.clone();
    cap.position.copy(n).multiplyScalar(-pl.constant);
    cap.lookAt(cap.position.clone().sub(n));
  }
  update(plane);
  return {
    update,
    dispose() {
      scene.remove(grupo);
      grupo.traverse((o) => { if (o.isMesh && o.material !== capMat) o.material = null; });
      back.dispose(); front.dispose(); capMat.dispose(); cap.geometry.dispose();
    },
  };
};

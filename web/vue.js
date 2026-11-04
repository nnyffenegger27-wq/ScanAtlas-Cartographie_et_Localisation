// Toile cartographique commune au direct et à la carte : repère métrique, grille, déplacement et zoom.
const PAS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50];

export function couleurs() {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return { fond: v('--carte-fond'), grille: v('--grille'), forte: v('--grille-forte'), point: v('--point'), accent: v('--accent'),
           alerte: v('--alerte'), danger: v('--danger'), ok: v('--ok'), texte: v('--encre-3'), surface: v('--surface'), encre: v('--encre') };
}

export class Vue {
  constructor(toile, dessiner) {
    this.toile = toile; this.ctx = toile.getContext('2d'); this.dessiner = dessiner;
    this.cx = 0; this.cy = 0; this.e = 70;           // centre (m) et échelle (pixels par mètre)
    this.largeur = 0; this.hauteur = 0; this.dpr = 1;
    this.interception = null;                         // (phase, évènement, monde) → true si l'outil prend le geste
    this.surDeplacement = null;                       // appelé quand l'utilisateur déplace ou zoome la vue
    this.surSurvol = null;
    this.attente = false;
    new ResizeObserver(() => this.redimensionner()).observe(toile);
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => this.demander());
    this.brancher();
    this.redimensionner();
  }

  redimensionner() {
    const r = this.toile.getBoundingClientRect();
    this.dpr = window.devicePixelRatio || 1;
    this.largeur = r.width; this.hauteur = r.height;
    this.toile.width = Math.max(1, Math.round(r.width * this.dpr));
    this.toile.height = Math.max(1, Math.round(r.height * this.dpr));
    this.demander();
  }

  versEcran(x, y) { return [this.largeur / 2 + (x - this.cx) * this.e, this.hauteur / 2 - (y - this.cy) * this.e]; }
  versMonde(px, py) { return [this.cx + (px - this.largeur / 2) / this.e, this.cy - (py - this.hauteur / 2) / this.e]; }

  centrer(x, y) { this.cx = x; this.cy = y; this.demander(); }
  zoomer(facteur, px = this.largeur / 2, py = this.hauteur / 2) {
    const [mx, my] = this.versMonde(px, py);
    this.e = Math.max(4, Math.min(2000, this.e * facteur));
    this.cx = mx - (px - this.largeur / 2) / this.e; this.cy = my + (py - this.hauteur / 2) / this.e;
    this.demander();
  }
  ajuster(minx, miny, maxx, maxy, marge = 80) {
    const w = Math.max(maxx - minx, 1), h = Math.max(maxy - miny, 1);
    this.e = Math.max(4, Math.min((this.largeur - 2 * marge) / w, (this.hauteur - 2 * marge) / h, 400));
    this.cx = (minx + maxx) / 2; this.cy = (miny + maxy) / 2;
    this.demander();
  }

  brancher() {
    const t = this.toile; const pointeurs = new Map(); let pince = null; let glisse = null;
    const pos = (e) => { const r = t.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    t.addEventListener('pointerdown', (e) => {
      t.setPointerCapture(e.pointerId); pointeurs.set(e.pointerId, pos(e));
      if (pointeurs.size === 2) { const [a, b] = [...pointeurs.values()]; pince = Math.hypot(a[0] - b[0], a[1] - b[1]); glisse = null; return; }
      const [px, py] = pos(e);
      if (this.interception && this.interception('debut', e, this.versMonde(px, py))) { glisse = { outil: true }; return; }
      glisse = { px, py, cx: this.cx, cy: this.cy }; t.style.cursor = 'grabbing';
    });
    t.addEventListener('pointermove', (e) => {
      const [px, py] = pos(e);
      if (this.surSurvol) this.surSurvol(this.versMonde(px, py));
      if (!pointeurs.has(e.pointerId)) return;
      pointeurs.set(e.pointerId, [px, py]);
      if (pointeurs.size === 2 && pince) {
        const [a, b] = [...pointeurs.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        this.zoomer(d / pince, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); pince = d;
        if (this.surDeplacement) this.surDeplacement(); return;
      }
      if (!glisse) return;
      if (glisse.outil) { this.interception('bouge', e, this.versMonde(px, py)); return; }
      this.cx = glisse.cx - (px - glisse.px) / this.e; this.cy = glisse.cy + (py - glisse.py) / this.e;
      if (this.surDeplacement) this.surDeplacement();
      this.demander();
    });
    const fin = (e) => {
      pointeurs.delete(e.pointerId); pince = null;
      if (glisse && glisse.outil) this.interception('fin', e, this.versMonde(...pos(e)));
      glisse = null; t.style.cursor = '';
    };
    t.addEventListener('pointerup', fin); t.addEventListener('pointercancel', fin);
    t.addEventListener('wheel', (e) => {
      e.preventDefault();
      const [px, py] = pos(e);
      this.zoomer(Math.exp(-e.deltaY * 0.0015), px, py);
      if (this.surDeplacement) this.surDeplacement();
    }, { passive: false });
  }

  demander() {
    if (this.attente) return;
    this.attente = true;
    requestAnimationFrame(() => { this.attente = false; this.rendre(); });
  }

  rendre() {
    const { ctx } = this; const c = couleurs();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = c.fond; ctx.fillRect(0, 0, this.largeur, this.hauteur);
    this.tracerGrille(c);
    ctx.save();
    this.dessiner(ctx, this, c);
    ctx.restore();
    this.tracerEchelle(c);
  }

  tracerGrille(c) {
    const { ctx } = this;
    const cible = 90 / this.e;                       // un trait principal tous les ~90 px
    const pas = PAS.find((p) => p >= cible) || PAS[PAS.length - 1];
    const sous = pas / 5;
    const [x0, y1] = this.versMonde(0, 0); const [x1, y0] = this.versMonde(this.largeur, this.hauteur);
    const trace = (p, couleur, largeur) => {
      ctx.strokeStyle = couleur; ctx.lineWidth = largeur; ctx.beginPath();
      for (let x = Math.floor(x0 / p) * p; x <= x1; x += p) { const [px] = this.versEcran(x, 0); ctx.moveTo(Math.round(px) + .5, 0); ctx.lineTo(Math.round(px) + .5, this.hauteur); }
      for (let y = Math.floor(y0 / p) * p; y <= y1; y += p) { const [, py] = this.versEcran(0, y); ctx.moveTo(0, Math.round(py) + .5); ctx.lineTo(this.largeur, Math.round(py) + .5); }
      ctx.stroke();
    };
    if (sous * this.e >= 10) trace(sous, c.grille, 1);
    trace(pas, c.forte, 1);
    // origine
    const [ox, oy] = this.versEcran(0, 0);
    ctx.strokeStyle = c.texte; ctx.lineWidth = 1; ctx.beginPath();
    ctx.moveTo(ox - 6, oy); ctx.lineTo(ox + 6, oy); ctx.moveTo(ox, oy - 6); ctx.lineTo(ox, oy + 6); ctx.stroke();
    this.pas = pas;
  }

  tracerEchelle(c) {
    const { ctx } = this; const m = this.pas || 1; const w = m * this.e;
    const x = 16, y = this.hauteur - 16 - (this.decalageEchelle || 0);
    ctx.strokeStyle = c.encre; ctx.fillStyle = c.encre; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x, y - 5); ctx.lineTo(x, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y - 5); ctx.stroke();
    ctx.font = '11px ui-monospace, Consolas, monospace'; ctx.textBaseline = 'bottom';
    ctx.fillText(m >= 1 ? `${m} m` : `${Math.round(m * 100)} cm`, x + 4, y - 4);
  }
}

// Utilitaires de tracé partagés
export function nuagePoints(ctx, vue, tableau, pose, taille, couleur, alpha = 1) {
  // tableau : [x0, y0, x1, y1, …] en mm, dans le repère local du scan ; pose : [x, y, cap°]
  const a = (pose[2] * Math.PI) / 180, ca = Math.cos(a), sa = Math.sin(a), e = vue.e;
  const ox = vue.largeur / 2 - vue.cx * e, oy = vue.hauteur / 2 + vue.cy * e;
  ctx.globalAlpha = alpha; ctx.fillStyle = couleur; ctx.beginPath();
  const d = taille / 2;
  for (let i = 0; i < tableau.length; i += 2) {
    const lx = tableau[i] / 1000, ly = tableau[i + 1] / 1000;
    const x = pose[0] + lx * ca - ly * sa, y = pose[1] + lx * sa + ly * ca;
    const px = ox + x * e, py = oy - y * e;
    if (px < -4 || py < -4 || px > vue.largeur + 4 || py > vue.hauteur + 4) continue;
    ctx.rect(px - d, py - d, taille, taille);
  }
  ctx.fill(); ctx.globalAlpha = 1;
}

export function robot(ctx, vue, pose, couleur, perdu = false, c = null, fixe = 0) {
  const [px, py] = vue.versEcran(pose[0], pose[1]);
  const a = -(pose[2] * Math.PI) / 180; const taille = fixe || Math.max(11, 0.22 * vue.e);
  ctx.save(); ctx.translate(px, py); ctx.rotate(a);
  if (perdu) { ctx.strokeStyle = couleur; ctx.globalAlpha = .45; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(0, 0, taille * 1.9, 0, 7); ctx.stroke(); ctx.globalAlpha = 1; }
  ctx.fillStyle = couleur; ctx.strokeStyle = (c && c.fond) || '#fff'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(taille * 1.15, 0); ctx.lineTo(-taille * .8, taille * .75); ctx.lineTo(-taille * .45, 0); ctx.lineTo(-taille * .8, -taille * .75); ctx.closePath();
  ctx.stroke(); ctx.fill(); ctx.restore();
}

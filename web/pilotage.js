// Pilotage : clavier (Z S Q D A E, flèches) et manette (API Gamepad du navigateur), toujours actifs sur l'écran Direct.
// La page envoie une consigne toutes les 60 ms tant qu'on agit ; le serveur la périme au bout de 0,35 s (STOP si la page se fige).
import { appel } from './api.js';

const AXES = { z: [0, 1], s: [0, -1], q: [1, 1], d: [1, -1], a: [2, 1], e: [2, -1],
               arrowup: [0, 1], arrowdown: [0, -1], arrowleft: [2, 1], arrowright: [2, -1] };
const ZONE_MORTE = 0.22;

function sansZoneMorte(v) {
  const m = Math.abs(v);
  return m <= ZONE_MORTE ? 0 : Math.sign(v) * Math.min(1, (m - ZONE_MORTE) / (1 - ZONE_MORTE));
}

// Conversion du stick gauche (surge, sway) avec zone morte radiale et du stick droit (yaw) : mêmes règles qu'avant.
export function vecteurManette(lx, ly, rx) {
  const m = Math.hypot(lx, ly); let surge = 0, sway = 0;
  if (m > ZONE_MORTE) { const f = Math.min(1, (m - ZONE_MORTE) / (1 - ZONE_MORTE)) / m; surge = -ly * f; sway = -lx * f; }
  return [surge, sway, sansZoneMorte(-rx)];
}

export class Pilotage {
  constructor({ actif, surChangement, surMode }) {
    this.actif = actif; this.surChangement = surChangement; this.surMode = surMode;
    this.touches = new Set(); this.physiques = new Set(); this.verrouArret = false; this.manette = null; this.rbAvant = false;
    this.dernier = [0, 0, 0]; this.dernierEnvoi = 0; this.courant = [0, 0, 0];
    window.addEventListener('keydown', (e) => this.touche(e, true));
    window.addEventListener('keyup', (e) => this.touche(e, false));
    window.addEventListener('blur', () => { this.physiques.clear(); this.verrouArret = false; this.tout_arreter(); });
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.tout_arreter(); });
    setInterval(() => this.cycle(), 50);
  }

  // Champ où l'on tape du texte : les touches lui appartiennent. Les curseurs, cases et boutons n'en font pas partie.
  saisie(e) {
    const t = e.target; if (!t) return false;
    if (t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable) return true;
    return t.tagName === 'INPUT' && !['range', 'checkbox', 'radio', 'button'].includes(t.type);
  }

  // Arrêt d'urgence : coupe tout et ignore les touches de déplacement encore enfoncées (sinon la répétition clavier
  // les réactive aussitôt) jusqu'à ce qu'elles soient toutes relâchées.
  arretUrgence() {
    this.touches.clear(); this.verrouArret = this.physiques.size > 0;
    this.courant = [0, 0, 0]; this.dernier = [0, 0, 0]; this.surChangement(this.courant, this.sources());
    appel('/api/arret').catch(() => {});
  }

  touche(e, bas) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (!bas && k in AXES) { this.physiques.delete(k); if (!this.physiques.size) this.verrouArret = false; }
    if (k === ' ' || k === 'escape') {
      // Espace / Échap arrêtent partout, même si un curseur ou un bouton a le focus ; seul un champ de texte garde la touche.
      if (this.saisie(e) || !this.actif()) return;
      if (bas && !e.repeat) this.arretUrgence();
      e.preventDefault(); return;          // y compris au relâchement : Espace ne doit pas « cliquer » le bouton qui a le focus
    }
    if (!this.actif() || this.saisie(e)) { if (!bas) this.touches.delete(k); return; }
    if (k in AXES) {
      if (bas) { this.physiques.add(k); if (!this.verrouArret) this.touches.add(k); } else this.touches.delete(k);
      e.preventDefault();
    }
  }

  tout_arreter() {
    if (this.touches.size || this.dernier.some(Boolean)) { this.touches.clear(); this.envoyer([0, 0, 0], true); }
  }

  lireManette() {
    const pads = (navigator.getGamepads && navigator.getGamepads()) || [];
    const pad = [...pads].find((p) => p && p.connected && p.axes.length >= 4);
    this.manette = pad || null;
    if (!pad) { this.rbAvant = false; return { presente: false, v: [0, 0, 0], b: false }; }
    const b = !!(pad.buttons[1] && pad.buttons[1].pressed), rb = !!(pad.buttons[5] && pad.buttons[5].pressed);
    if (rb && !this.rbAvant && this.actif()) this.surMode();
    this.rbAvant = rb;
    return { presente: true, b, v: b ? [0, 0, 0] : vecteurManette(pad.axes[0], pad.axes[1], pad.axes[2]) };
  }

  sources() { return { clavier: this.touches.size > 0, manette: !!this.manette }; }

  cycle() {
    const m = this.lireManette();
    const actif = this.actif();
    let v = [0, 0, 0];
    if (actif) {
      for (const k of this.touches) { const [axe, signe] = AXES[k]; v[axe] += signe; }
      v = v.map((x) => Math.max(-1, Math.min(1, x)));
      if (m.presente && m.v.some(Boolean)) v = m.v;
      if (m.b) v = [0, 0, 0];
    } else if (this.touches.size) this.touches.clear();
    this.courant = v;
    this.surChangement(v, { clavier: this.touches.size > 0, manette: m.presente });
    this.envoyer(v, false);
  }

  envoyer(v, force) {
    const bouge = v.some(Boolean), change = v.some((x, i) => x !== this.dernier[i]);
    const maintenant = performance.now();
    if (!bouge && !change && !force) return;
    if (bouge && !change && maintenant - this.dernierEnvoi < 60) return;
    this.dernier = v; this.dernierEnvoi = maintenant;
    appel('/api/pilote', { surge: v[0], sway: v[1], yaw: v[2] }).catch(() => {});
    if (!bouge) setTimeout(() => appel('/api/pilote', { surge: 0, sway: 0, yaw: 0 }).catch(() => {}), 120);
  }
}

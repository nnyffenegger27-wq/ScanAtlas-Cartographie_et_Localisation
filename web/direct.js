// Écran Direct : carte en cours de tracé, instruments, pilotage visible.
import { appel, lire, agir } from './api.js';
import { Vue, nuagePoints, robot, imageGrille, poserGrille, segments } from './vue.js';

export function creerDirect({ pilotage }) {
  const S = { carte: null, scan: null, etat: null, suivre: true, couches: new Set(['points']), grille: null, auto: null,
              replacer: null, suivreAvant: true };
  const $ = (id) => document.getElementById(id);
  const vue = new Vue($('toile-direct'), dessiner);
  vue.decalageEchelle = 76;   // au-dessus de la barre d'outils du bas
  vue.surDeplacement = () => { if (S.suivre) basculerSuivi(false); };
  let affiche = false;

  function basculerSuivi(v) {
    S.suivre = v; $('z-suivre').classList.toggle('actif', v);
    if (v && S.scan) vue.centrer(S.scan.pose[0], S.scan.pose[1]);
  }
  $('z-suivre').onclick = () => basculerSuivi(!S.suivre);
  $('z-plus').onclick = () => vue.zoomer(1.4);
  $('z-moins').onclick = () => vue.zoomer(1 / 1.4);

  function dessiner(ctx, v, c) {
    const carte = S.carte;
    if (carte && !carte.vide) {
      if (S.couches.has('grille') && S.grille && !S.grille.vide) {
        if (!S.grille.image) S.grille.image = imageGrille(S.grille, c);
        poserGrille(ctx, v, S.grille, S.grille.image);
      }
      if (S.couches.has('points')) nuagePoints(ctx, v, carte.pts, [0, 0, 0], v.e > 40 ? 3 : 2, c.point, .75);
      if (S.couches.has('plan')) segments(ctx, v, carte.segments, c.encre, 2);
      if (carte.trajet.length > 1) {
        ctx.strokeStyle = c.accent; ctx.lineWidth = 1.6; ctx.setLineDash([5, 4]); ctx.globalAlpha = .8; ctx.beginPath();
        carte.trajet.forEach(([x, y], i) => { const [px, py] = v.versEcran(x, y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
        ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      }
    }
    exploration(ctx, v, c);
    if (S.scan) {
      const perdu = !S.scan.accepte;
      nuagePoints(ctx, v, S.scan.pts, S.scan.pose_scan, 3.4, perdu ? c.alerte : c.accent, .95);
      robot(ctx, v, S.scan.pose, perdu ? c.alerte : c.accent, perdu, c);
    }
    indice(ctx, v, c);
  }

  // Exploration autonome : zones à voir, chemin prévu, destination
  function exploration(ctx, v, c) {
    const a = S.auto; if (!a || a.etat !== 'exploration') return;
    ctx.save();
    ctx.fillStyle = c.alerte; ctx.globalAlpha = .55;
    for (const [x, y] of a.frontieres || []) { const [px, py] = v.versEcran(x, y); ctx.beginPath(); ctx.moveTo(px, py - 5); ctx.lineTo(px + 5, py); ctx.lineTo(px, py + 5); ctx.lineTo(px - 5, py); ctx.closePath(); ctx.fill(); }
    ctx.globalAlpha = .95;
    if (a.chemin && a.chemin.length && S.scan) {
      ctx.strokeStyle = c.accent; ctx.lineWidth = 2.4; ctx.setLineDash([2, 6]); ctx.lineCap = 'round'; ctx.beginPath();
      const [x0, y0] = v.versEcran(S.scan.pose[0], S.scan.pose[1]); ctx.moveTo(x0, y0);
      for (const [x, y] of a.chemin) { const [px, py] = v.versEcran(x, y); ctx.lineTo(px, py); }
      ctx.stroke(); ctx.setLineDash([]);
    }
    if (a.cible) {
      const [px, py] = v.versEcran(a.cible[0], a.cible[1]);
      ctx.strokeStyle = c.accent; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(px, py, 9, 0, 7); ctx.stroke();
      ctx.beginPath(); ctx.arc(px, py, 3, 0, 7); ctx.fillStyle = c.accent; ctx.fill();
    }
    ctx.restore();
  }

  // Position et direction indiquées par l'utilisateur pendant « Replacer »
  function indice(ctx, v, c) {
    const r = S.replacer; if (!r || !r.debut) return;
    const cap = r.cap != null ? r.cap : (S.scan ? S.scan.pose[2] : 0);
    ctx.save(); ctx.globalAlpha = .9;
    robot(ctx, v, [r.debut[0], r.debut[1], cap], c.accent, true, c);
    if (r.cap != null) {
      const [px, py] = v.versEcran(r.debut[0], r.debut[1]); const a = -cap * Math.PI / 180;
      ctx.strokeStyle = c.accent; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.beginPath(); ctx.moveTo(px, py);
      ctx.lineTo(px + Math.cos(a) * 90, py + Math.sin(a) * 90); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.restore();
  }

  // Couches : la grille d'occupation vient du serveur, seulement quand elle est visible et a changé.
  let grilleEnCours = false, grilleT = 0;
  async function rafraichirGrille(force = false) {
    if (!S.couches.has('grille') || grilleEnCours) return;
    const cles = S.carte && !S.carte.vide ? S.carte.cles : -1;
    if (cles < 0 || (!force && S.grille && S.grille.cles === cles)) return;
    if (Date.now() - grilleT < 1200) { setTimeout(() => rafraichirGrille(), 1300); return; }
    grilleEnCours = true; grilleT = Date.now();
    try { const g = await lire('/api/direct/grille'); S.grille = g; if (affiche) vue.demander(); } catch { /* prochaine carte */ }
    grilleEnCours = false;
  }
  for (const b of document.querySelectorAll('#seg-couches-direct button')) {
    b.onclick = () => {
      const k = b.dataset.couche;
      if (S.couches.has(k) && S.couches.size > 1) S.couches.delete(k); else S.couches.add(k);
      for (const x of document.querySelectorAll('#seg-couches-direct button')) x.classList.toggle('actif', S.couches.has(x.dataset.couche));
      rafraichirGrille(true); vue.demander();
    };
  }

  // Replacer le robot
  function replacerActif() { return !!(S.replacer && S.replacer.actif); }
  function demarrerReplacer() {
    S.replacer = { actif: true, debut: null, cap: null }; S.suivreAvant = S.suivre; basculerSuivi(false);
    $('consigne-replacer').hidden = false; $('vue-direct').classList.add('replacement'); vue.demander();
  }
  function finirReplacer() {
    S.replacer = null; $('consigne-replacer').hidden = true; $('vue-direct').classList.remove('replacement');
    if (S.suivreAvant) basculerSuivi(true); vue.demander();
  }
  vue.interception = (phase, e, [mx, my]) => {
    if (!replacerActif()) return false;
    const r = S.replacer;
    if (phase === 'debut') { r.debut = [mx, my]; r.cap = null; vue.demander(); return true; }
    if (!r.debut) return true;
    const dx = mx - r.debut[0], dy = my - r.debut[1];
    if (Math.hypot(dx, dy) > .12) r.cap = Math.atan2(dy, dx) * 180 / Math.PI;
    if (phase === 'bouge') { vue.demander(); return true; }
    const cap = r.cap != null ? r.cap : (S.scan ? S.scan.pose[2] : 0);
    const [x, y] = r.debut;
    finirReplacer();
    agir(appel('/api/replacer', { x, y, cap }));
    return true;
  };
  $('bouton-replacer').onclick = () => (replacerActif() ? finirReplacer() : demarrerReplacer());
  $('i-replacer').onclick = demarrerReplacer;
  $('replacer-annuler').onclick = finirReplacer;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && replacerActif()) finirReplacer(); });

  // Exploration autonome
  $('bouton-auto').onclick = () => {
    const exploration = S.auto && S.auto.etat === 'exploration';
    agir(appel('/api/auto', { actif: !exploration }));
  };

  function instruments() {
    const sc = S.scan, e = S.etat;
    const zone = $('etat-suivi');
    let classe = '', texte = 'Hors connexion';
    if (e && e.connexion === 'connecte') {
      if (!sc) { classe = 'attente'; texte = e.pret ? 'En attente du premier tour' : 'En attente du flux lidar'; }
      else if (sc.accepte) { classe = 'actif'; texte = 'Position suivie'; }
      else { classe = 'perdu'; texte = sc.perdu != null ? `Position perdue · ${Math.round(sc.perdu)} s` : 'Position perdue'; }
    } else if (e && e.connexion === 'connexion') { classe = 'attente'; texte = 'Connexion…'; }
    else if (e && e.connexion === 'attente') { classe = 'attente'; texte = 'Reconnexion…'; }
    zone.className = 'etat ' + classe; $('etat-suivi-texte').textContent = texte;
    if (sc) {
      $('i-pos').textContent = `x ${sc.pose[0].toFixed(2)} · y ${sc.pose[1].toFixed(2)} m`;
      $('i-cap').textContent = `${sc.pose[2].toFixed(1)}°`;
      $('i-conc').textContent = sc.concordance == null ? '—' : `${sc.concordance.toFixed(0)} %`;
      $('i-cles').textContent = sc.cles;
      $('i-note').textContent = sc.verification > 0 && sc.accepte ? 'Vérification de la position : la carte n’est pas enrichie pour l’instant.' : (sc.accepte ? '' : sc.message);
    } else { for (const id of ['i-pos', 'i-cap', 'i-conc']) $(id).textContent = '—'; $('i-note').textContent = ''; }
    const a = S.auto, exploration = !!(a && a.etat === 'exploration');
    if (a && a.etat !== 'inactif' && a.message && (sc ? sc.accepte : true)) $('i-note').textContent = a.message;
    const aCarte = !!(S.carte && !S.carte.vide), connecte = !!(e && e.connexion === 'connecte');
    $('i-replacer').hidden = !(sc && !sc.accepte && aCarte && connecte);
    const auto = $('bouton-auto');
    auto.textContent = exploration ? 'Arrêter l’exploration' : 'Explorer seul';
    auto.classList.toggle('actif', exploration); auto.classList.toggle('primaire', !exploration);
    auto.disabled = !connecte || (!exploration && !(sc && sc.accepte && e.reglages.mode === 'cartographier'));
    auto.title = exploration ? 'Arrête l’exploration (toucher une commande la coupe aussi)'
      : (e && e.reglages.mode !== 'cartographier' ? 'Passe en mode Cartographier pour explorer seul' : 'Le robot choisit seul où aller pour compléter la carte');
    $('bouton-replacer').disabled = !connecte || !aCarte;
    $('bouton-scan').disabled = !(connecte && sc && sc.accepte);
    const vide = (!S.carte || S.carte.vide) && !sc;
    $('accueil').hidden = !(vide && (!e || e.connexion === 'hors_ligne'));
    $('bouton-retrouver').disabled = !(S.carte && !S.carte.vide) || !e || e.connexion !== 'connecte';
  }

  // Mode, réglages, actions
  for (const b of document.querySelectorAll('#seg-mode button')) b.onclick = () => agir(appel('/api/reglages', { mode: b.dataset.mode }));
  $('bouton-retrouver').onclick = () => agir(appel('/api/retrouver'));
  $('bouton-scan').onclick = () => agir(appel('/api/scan'));
  $('m-reprendre').onclick = () => { fermerMenu(); agir(appel('/api/reprendre')); };
  $('m-nouvelle').onclick = () => { fermerMenu(); if (confirm('Effacer la carte actuelle ? Enregistre-la d’abord depuis l’écran Carte pour la conserver.')) agir(appel('/api/nouvelle_carte')); };
  $('recup-auto').onchange = (e) => agir(appel('/api/reglages', { recup_auto: e.target.checked }));
  $('puissance').oninput = (e) => { $('o-puissance').textContent = e.target.value + ' %'; };
  $('puissance').onchange = (e) => agir(appel('/api/reglages', { puissance: +e.target.value }));
  $('rotation').oninput = (e) => { $('o-rotation').textContent = e.target.value + ' %'; };
  $('rotation').onchange = (e) => agir(appel('/api/reglages', { rotation_max: +e.target.value }));
  const menu = $('menu-plus');
  const fermerMenu = () => { menu.hidden = true; };
  $('bouton-plus').onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
  document.addEventListener('click', (e) => { if (!menu.contains(e.target)) fermerMenu(); });

  function pave(v, sources) {
    const p = +$('puissance').value / 100, yaw = +$('rotation').value / 100;
    const val = { avance: Math.max(0, v[0]), recul: Math.max(0, -v[0]), gauche: Math.max(0, v[1]), droite: Math.max(0, -v[1]),
                  rot_g: Math.max(0, v[2]) * yaw, rot_d: Math.max(0, -v[2]) * yaw, stop: v.some(Boolean) ? 0 : 1 };
    for (const i of document.querySelectorAll('#pave i[data-c]')) {
      const x = val[i.dataset.c] * (i.dataset.c === 'stop' ? 1 : p);
      i.style.setProperty('--v', x.toFixed(2)); i.classList.toggle('on', x > 0.01);
    }
    $('p-clavier').classList.add('on'); $('p-manette').classList.toggle('on', !!sources.manette);
    $('t-manette').textContent = sources.manette ? 'Manette' : 'Manette absente';
    $('entrees').title = sources.manette ? 'Manette détectée' : 'Branche une manette puis appuie sur un bouton pour l’activer';
  }

  return {
    pave,
    montrer(oui) { affiche = oui; if (oui) { vue.redimensionner(); vue.demander(); } },
    etat(e) {
      S.etat = e;
      if (e.auto) { S.auto = Object.assign({}, S.auto, e.auto); if (e.auto.etat !== 'exploration') { S.auto.chemin = []; S.auto.cible = null; S.auto.frontieres = []; } }
      for (const b of document.querySelectorAll('#seg-mode button')) b.classList.toggle('actif', b.dataset.mode === e.reglages.mode);
      $('recup-auto').checked = e.reglages.recup_auto;
      $('puissance').value = e.reglages.puissance; $('o-puissance').textContent = e.reglages.puissance + ' %';
      $('rotation').value = e.reglages.rotation_max; $('o-rotation').textContent = e.reglages.rotation_max + ' %';
      instruments(); vue.demander();
    },
    scan(s) {
      const premier = !S.scan; S.scan = s;
      if (S.suivre) { vue.cx += (s.pose[0] - vue.cx) * .35; vue.cy += (s.pose[1] - vue.cy) * .35; if (premier) { vue.cx = s.pose[0]; vue.cy = s.pose[1]; } }
      instruments(); if (affiche) vue.demander();
    },
    carte(c) { S.carte = c; if (c.vide) { S.scan = null; S.grille = null; } else rafraichirGrille(); instruments(); if (affiche) vue.demander(); },
    auto(d) { S.auto = Object.assign({}, S.auto, d); instruments(); if (affiche) vue.demander(); },
  };
}

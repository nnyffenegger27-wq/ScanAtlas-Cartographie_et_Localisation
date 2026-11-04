// Écran Direct : carte en cours de tracé, instruments, pilotage visible.
import { appel, agir } from './api.js';
import { Vue, nuagePoints, robot } from './vue.js';

export function creerDirect({ pilotage }) {
  const S = { carte: null, scan: null, etat: null, suivre: true };
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
      nuagePoints(ctx, v, carte.pts, [0, 0, 0], v.e > 40 ? 3 : 2, c.point, .75);
      ctx.strokeStyle = c.point; ctx.globalAlpha = .5; ctx.lineWidth = 1.4; ctx.beginPath();
      for (const s of carte.segments) { const [x0, y0] = v.versEcran(s[0], s[1]), [x1, y1] = v.versEcran(s[2], s[3]); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); }
      ctx.stroke(); ctx.globalAlpha = 1;
      if (carte.trajet.length > 1) {
        ctx.strokeStyle = c.accent; ctx.lineWidth = 1.6; ctx.setLineDash([5, 4]); ctx.globalAlpha = .8; ctx.beginPath();
        carte.trajet.forEach(([x, y], i) => { const [px, py] = v.versEcran(x, y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
        ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      }
    }
    if (S.scan) {
      const perdu = !S.scan.accepte;
      nuagePoints(ctx, v, S.scan.pts, S.scan.pose_scan, 3.4, perdu ? c.alerte : c.accent, .95);
      robot(ctx, v, S.scan.pose, perdu ? c.alerte : c.accent, perdu, c);
    }
  }

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
    const vide = (!S.carte || S.carte.vide) && !sc;
    $('accueil').hidden = !(vide && (!e || e.connexion === 'hors_ligne'));
    $('bouton-retrouver').disabled = !(S.carte && !S.carte.vide) || !e || e.connexion !== 'connecte';
  }

  // Mode, réglages, actions
  for (const b of document.querySelectorAll('#seg-mode button')) b.onclick = () => agir(appel('/api/reglages', { mode: b.dataset.mode }));
  $('bouton-retrouver').onclick = () => agir(appel('/api/retrouver'));
  $('m-reprendre').onclick = () => { fermerMenu(); agir(appel('/api/reprendre')); };
  $('m-nouvelle').onclick = () => { fermerMenu(); if (confirm('Effacer la carte actuelle ? Enregistre-la d’abord depuis l’écran Carte pour la conserver.')) agir(appel('/api/nouvelle_carte')); };
  $('recup-auto').onchange = (e) => agir(appel('/api/reglages', { recup_auto: e.target.checked }));
  $('puissance').oninput = (e) => { $('o-puissance').textContent = e.target.value + ' %'; };
  $('puissance').onchange = (e) => agir(appel('/api/reglages', { puissance: +e.target.value }));
  $('rotation').oninput = (e) => { $('o-rotation').textContent = e.target.value + ' %'; };
  $('rotation').onchange = (e) => agir(appel('/api/reglages', { rotation_max: +e.target.value }));
  $('bouton-stop').onclick = () => { appel('/api/arret').catch(() => {}); };
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
    carte(c) { S.carte = c; if (c.vide) S.scan = null; instruments(); if (affiche) vue.demander(); },
  };
}

// Écran Carte : la même carte que le direct, pour la relire, la corriger, l'exporter.
import { appel, lire, agir, envoyerFichier, lienSession, lienScan, toast } from './api.js';
import { Vue, nuagePoints, robot } from './vue.js';

export function creerCarte() {
  const $ = (id) => document.getElementById(id);
  const S = { liste: null, nuage: null, grille: null, plan: null, versionAffichee: -1, couches: new Set(['points']), outil: 'naviguer',
              choisi: null, apercu: null, proposition: null, ajuste: false, verrou: false, affiche: false, sale: true, image: null };
  const vue = new Vue($('toile-carte'), dessiner);
  vue.interception = interception;
  vue.surSurvol = ([x, y]) => { $('coordonnees').textContent = `x ${x.toFixed(2)} m   y ${y.toFixed(2)} m`; };

  // ---------------------------------------------------------------- chargement
  async function recharger() {
    if (!S.affiche) { S.sale = true; return; }
    S.sale = false;
    const liste = await agir(lire('/api/carte'));
    if (!liste) return;
    const change = !S.liste || liste.version !== S.liste.version;
    S.liste = liste;
    if (S.choisi != null && S.choisi >= liste.scans.length) S.choisi = null;
    if (change) {
      const [nuage, grille, plan] = await Promise.all([
        lire('/api/carte/nuage').catch(() => null),
        S.couches.has('grille') ? lire('/api/carte/grille').catch(() => null) : null,
        S.couches.has('plan') ? lire('/api/carte/plan').catch(() => null) : null]);
      S.nuage = nuage; S.grille = grille; S.plan = plan; S.image = null;
      if (S.choisi != null) S.proposition = null;
      if (!S.ajuste && nuage && nuage.scans.length) { cadrer(); S.ajuste = true; }
    }
    interface_(); vue.demander();
  }

  function cadrer() {
    let [a, b, c, d] = [Infinity, Infinity, -Infinity, -Infinity];
    for (const s of S.nuage.scans) {
      const t = (s.pose[2] * Math.PI) / 180, ct = Math.cos(t), st = Math.sin(t);
      for (let i = 0; i < s.pts.length; i += 2) {
        const lx = s.pts[i] / 1000, ly = s.pts[i + 1] / 1000, x = s.pose[0] + lx * ct - ly * st, y = s.pose[1] + lx * st + ly * ct;
        if (x < a) a = x; if (x > c) c = x; if (y < b) b = y; if (y > d) d = y;
      }
    }
    if (isFinite(a)) vue.ajuster(a, b, c, d);
  }

  // ---------------------------------------------------------------- dessin
  function indexPose(id) { return S.apercu && S.apercu.id === id ? S.apercu.pose : S.liste.scans[id].pose; }

  function dessiner(ctx, v, c) {
    if (!S.liste) return;
    if (S.couches.has('grille') && S.grille) dessinerGrille(ctx, v, c);
    if (S.couches.has('points') && S.nuage) {
      for (const s of S.nuage.scans) {
        const meta = S.liste.scans[s.id]; if (!meta || s.id === S.choisi) continue;
        nuagePoints(ctx, v, s.pts, indexPose(s.id), 2.4, c.point, meta.inclus ? .8 : .28);
      }
      const sel = S.nuage.scans.find((s) => s.id === S.choisi);
      if (sel) nuagePoints(ctx, v, sel.pts, indexPose(sel.id), 3.2, c.accent, 1);
    }
    if (S.couches.has('plan') && S.plan) {
      ctx.strokeStyle = c.encre; ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.beginPath();
      for (const s of S.plan.segments) { const [x0, y0] = v.versEcran(s[0], s[1]), [x1, y1] = v.versEcran(s[2], s[3]); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); }
      ctx.stroke();
    }
    if (S.proposition && S.nuage) {
      const s = S.nuage.scans.find((q) => q.id === S.proposition.id);
      if (s) nuagePoints(ctx, v, s.pts, S.proposition.pose, 3.4, c.alerte, 1);
    }
    // positions des scans : petit repère, plus marqué pour le scan choisi
    for (const m of S.liste.scans) {
      if (!m.visible) continue;
      robot(ctx, v, indexPose(m.id), m.id === S.choisi ? c.accent : c.texte, false, c, m.id === S.choisi ? 9 : 5);
    }
  }

  function dessinerGrille(ctx, v, c) {
    const g = S.grille;
    if (!S.image) {
      const img = document.createElement('canvas'); img.width = g.largeur; img.height = g.hauteur;
      const x = img.getContext('2d'); const data = x.createImageData(g.largeur, g.hauteur);
      const brut = Uint8Array.from(atob(g.donnees), (ch) => ch.charCodeAt(0));
      const tint = (hex) => { const e = document.createElement('canvas').getContext('2d'); e.fillStyle = hex; e.fillRect(0, 0, 1, 1); return e.getImageData(0, 0, 1, 1).data; };
      const libre = tint(c.accent), plein = tint(c.point);
      for (let r = 0; r < g.hauteur; r++) for (let q = 0; q < g.largeur; q++) {
        const val = brut[r * g.largeur + q]; if (!val) continue;
        const p = (val - 1) / 254, o = ((g.hauteur - 1 - r) * g.largeur + q) * 4;
        const cible = p > .5 ? plein : libre;
        data.data[o] = cible[0]; data.data[o + 1] = cible[1]; data.data[o + 2] = cible[2]; data.data[o + 3] = p > .5 ? 50 + 190 * p : 40 * (1 - p) + 14;
      }
      x.putImageData(data, 0, 0); S.image = img;
    }
    const [x0, y0] = v.versEcran(g.origine[0], g.origine[1] + g.hauteur * g.resolution);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(S.image, x0, y0, g.largeur * g.resolution * v.e, g.hauteur * g.resolution * v.e);
  }

  // ---------------------------------------------------------------- outils sur la toile
  let geste = null;
  function interception(phase, e, [mx, my]) {
    if (S.outil === 'naviguer' || S.choisi == null || S.verrou) return false;
    const pose = indexPose(S.choisi);
    if (phase === 'debut') { geste = { mx, my, pose: [...pose], a0: Math.atan2(my - pose[1], mx - pose[0]) }; return true; }
    if (!geste) return true;
    if (phase === 'bouge') {
      if (S.outil === 'deplacer') S.apercu = { id: S.choisi, pose: [geste.pose[0] + mx - geste.mx, geste.pose[1] + my - geste.my, geste.pose[2]] };
      else { const da = ((Math.atan2(my - geste.pose[1], mx - geste.pose[0]) - geste.a0) * 180) / Math.PI; S.apercu = { id: S.choisi, pose: [geste.pose[0], geste.pose[1], geste.pose[2] + da] }; }
      remplirPose(S.apercu.pose); vue.demander();
    } else if (phase === 'fin') {
      const a = S.apercu; geste = null; S.apercu = null;
      if (a) agir(appel('/api/carte/scan', { id: a.id, pose: a.pose }));
    }
    return true;
  }

  // ---------------------------------------------------------------- interface
  function remplirPose(p) { $('p-x').value = p[0].toFixed(3); $('p-y').value = p[1].toFixed(3); $('p-t').value = p[2].toFixed(2); }

  function interface_() {
    const L = S.liste; if (!L) return;
    const inclus = L.scans.filter((s) => s.inclus).length;
    $('carte-nom').textContent = L.nom;
    $('carte-resume').textContent = L.scans.length ? `${L.scans.length} scans · ${inclus} inclus · ${L.scans.reduce((a, s) => a + s.points, 0).toLocaleString('fr-FR')} mesures` : 'Aucun scan';
    $('carte-vide').hidden = L.scans.length > 0;
    const ul = $('liste-scans'); ul.textContent = '';
    for (const s of L.scans) {
      const li = document.createElement('li'); li.className = s.id === S.choisi ? 'choisi' : '';
      const oeil = bouton('◉', s.visible, 'Afficher / masquer', () => agir(appel('/api/carte/scan', { id: s.id, visible: !s.visible })));
      const inc = bouton('✓', s.inclus, 'Inclure dans les calculs et la carte de départ', () => agir(appel('/api/carte/scan', { id: s.id, inclus: !s.inclus })));
      const nom = document.createElement('span'); nom.className = 'nom'; nom.textContent = s.nom; nom.title = s.source;
      const n = document.createElement('span'); n.className = 'n'; n.textContent = s.points;
      li.append(oeil, inc, nom, n);
      li.onclick = () => { S.choisi = s.id; S.proposition = null; $('insp-resultat').hidden = true; interface_(); vue.demander(); };
      ul.appendChild(li);
    }
    const f = L.filtres; for (const [id, k] of [['f-mini', 'mini'], ['f-maxi', 'maxi'], ['f-intensite', 'intensite']]) if (document.activeElement !== $(id)) $(id).value = f[k];
    $('f-resolution').value = String(L.resolution);
    const m = S.choisi != null ? L.scans[S.choisi] : null;
    $('inspecteur').hidden = !m;
    if (m) {
      $('insp-nom').textContent = m.nom;
      $('insp-info').textContent = `${m.source} · ${m.points} points · étendue ${m.etendue}° · ${m.etat}` + (m.recalage ? ` · ${m.recalage}` : '');
      if (!['p-x', 'p-y', 'p-t'].includes(document.activeElement.id) && !S.apercu) remplirPose(m.pose);
      $('insp-csv').href = lienScan(m.id);
    }
    verrouiller();
  }
  function bouton(texte, on, titre, f) {
    const b = document.createElement('button'); b.className = 'bascule' + (on ? ' on' : ''); b.textContent = texte; b.title = titre;
    b.onclick = (e) => { e.stopPropagation(); f(); }; return b;
  }
  function verrouiller() {
    const v = S.verrou;
    $('verrou').hidden = !v;
    for (const id of ['c-importer', 'vide-importer', 'vide-exemple', 'c-assembler', 'insp-recaler', 'insp-supprimer', 'insp-appliquer', 'p-x', 'p-y', 'p-t', 'f-mini', 'f-maxi', 'f-intensite', 'f-resolution']) $(id).disabled = v;
    for (const b of document.querySelectorAll('#seg-outil button[data-outil]:not([data-outil=naviguer])')) b.disabled = v;
    if (v && S.outil !== 'naviguer') choisirOutil('naviguer');
  }

  function choisirOutil(o) {
    S.outil = o; for (const b of document.querySelectorAll('#seg-outil button')) b.classList.toggle('actif', b.dataset.outil === o);
    $('toile-carte').style.cursor = o === 'naviguer' ? '' : 'crosshair';
  }
  for (const b of document.querySelectorAll('#seg-outil button')) b.onclick = () => {
    if (b.dataset.outil !== 'naviguer' && S.choisi == null) { toast('Choisis d’abord un scan dans la liste.'); return; }
    choisirOutil(b.dataset.outil);
  };
  for (const b of document.querySelectorAll('#seg-couches button')) b.onclick = () => {
    const c = b.dataset.couche; S.couches.has(c) ? S.couches.delete(c) : S.couches.add(c);
    if (!S.couches.size) S.couches.add('points');
    for (const x of document.querySelectorAll('#seg-couches button')) x.classList.toggle('actif', S.couches.has(x.dataset.couche));
    S.liste = null; recharger();    // recharge les couches demandées
  };

  // import / export
  const fichier = $('fichier');
  async function importer(fichiers) {
    for (const f of fichiers) {
      const r = await agir(envoyerFichier(f.name, f));
      if (r) toast(r.message);
    }
    S.ajuste = false; recharger();
  }
  $('c-importer').onclick = $('vide-importer').onclick = () => fichier.click();
  fichier.onchange = () => { importer([...fichier.files]); fichier.value = ''; };
  const zone = document.querySelector('.zone-carte');
  zone.addEventListener('dragover', (e) => { if (S.verrou) return; e.preventDefault(); zone.classList.add('glisse'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('glisse'));
  zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('glisse'); if (!S.verrou) importer([...e.dataTransfer.files]); });
  $('c-enregistrer').onclick = () => { if (!S.liste || !S.liste.scans.length) { toast('La carte est vide.'); return; } location.href = lienSession(); };
  $('vide-exemple').onclick = async () => { await agir(appel('/api/carte/demo')); S.ajuste = false; recharger(); };
  $('c-tout-visible').onclick = () => agir(appel('/api/carte/tous', { visible: !(S.liste && S.liste.scans.every((s) => s.visible)) }));
  $('c-tout-inclus').onclick = () => { if (!S.verrou) agir(appel('/api/carte/tous', { inclus: !(S.liste && S.liste.scans.every((s) => s.inclus)) })); else toast('Déconnecte le robot avant de modifier la carte.', true); };

  // pose, recalage, suppression
  const validerPose = () => {
    const p = ['p-x', 'p-y', 'p-t'].map((id) => parseFloat($(id).value.replace(',', '.')));
    if (p.some((x) => !isFinite(x))) { toast('Pose invalide.', true); return; }
    agir(appel('/api/carte/scan', { id: S.choisi, pose: p }));
  };
  for (const id of ['p-x', 'p-y', 'p-t']) $(id).onchange = validerPose;
  $('insp-recaler').onclick = () => agir(appel('/api/carte/recaler', { id: S.choisi }));
  $('insp-appliquer').onclick = () => { const p = S.proposition; if (!p) return; $('insp-resultat').hidden = true; S.proposition = null; agir(appel('/api/carte/scan', { id: p.id, pose: p.pose })); };
  $('insp-ignorer').onclick = () => { S.proposition = null; $('insp-resultat').hidden = true; vue.demander(); };
  $('insp-supprimer').onclick = () => { const m = S.liste.scans[S.choisi]; if (confirm(`Supprimer « ${m.nom} » de la carte ?`)) { const id = S.choisi; S.choisi = null; agir(appel('/api/carte/supprimer', { id })); } };
  $('c-assembler').onclick = () => agir(appel('/api/carte/assembler'));
  $('c-annuler').onclick = () => agir(appel('/api/carte/annuler'));

  // filtres
  const menu = $('menu-filtres');
  $('bouton-filtres').onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
  document.addEventListener('click', (e) => { if (!menu.contains(e.target)) menu.hidden = true; });
  const num = (id) => parseFloat($(id).value.replace(',', '.'));
  for (const id of ['f-mini', 'f-maxi', 'f-intensite']) $(id).onchange = () => agir(appel('/api/carte/filtres', { mini: num('f-mini'), maxi: num('f-maxi'), intensite: num('f-intensite') })).then(() => recharger());
  $('f-resolution').onchange = () => agir(appel('/api/carte/filtres', { resolution: num('f-resolution') }));

  return {
    montrer(oui) { S.affiche = oui; if (oui) { vue.redimensionner(); if (S.sale || !S.liste) recharger(); else vue.demander(); } },
    document() { if (S.affiche) recharger(); else S.sale = true; },
    etat(e) {
      const v = e.connexion !== 'hors_ligne'; if (v !== S.verrou) { S.verrou = v; if (S.liste) interface_(); }
    },
    tache(t) {
      $('c-tache').textContent = t.texte || '';
      $('c-annuler').hidden = t.etat !== 'en_cours';
      for (const id of ['c-assembler', 'insp-recaler']) $(id).disabled = t.etat === 'en_cours' || S.verrou;
      if (t.etat === 'fini' && t.nom === 'Recalage' && t.resultat) {
        const r = t.resultat;
        $('insp-resultat').hidden = false;
        $('insp-appliquer').hidden = !r.applicable;
        $('insp-resultat-texte').textContent = r.applicable
          ? `Pose trouvée : x ${r.pose[0].toFixed(3)} m, y ${r.pose[1].toFixed(3)} m, cap ${r.pose[2].toFixed(2)}° · concordance ${(100 * r.concordance).toFixed(0)} % · RMSE ${(1000 * r.rmse).toFixed(0)} mm. L’aperçu orange montre le résultat.`
          : 'Pas de position sûre : ' + r.message;
        S.proposition = r.applicable ? { id: r.id, pose: r.pose } : null; vue.demander();
      }
      if (t.etat === 'fini' && t.nom === 'Assemblage' && t.resultat) toast(t.resultat.message);
      if (t.etat === 'erreur') toast(t.texte, true);
    },
  };
}

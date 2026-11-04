// Point d'entrée : écrans, connexion au robot, flux d'événements.
import { appel, lire, agir, ecouter, toast } from './api.js';
import { Pilotage } from './pilotage.js';
import { creerDirect } from './direct.js';
import { creerCarte } from './carte.js';

const $ = (id) => document.getElementById(id);
let etat = null, vueActive = 'direct';

const direct = creerDirect({});
const carte = creerCarte();
const pilotage = new Pilotage({
  actif: () => vueActive === 'direct' && document.hasFocus(),
  surChangement: (v, s) => direct.pave(v, s),
  surMode: () => agir(appel('/api/reglages', { mode: etat && etat.reglages.mode === 'cartographier' ? 'localiser' : 'cartographier' })),
});

// ---- écrans
function afficher() {
  const nom = location.hash === '#carte' ? 'carte' : 'direct';
  vueActive = nom;
  for (const a of document.querySelectorAll('.onglets a')) a.classList.toggle('actif', a.dataset.vue === nom);
  $('vue-direct').hidden = nom !== 'direct'; $('vue-carte').hidden = nom !== 'carte';
  direct.montrer(nom === 'direct'); carte.montrer(nom === 'carte');
  if (nom !== 'direct') agir(appel('/api/arret'));
}
window.addEventListener('hashchange', afficher);

// ---- connexion
let liaison = 'wifi';
const pop = $('popover-connexion');
function majLiaison() {
  for (const b of document.querySelectorAll('#seg-liaison button')) b.classList.toggle('actif', b.dataset.liaison === liaison);
  const usb = liaison === 'usb';
  $('etiquette-hote').textContent = usb ? 'Port série' : 'Adresse du robot';
  $('aide-liaison').innerHTML = usb ? 'Câble USB branché au robot. Laisse « auto » si un seul port est détecté.' : 'Connecte d’abord le PC au Wi-Fi <b>ScanAtlas</b> du robot.';
}
function choisirLiaison(l, remplir = true) {
  liaison = l; majLiaison();
  const h = $('hote');
  if (remplir && l === 'usb' && ['', '192.168.4.1', '127.0.0.1'].includes(h.value.trim())) h.value = 'auto';
  if (remplir && l === 'wifi' && (h.value.trim() === 'auto' || /^COM\d+$/i.test(h.value.trim()) || h.value.startsWith('/dev/'))) h.value = '192.168.4.1';
  if (l === 'usb') lire('/api/ports').then((r) => { $('liste-ports').innerHTML = r.ports.map((p) => `<option value="${p.port}">${p.description}</option>`).join('') + '<option value="auto">auto</option>'; }).catch(() => {});
}
for (const b of document.querySelectorAll('#seg-liaison button')) b.onclick = () => choisirLiaison(b.dataset.liaison);
function ouvrirPop(oui) { pop.hidden = !oui; $('puce-connexion').setAttribute('aria-expanded', String(oui)); }
$('puce-connexion').onclick = (e) => { e.stopPropagation(); ouvrirPop(pop.hidden); };
document.addEventListener('click', (e) => { if (!pop.contains(e.target) && e.target !== $('puce-connexion')) ouvrirPop(false); });
$('bouton-connexion').onclick = async () => {
  if (etat && etat.connexion !== 'hors_ligne') { await agir(appel('/api/deconnexion')); return; }
  const r = await agir(appel('/api/connexion', { liaison, hote: $('hote').value }));
  if (r) ouvrirPop(false);
};
$('reco-auto').onchange = (e) => agir(appel('/api/reglages', { reconnexion_auto: e.target.checked }));
const salles = () => Array.from(document.querySelectorAll('.choix-salle'));
function remplirSalles(e) {
  if (!e.salles || salles()[0].options.length === e.salles.length) return;
  let memo = null; try { memo = localStorage.getItem('salle-demo'); } catch (_) { /* stockage indisponible */ }
  for (const s of salles()) s.replaceChildren(...e.salles.map((x) => new Option(x.titre, x.id, false, x.id === memo)));
}
function salleChoisie() { const s = salles()[0]; return s ? s.value : undefined; }
for (const s of salles()) s.onchange = () => {
  for (const autre of salles()) autre.value = s.value;
  try { localStorage.setItem('salle-demo', s.value); } catch (_) { /* facultatif */ }
};
$('bouton-demo').onclick = () => { ouvrirPop(false); agir(appel('/api/demo', { actif: !(etat && etat.demo), salle: salleChoisie() })); };
$('accueil-connecter').onclick = () => { ouvrirPop(true); $('hote').focus(); };
$('accueil-demo').onclick = () => agir(appel('/api/demo', { actif: true, salle: salleChoisie() }));

function majConnexion(e) {
  etat = e;
  const v = $('voyant'), t = $('puce-texte');
  const textes = { hors_ligne: 'Hors connexion', connexion: 'Connexion…', connecte: e.demo ? 'Robot simulé' : (e.liaison === 'usb' ? 'Robot · USB' : 'Robot · Wi-Fi'),
                   attente: e.reconnexion ? `Reconnexion dans ${Math.ceil(e.reconnexion.restant)} s` : 'Reconnexion…' };
  v.className = 'voyant ' + (e.connexion === 'connecte' ? 'connecte' : e.connexion === 'connexion' ? 'connexion' : e.connexion === 'attente' ? 'attente' : '');
  t.textContent = textes[e.connexion];
  const actif = e.connexion !== 'hors_ligne';
  $('bouton-connexion').textContent = actif ? 'Déconnecter' : 'Connecter'; $('bouton-connexion').classList.toggle('primaire', !actif);
  remplirSalles(e);
  for (const s of salles()) { s.disabled = !!e.demo; if (e.demo && e.salle_demo) s.value = e.salle_demo; }
  $('champ-salle').hidden = actif && !e.demo;
  $('bouton-demo').textContent = e.demo ? 'Quitter la démonstration' : 'Essayer avec un robot simulé';
  $('reco-auto').checked = e.reglages.reconnexion_auto;
  if (!pop.matches(':focus-within') && !actif) { if (e.liaison !== liaison) choisirLiaison(e.liaison, false); if (document.activeElement !== $('hote')) $('hote').value = e.hote; }
  direct.etat(e); carte.etat(e);
}

// ---- bandeau : dernier message grave ou d'état
let effacement = null;
function bandeau(texte, grave) {
  const b = $('bandeau'); b.textContent = texte; b.className = 'bandeau' + (grave ? ' grave' : ''); b.hidden = !texte;
  clearTimeout(effacement); if (texte) effacement = setTimeout(() => { b.hidden = true; }, grave ? 9000 : 5000);
}

ecouter({
  etat: majConnexion,
  scan: (s) => direct.scan(s),
  carte: (c) => direct.carte(c),
  auto: (d) => direct.auto(d),
  document: () => carte.document(),
  tache: (t) => carte.tache(t),
  message: (m) => bandeau(m.texte, m.grave),
  messages: () => {},
  coupe: () => bandeau('Le serveur ScanAtlas ne répond plus. Relance l’application.', true),
  ouvert: () => bandeau('', false),
});

if (!location.hash) location.hash = '#direct';
afficher();

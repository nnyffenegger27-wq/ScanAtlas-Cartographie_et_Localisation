// Échanges avec le serveur local : ordres JSON, lecture, flux d'événements, petites notifications.
export const jeton = document.querySelector('meta[name=jeton]').content;

async function reponse(r) {
  let donnees = {};
  try { donnees = await r.json(); } catch { /* corps vide */ }
  if (!r.ok) throw new Error(donnees.erreur || `Erreur ${r.status}`);
  return donnees;
}

export function appel(chemin, corps = {}) {
  return fetch(chemin, { method: 'POST', headers: { 'X-Jeton': jeton, 'Content-Type': 'application/json' }, body: JSON.stringify(corps) }).then(reponse);
}
export function lire(chemin) {
  return fetch(chemin, { headers: { 'X-Jeton': jeton } }).then(reponse);
}
export function envoyerFichier(nom, fichier) {
  return fetch('/api/carte/importer?nom=' + encodeURIComponent(nom), { method: 'POST', headers: { 'X-Jeton': jeton }, body: fichier }).then(reponse);
}
export const lienSession = () => '/api/carte/session?jeton=' + encodeURIComponent(jeton);
export const lienScan = (i) => `/api/carte/scan/${i}.csv?jeton=${encodeURIComponent(jeton)}`;

export function ecouter(gestionnaires) {
  const flux = new EventSource('/api/flux?jeton=' + encodeURIComponent(jeton));
  for (const [genre, f] of Object.entries(gestionnaires)) {
    flux.addEventListener(genre, (e) => { try { f(JSON.parse(e.data)); } catch (err) { console.error(genre, err); } });
  }
  flux.onopen = () => gestionnaires.ouvert && gestionnaires.ouvert();
  flux.onerror = () => gestionnaires.coupe && gestionnaires.coupe();
  return flux;
}

export function toast(texte, grave = false) {
  const zone = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast' + (grave ? ' grave' : '');
  el.textContent = texte;
  zone.appendChild(el);
  setTimeout(() => el.remove(), grave ? 7000 : 4200);
}

// Exécute un ordre et montre l'erreur éventuelle plutôt que de la perdre.
export async function agir(promesse) {
  try { return await promesse; } catch (e) { toast(e.message, true); return null; }
}

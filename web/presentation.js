// Navigation documentaire uniquement : aucun accès au transport ni aux commandes du robot.
const liens=[...document.querySelectorAll('.chapitres a')];
const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){for(const a of liens){if(a.hash==='#'+e.target.id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');}}},{rootMargin:'-15% 0px -65% 0px'});
for(const section of document.querySelectorAll('.chapitre'))observer.observe(section);
document.querySelector('#filtre-reference').addEventListener('change',e=>{for(const row of document.querySelectorAll('tr[data-reference]'))row.hidden=e.target.value!=='toutes'&&row.dataset.reference!==e.target.value;});
const dialog=document.querySelector('#image-dialog');let origine;
for(const b of document.querySelectorAll('[data-image]'))b.addEventListener('click',()=>{origine=b;document.querySelector('#image-grande').src=b.dataset.image;document.querySelector('#image-grande').alt=b.querySelector('img').alt;document.querySelector('#image-legende').textContent=b.dataset.legende;dialog.showModal();});
document.querySelector('#fermer-image').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
dialog.addEventListener('close',()=>origine?.focus());
document.querySelector('#imprimer').addEventListener('click',()=>window.print());

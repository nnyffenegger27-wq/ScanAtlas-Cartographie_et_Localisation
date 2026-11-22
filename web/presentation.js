// Navigation documentaire uniquement : aucun accès au transport ni aux commandes du robot.
const liens=[...document.querySelectorAll('.chapitres a')];
const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){for(const a of liens){if(a.hash==='#'+e.target.id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');}}},{rootMargin:'-15% 0px -65% 0px'});
for(const section of document.querySelectorAll('.chapitre'))observer.observe(section);
document.querySelector('#filtre-reference').addEventListener('change',e=>{for(const row of document.querySelectorAll('tr[data-reference],.ligne-comparaison[data-reference]'))row.hidden=e.target.value!=='toutes'&&row.dataset.reference!==e.target.value;});
const dialog=document.querySelector('#image-dialog');let origine;
for(const b of document.querySelectorAll('[data-image]'))b.addEventListener('click',()=>{origine=b;document.querySelector('#image-grande').src=b.dataset.image;document.querySelector('#image-grande').alt=b.querySelector('img').alt;document.querySelector('#image-legende').textContent=b.dataset.legende;dialog.showModal();});
document.querySelector('#fermer-image').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
dialog.addEventListener('close',()=>origine?.focus());
document.querySelector('#imprimer').addEventListener('click',()=>window.print());

// Repères de lecture ; désactivables nativement via les préférences de mouvement.
const barre=document.querySelector('.presentation-barre');
new ResizeObserver(()=>document.body.style.setProperty('--hauteur-barre',barre.offsetHeight+'px')).observe(barre);
let attenteLecture=false;
function progression(){const total=document.documentElement.scrollHeight-innerHeight;document.querySelector('.progression-lecture span').style.width=(total>0?Math.max(0,Math.min(100,scrollY/total*100)):0)+'%';attenteLecture=false;}
addEventListener('scroll',()=>{if(!attenteLecture){attenteLecture=true;requestAnimationFrame(progression);}},{passive:true});
addEventListener('resize',progression);progression();
// À l'impression, les étapes sont toutes développées, puis l'état de lecture est restauré.
let replis=[];
addEventListener('beforeprint',()=>{replis=[...document.querySelectorAll('details')].filter(d=>!d.open);for(const d of replis)d.open=true;});
addEventListener('afterprint',()=>{for(const d of replis)d.open=false;replis=[];});

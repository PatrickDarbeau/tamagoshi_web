const POLL_MS = 3000;

const grille = document.getElementById('animaux-grid');
const template = document.getElementById('tpl-animal');
const inventaireEl = document.getElementById('inventaire');
const btnRecolter = document.getElementById('btn-recolter');
const clockEl = document.getElementById('clock');
const clockIcon = document.getElementById('clock-icon');
const clockText = document.getElementById('clock-text');
const toastsEl = document.getElementById('toasts');
const formCreer = document.getElementById('form-creer-animal');
const inputNom = document.getElementById('input-nom');
const btnPause = document.getElementById('btn-pause');
const inputVitesse = document.getElementById('input-vitesse');
const vitesseValeurEl = document.getElementById('vitesse-valeur');
const btnReset = document.getElementById('btn-reset');
const btnAide = document.getElementById('btn-aide');
const aideOverlay = document.getElementById('aide-overlay');
const btnAideFermer = document.getElementById('btn-aide-fermer');

const STAGE_LABELS = {
  oeuf: '🥚 Œuf',
  bebe: '👶 Bébé',
  ado: '🧒 Ado',
  adulte: '🦖 Adulte',
};

const elements = new Map(); // id -> {root, refs}
let dernierEtat = null;
let recolteRestant = 0;

function formaterHorodatage(iso) {
  const d = new Date(iso);
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function toast(message) {
  const estObjet = typeof message === 'object' && message !== null;
  const texte = estObjet ? message.texte : message;

  const el = document.createElement('div');
  el.className = 'toast';

  const texteEl = document.createElement('div');
  texteEl.className = 'toast-texte';
  texteEl.textContent = texte;
  el.appendChild(texteEl);

  if (estObjet && message.horodatage) {
    const heureEl = document.createElement('div');
    heureEl.className = 'toast-heure';
    heureEl.textContent = formaterHorodatage(message.horodatage);
    el.appendChild(heureEl);
  }

  toastsEl.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

async function appelApi(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    toast(data.erreur || "Une erreur est survenue.");
    return null;
  }
  return data;
}

function labelDuree(secondes) {
  return secondes > 0 ? ` (${secondes}s)` : '';
}

function formaterVitesse(valeur) {
  return 'x' + parseFloat(valeur).toFixed(2).replace(/\.?0+$/, '');
}

function calculerMood(animal, estNuit) {
  if (!animal.vivant) return 'mort';
  if (animal.stage === 'oeuf') return 'neutre';
  if (animal.sante < 35) return 'sick';
  if (animal.proprete >= 55) return 'dirty';
  if (estNuit) return 'sleeping';
  if (animal.humeur < 35) return 'sad';
  return 'happy';
}

function creerCarte(animal) {
  const frag = template.content.cloneNode(true);
  const root = frag.querySelector('.device');
  const refs = {
    root,
    nom: frag.querySelector('.nom'),
    stageBadge: frag.querySelector('.stage-badge'),
    age: frag.querySelector('.age'),
    poopLayer: frag.querySelector('.poop-layer'),
    fills: {
      sante: frag.querySelector('.fill-sante'),
      humeur: frag.querySelector('.fill-humeur'),
      faim: frag.querySelector('.fill-faim'),
      soif: frag.querySelector('.fill-soif'),
      proprete: frag.querySelector('.fill-proprete'),
    },
    actions: frag.querySelector('.actions'),
    feedPicker: frag.querySelector('.feed-picker'),
    boutons: {},
  };
  frag.querySelectorAll('.actions button').forEach((btn) => {
    refs.boutons[btn.dataset.action] = btn;
  });

  refs.boutons.nourrir.addEventListener('click', () => {
    refs.feedPicker.classList.toggle('open');
    renderFeedPicker(animal.id, refs);
  });
  refs.boutons.soigner.addEventListener('click', () => faireAction(animal.id, 'soigner', refs));
  refs.boutons.caresser.addEventListener('click', () => faireAction(animal.id, 'caresser', refs));
  refs.boutons.nettoyer.addEventListener('click', () => faireAction(animal.id, 'nettoyer', refs));
  refs.boutons.supprimer.addEventListener('click', () => faireAction(animal.id, 'supprimer', refs));

  grille.appendChild(frag);
  elements.set(animal.id, refs);
  return refs;
}

async function faireAction(id, action, refs) {
  if (action === 'supprimer') {
    const data = await appelApi(`/api/animaux/${id}/supprimer`, { method: 'POST' });
    if (data) appliquerEtat(data);
    return;
  }
  const data = await appelApi(`/api/animaux/${id}/${action}`, { method: 'POST' });
  if (!data) return;
  if (action === 'nourrir') flashMood(refs, 'mood-eating');
  if (action === 'caresser') flashMood(refs, 'mood-petted');
  appliquerEtat(data);
}

function flashMood(refs, classe) {
  refs.root.classList.add(classe);
  setTimeout(() => refs.root.classList.remove(classe), 900);
}

function renderFeedPicker(animalId, refs) {
  const provisions = (dernierEtat && dernierEtat.provisions) || [];
  refs.feedPicker.innerHTML = '';
  if (provisions.length === 0) {
    refs.feedPicker.innerHTML = '<span class="empty">Aucune provision. Cherchez-en !</span>';
    return;
  }
  provisions.forEach((groupe) => {
    const btn = document.createElement('button');
    btn.textContent = `${groupe.emoji} ${groupe.nom} ×${groupe.count}`;
    btn.addEventListener('click', async () => {
      const item = trouverProvisionParType(groupe.type);
      if (!item) return;
      const data = await appelApi(`/api/animaux/${animalId}/nourrir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provision_id: item.id }),
      });
      refs.feedPicker.classList.remove('open');
      if (!data) return;
      flashMood(refs, 'mood-eating');
      appliquerEtat(data);
    });
    refs.feedPicker.appendChild(btn);
  });
}

function trouverProvisionParType(type) {
  // Chaque groupe agrégé garde l'id d'un item réel de ce type en stock.
  const groupe = dernierEtat.provisions.find((p) => p.type === type);
  return groupe ? { id: groupe.id, type } : null;
}

function mettreAJourCarte(animal, refs, estNuit) {
  refs.nom.textContent = animal.nom;
  refs.stageBadge.textContent = STAGE_LABELS[animal.stage] || animal.stage;
  refs.stageBadge.className = 'stage-badge stage-badge-' + animal.stage;
  refs.age.textContent = animal.stage === 'oeuf' ? '' : `${animal.age_jours.toFixed(1)}j`;

  Object.entries(refs.fills).forEach(([cle, el]) => {
    el.style.width = `${animal[cle]}%`;
  });

  refs.poopLayer.innerHTML = '';
  if (animal.proprete >= 40) {
    const nb = animal.proprete >= 80 ? 3 : animal.proprete >= 55 ? 2 : 1;
    for (let i = 0; i < nb; i++) {
      const s = document.createElement('span');
      s.className = 'poop';
      s.textContent = '💩';
      refs.poopLayer.appendChild(s);
    }
  }

  const mood = calculerMood(animal, estNuit);
  refs.root.className = 'device stage-' + animal.stage + (estNuit ? ' nuit' : '');
  refs.root.classList.add(
    mood === 'mort' ? 'mood-mort' : `mood-${mood}`
  );
  if (!animal.vivant) refs.root.classList.add('mort');

  const restants = animal.cooldowns_restants || {};
  Object.entries(refs.boutons).forEach(([action, btn]) => {
    if (action === 'supprimer') return;
    const secondes = restants[action] || 0;
    btn.disabled = secondes > 0 || !animal.vivant;
    const base = btn.dataset.label || btn.textContent.replace(/\s*\(\d+s\)$/, '');
    btn.dataset.label = base;
    btn.textContent = base + labelDuree(secondes);
  });
  if (animal.vivant && refs.feedPicker.classList.contains('open')) {
    renderFeedPicker(animal.id, refs);
  }
}

function appliquerEtat(data) {
  dernierEtat = data;

  clockEl.classList.toggle('night', data.est_nuit);
  clockIcon.textContent = data.est_nuit ? '🌙' : '☀️';
  const heure = Math.floor(data.heure_du_jour);
  const minute = Math.round((data.heure_du_jour % 1) * 60);
  clockText.textContent = `Jour ${data.jour} · ${String(heure).padStart(2, '0')}h${String(minute).padStart(2, '0')}`;

  if (data.provisions.length === 0) {
    inventaireEl.innerHTML = '<span class="empty">Aucune provision. Partez en chercher !</span>';
  } else {
    inventaireEl.innerHTML = '';
    data.provisions.forEach((p) => {
      const el = document.createElement('div');
      el.className = 'item';
      el.textContent = `${p.emoji} ${p.nom} ×${p.count}`;
      inventaireEl.appendChild(el);
    });
  }
  recolteRestant = data.recolte_dans || 0;
  majBoutonRecolte();

  btnPause.textContent = data.en_pause ? '▶️ Reprendre' : '⏸️ Pause';
  btnPause.classList.toggle('confirm', !!data.en_pause);
  if (document.activeElement !== inputVitesse) {
    inputVitesse.value = data.vitesse;
  }
  vitesseValeurEl.textContent = formaterVitesse(data.vitesse);

  const idsVus = new Set();
  data.animaux.forEach((animal) => {
    idsVus.add(animal.id);
    const refs = elements.get(animal.id) || creerCarte(animal);
    mettreAJourCarte(animal, refs, data.est_nuit);
  });
  [...elements.keys()].forEach((id) => {
    if (!idsVus.has(id)) {
      elements.get(id).root.remove();
      elements.delete(id);
    }
  });

  (data.messages || []).forEach(toast);
}

function majBoutonRecolte() {
  btnRecolter.disabled = recolteRestant > 0;
  const base = '🔎 Chercher des provisions';
  btnRecolter.textContent = base + labelDuree(recolteRestant);
}

setInterval(() => {
  if (recolteRestant > 0) {
    recolteRestant -= 1;
    majBoutonRecolte();
  }
}, 1000);

async function rafraichir() {
  const data = await appelApi('/api/state');
  if (data) appliquerEtat(data);
}

formCreer.addEventListener('submit', async (e) => {
  e.preventDefault();
  const nom = inputNom.value.trim();
  if (!nom) return;
  const data = await appelApi('/api/animaux', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nom }),
  });
  if (data) {
    appliquerEtat(data);
    inputNom.value = '';
  }
});

btnRecolter.addEventListener('click', async () => {
  const data = await appelApi('/api/provisions/recolter', { method: 'POST' });
  if (data) appliquerEtat(data);
});

btnPause.addEventListener('click', async () => {
  const enPause = !(dernierEtat && dernierEtat.en_pause);
  const data = await appelApi('/api/pause', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ en_pause: enPause }),
  });
  if (data) appliquerEtat(data);
});

inputVitesse.addEventListener('input', () => {
  vitesseValeurEl.textContent = formaterVitesse(inputVitesse.value);
});

inputVitesse.addEventListener('change', async () => {
  const data = await appelApi('/api/vitesse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ valeur: parseFloat(inputVitesse.value) }),
  });
  if (data) appliquerEtat(data);
});

let resetArme = false;
let resetTimeoutId = null;
btnReset.addEventListener('click', async () => {
  if (!resetArme) {
    resetArme = true;
    btnReset.textContent = '⚠️ Confirmer ?';
    btnReset.classList.add('confirm');
    resetTimeoutId = setTimeout(() => {
      resetArme = false;
      btnReset.textContent = '🔄 Réinitialiser';
      btnReset.classList.remove('confirm');
    }, 4000);
    return;
  }
  clearTimeout(resetTimeoutId);
  resetArme = false;
  btnReset.textContent = '🔄 Réinitialiser';
  btnReset.classList.remove('confirm');
  const data = await appelApi('/api/reinitialiser', { method: 'POST' });
  if (data) appliquerEtat(data);
});

function ouvrirAide() {
  aideOverlay.classList.add('open');
}
function fermerAide() {
  aideOverlay.classList.remove('open');
}
btnAide.addEventListener('click', ouvrirAide);
btnAideFermer.addEventListener('click', fermerAide);
aideOverlay.addEventListener('click', (e) => {
  if (e.target === aideOverlay) fermerAide();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && aideOverlay.classList.contains('open')) fermerAide();
});

rafraichir();
setInterval(rafraichir, POLL_MS);

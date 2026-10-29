// Lecteur audio persistant + navigation sans rechargement (le son continue d'une page à l'autre).
(function () {
  const audio = new Audio();
  audio.preload = 'metadata';
  const $ = (s, el = document) => el.querySelector(s);
  const lecteur = $('.lecteur');
  const ui = {
    titre: $('.l-titre'), sous: $('.l-sous'), play: $('.l-play'),
    prec: $('.l-prec'), suiv: $('.l-suiv'), recul: $('.l-recul'), avance: $('.l-avance'),
    barre: $('.l-barre input'), cur: $('.l-cur'), tot: $('.l-tot'),
    vitesse: $('.l-vitesse'), dl: $('.l-dl'),
  };
  const VITESSES = [1, 1.25, 1.5, 1.75, 2, 0.75];
  let file = [], position = -1;

  const stockage = {
    lire(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    ecrire(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };

  function temps(s) {
    if (!isFinite(s)) return '0:00';
    s = Math.floor(s);
    const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, sec = String(s % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
  }

  function episodeDepuis(el) {
    return { src: el.dataset.src, titre: el.dataset.titre, sous: el.dataset.sous || '' };
  }

  function icone(nom) { return `<svg width="18" height="18"><use href="#i-${nom}"/></svg>`; }

  function majUI() {
    const ep = file[position];
    if (!ep) return;
    document.body.classList.add('avec-lecteur');
    ui.titre.textContent = ep.titre;
    ui.sous.textContent = ep.sous;
    ui.dl.href = ep.src;
    ui.prec.disabled = position <= 0;
    ui.suiv.disabled = position >= file.length - 1;
    marquerEnCours();
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: ep.titre, artist: 'Yacine Abou Sirine', album: ep.sous });
    }
  }

  function marquerEnCours() {
    const src = file[position] && file[position].src;
    document.querySelectorAll('[data-src]').forEach(el => el.classList.toggle('en-cours', el.dataset.src === src));
  }

  function jouer(liste, i, depuis = 0) {
    file = liste; position = i;
    audio.src = file[i].src;
    audio.currentTime = depuis;
    audio.playbackRate = Number(ui.vitesse.dataset.v || 1);
    audio.play().catch(() => {});
    majUI();
    sauver();
  }

  function sauver() {
    if (!file[position]) return;
    stockage.ecrire('lecteur', { file, position, t: audio.currentTime || 0 });
  }

  // Clic sur un épisode : la file d'attente = la liste qui le contient.
  document.addEventListener('click', e => {
    if (e.target.closest('a')) return; // téléchargement ou lien vers la rubrique
    const el = e.target.closest('[data-src]');
    if (!el) return;
    e.preventDefault();
    if (file[position] && file[position].src === el.dataset.src) { basculer(); return; }
    const conteneur = el.closest('[data-file]');
    const els = conteneur ? [...conteneur.querySelectorAll('[data-src]')] : [el];
    jouer(els.map(episodeDepuis), els.indexOf(el));
  });

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-tout-ecouter]');
    if (!b) return;
    const els = [...document.querySelectorAll(b.dataset.toutEcouter + ' [data-src]')];
    if (els.length) jouer(els.map(episodeDepuis), 0);
  });

  function basculer() { audio.paused ? audio.play().catch(() => {}) : audio.pause(); }
  ui.play.addEventListener('click', basculer);
  ui.prec.addEventListener('click', () => position > 0 && jouer(file, position - 1));
  ui.suiv.addEventListener('click', () => position < file.length - 1 && jouer(file, position + 1));
  ui.recul.addEventListener('click', () => { audio.currentTime = Math.max(0, audio.currentTime - 15); });
  ui.avance.addEventListener('click', () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 15); });
  ui.vitesse.addEventListener('click', () => {
    const v = VITESSES[(VITESSES.indexOf(Number(ui.vitesse.dataset.v || 1)) + 1) % VITESSES.length];
    ui.vitesse.dataset.v = v; ui.vitesse.textContent = v + '×'; audio.playbackRate = v;
  });
  ui.barre.addEventListener('input', () => { if (audio.duration) audio.currentTime = ui.barre.value / 1000 * audio.duration; });

  audio.addEventListener('play', () => { ui.play.innerHTML = icone('pause'); ui.play.setAttribute('aria-label', 'Pause'); });
  audio.addEventListener('pause', () => { ui.play.innerHTML = icone('play'); ui.play.setAttribute('aria-label', 'Lecture'); sauver(); });
  audio.addEventListener('loadedmetadata', () => { ui.tot.textContent = temps(audio.duration); });
  let dernier = 0;
  audio.addEventListener('timeupdate', () => {
    ui.cur.textContent = temps(audio.currentTime);
    if (audio.duration) ui.barre.value = audio.currentTime / audio.duration * 1000;
    if (Date.now() - dernier > 5000) { dernier = Date.now(); sauver(); }
  });
  audio.addEventListener('ended', () => { if (position < file.length - 1) jouer(file, position + 1); });

  if ('mediaSession' in navigator) {
    navigator.mediaSession.setActionHandler('play', () => audio.play());
    navigator.mediaSession.setActionHandler('pause', () => audio.pause());
    navigator.mediaSession.setActionHandler('previoustrack', () => ui.prec.click());
    navigator.mediaSession.setActionHandler('nexttrack', () => ui.suiv.click());
    navigator.mediaSession.setActionHandler('seekbackward', () => ui.recul.click());
    navigator.mediaSession.setActionHandler('seekforward', () => ui.avance.click());
  }

  // Reprise de la dernière écoute (sans lancer le son automatiquement).
  const repris = stockage.lire('lecteur');
  if (repris && repris.file && repris.file[repris.position]) {
    file = repris.file; position = repris.position;
    audio.src = file[position].src;
    audio.addEventListener('loadedmetadata', function une() {
      audio.currentTime = repris.t || 0; audio.removeEventListener('loadedmetadata', une);
    });
    majUI();
  }

  // --- Navigation interne sans rechargement ---
  async function naviguer(url, pousser = true) {
    let reponse;
    try { reponse = await fetch(url); } catch (e) { location.href = url; return; }
    if (!reponse.ok) { location.href = url; return; }
    const doc = new DOMParser().parseFromString(await reponse.text(), 'text/html');
    const nouveau = doc.querySelector('main');
    if (!nouveau) { location.href = url; return; }
    document.querySelector('main').replaceWith(nouveau);
    document.title = doc.title;
    document.querySelectorAll('.nav-links a').forEach((a, i) => {
      const b = doc.querySelectorAll('.nav-links a')[i];
      b && b.hasAttribute('aria-current') ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
    });
    $('header.entete').classList.remove('ouvert');
    if (pousser) history.pushState({}, '', url);
    const ancre = new URL(url, location.href).hash;
    if (ancre && document.querySelector(ancre)) document.querySelector(ancre).scrollIntoView();
    else window.scrollTo(0, 0);
    initPage();
  }

  document.addEventListener('click', e => {
    const a = e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || a.target || a.hasAttribute('download')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || /\.(mp3|json|xml)$/i.test(url.pathname)) return;
    if (url.pathname === location.pathname && url.hash) return; // ancre sur la même page
    e.preventDefault();
    naviguer(url.href);
  });
  window.addEventListener('popstate', () => naviguer(location.href, false));

  document.addEventListener('submit', e => {
    const f = e.target.closest('form[data-recherche]');
    if (!f) return;
    e.preventDefault();
    const q = new FormData(f).get('q') || '';
    naviguer(f.action + '?q=' + encodeURIComponent(q));
  });

  $('.menu-btn').addEventListener('click', () => {
    const h = $('header.entete');
    h.classList.toggle('ouvert');
    $('.menu-btn').setAttribute('aria-expanded', h.classList.contains('ouvert'));
  });

  document.addEventListener('keydown', e => {
    if (e.key === '/' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      const champ = $('.recherche-entete input');
      if (champ && champ.offsetParent) { e.preventDefault(); champ.focus(); }
    }
  });

  // --- Comportements propres à chaque page ---
  function initPage() {
    marquerEnCours();
    document.querySelectorAll('.onglets').forEach(groupe => {
      groupe.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
        groupe.querySelectorAll('button').forEach(x => x.setAttribute('aria-selected', x === b));
        document.querySelectorAll(groupe.dataset.onglets).forEach(o => { o.hidden = o.id !== b.dataset.cible; });
      }));
    });
    const zone = $('#resultats');
    if (zone) initRecherche(zone);
  }

  // --- Recherche ---
  let index = null;
  const normaliser = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const echapper = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  async function initRecherche(zone) {
    const champ = $('#q');
    const q = new URLSearchParams(location.search).get('q') || '';
    champ.value = q;
    if (!index) {
      zone.innerHTML = '<p class="resultat-info">Chargement…</p>';
      index = await (await fetch(zone.dataset.index)).json();
      index.forEach(e => { e.n = normaliser(e.t + ' ' + e.s); });
    }
    const afficher = () => {
      const mots = normaliser(champ.value.trim()).split(/\s+/).filter(Boolean);
      history.replaceState({}, '', location.pathname + (champ.value ? '?q=' + encodeURIComponent(champ.value) : ''));
      if (!mots.length) { zone.innerHTML = `<p class="resultat-info">${index.length} audios disponibles. Tapez un mot : sourate, thème, titre…</p>`; return; }
      const trouves = index.filter(e => mots.every(m => e.n.includes(m)));
      const surligner = t => {
        let r = echapper(t);
        mots.forEach(m => {
          const re = new RegExp('(' + m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').split('').map(c => c + '[\\u0300-\\u036f]*').join('') + ')', 'gi');
          r = r.normalize('NFD').replace(re, '<mark>$1</mark>').normalize('NFC');
        });
        return r;
      };
      zone.innerHTML = `<p class="resultat-info">${trouves.length} résultat${trouves.length > 1 ? 's' : ''}</p>` +
        (trouves.length ? `<div class="carte-liste"><ul class="episodes" data-file>${trouves.slice(0, 200).map(e => `
          <li class="ep" data-src="${echapper(e.u)}" data-titre="${echapper(e.t)}" data-sous="${echapper(e.s)}">
            <button class="ep-play" aria-label="Écouter"><svg width="14" height="14"><use href="#i-play"/></svg></button>
            <div class="ep-texte"><div class="ep-titre">${surligner(e.t)}</div><div class="ep-sous"><a href="${echapper(e.p)}">${echapper(e.s)}</a></div></div>
            <div class="ep-meta">${e.d || ''}</div>
          </li>`).join('')}</ul></div>` : '');
      marquerEnCours();
    };
    champ.oninput = afficher;
    afficher();
    if (!q) champ.focus();
  }

  initPage();
})();

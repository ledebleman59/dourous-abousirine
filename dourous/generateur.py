"""Génération du site statique (dossier dist/) à partir du catalogue."""
import json
import math
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from .catalogue import construire_arbre, tous_les_episodes, url_audio

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

LIENS = {
    "youtube": "https://www.youtube.com/YacineAbouSirine",
    "telegram": "https://t.me/dourous_abousirine",
    "instagram": "https://www.instagram.com/yacineabousirine/",
    "spotify": "https://open.spotify.com/show/0JA0wI3v30Oyo11yWtx08C",
    "apple": "https://podcasts.apple.com/fr/podcast/dourous-abou-sirine/id1484087850",
    "sadaqa": "https://sadaqaharamain.com/",
    "alsirate": "https://www.alsiratevoyage.com/",
    "contact": "contact@dourous-abousirine.fr",
}
IMAGE_SADAQA = "https://www.dourous-abousirine.fr/images/2026/06/04/minaret.png"

# Icône de chaque rubrique, choisie d'après des mots de son chemin.
ICONES = [("tafsir", "book"), ("fiqh", "scale"), ("croyance", "star"), ("rappels", "scroll"),
          ("hajj", "plane"), ("prophetes", "scroll"), ("khutba", "mosque"),
          ("conferences", "mic"), ("enfants", "child")]


def e(texte):
    return escape(str(texte or ""), quote=True)


def format_duree(secondes):
    if not secondes:
        return ""
    minutes = round(secondes / 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def format_date(iso):
    if not iso:
        return ""
    a, m, j = (int(x) for x in iso.split("-"))
    return f"{j} {MOIS[m - 1]} {a}"


def icone(nom, taille=22):
    return f'<svg width="{taille}" height="{taille}" aria-hidden="true"><use href="#i-{nom}"/></svg>'


def icone_rubrique(r):
    from .catalogue import slugifier
    cle = slugifier(r["chemin"])
    for mot, ico in ICONES:
        if mot in cle:
            return ico
    return "book"


class Generateur:
    def __init__(self, fichiers, affichage, config, racine_projet):
        self.config = config
        self.base = "/" + config.get("chemin_site", "/").strip("/") + "/"
        self.base = self.base.replace("//", "/")
        self.audio_base = config["url_audio"]
        self.racine, self.index = construire_arbre(fichiers, affichage)
        self.projet = Path(racine_projet)
        self.sortie = self.projet / "dist"
        for ep in tous_les_episodes(self.racine):
            ep["url"] = url_audio(self.audio_base, ep["chemin"])

    # --- utilitaires ---
    def lien(self, url_relative=""):
        return self.base + url_relative

    def rubrique(self, chemin):
        return self.index.get(chemin)

    def sous_titre(self, ep):
        noms, chemin = [], ep["rubrique"]
        while chemin:
            r = self.index[chemin]
            noms.insert(0, r["nom"])
            chemin = r["parent"]
        return " · ".join(noms[-2:])

    def ep_attrs(self, ep):
        titre = ep["titre"]
        return (f'data-src="{e(ep["url"])}" data-titre="{e(titre)}" '
                f'data-sous="{e(self.sous_titre(ep))}"')

    def recents(self, rubrique, n):
        eps = sorted(tous_les_episodes(rubrique), key=lambda x: x.get("date") or "", reverse=True)
        return eps[:n]

    def nb(self, rubrique):
        return sum(1 for _ in tous_les_episodes(rubrique))

    # --- gabarit commun ---
    def page(self, titre, contenu, actif="", description=""):
        nav = [("", "Accueil"), ("cours/", "Cours"), ("khutba-joumou3a/", "Khutbas"),
               ("conferences/", "Conférences"), ("cours-enfants/", "Enfants"), ("#apropos", "À propos")]
        liens = "".join(
            f'<a href="{self.lien(u)}"{" aria-current=\"page\"" if u == actif else ""}>{n}</a>' for u, n in nav)
        liens_mobile = "".join(f'<a href="{self.lien(u)}">{n}</a>' for u, n in nav)
        titre_complet = f"{titre} · Dourous Abou Sirine" if titre else "Dourous Abou Sirine · Cours et khutbas de l'imam Yacine Abou Sirine"
        description = description or "Cours, khutbas et conférences de l'imam Yacine Abou Sirine, à écouter en ligne ou à télécharger gratuitement."
        recherche = self.lien("recherche/")
        return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre_complet)}</title>
<meta name="description" content="{e(description)}">
<meta property="og:title" content="{e(titre_complet)}">
<meta property="og:description" content="{e(description)}">
<meta name="theme-color" content="#f8f5ee">
<link rel="icon" href="{self.lien('static/favicon.svg')}" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=Amiri:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{self.lien('static/style.css')}?v={self.version}">
</head>
<body>
{SPRITE}
<header class="entete">
  <div class="wrap nav">
    <a class="brand" href="{self.lien()}"><span class="brand-mark">{icone("star", 18)}</span>Dourous Abou Sirine</a>
    <nav class="nav-links" aria-label="Navigation principale">{liens}</nav>
    <form class="recherche-entete" action="{recherche}" data-recherche role="search">
      {icone("search", 16)}<label class="sr" for="q-entete">Rechercher</label>
      <input id="q-entete" name="q" type="search" placeholder="Rechercher un cours, une sourate…">
    </form>
    <button class="menu-btn" aria-label="Menu" aria-expanded="false">{icone("menu", 24)}</button>
  </div>
  <div class="menu-mobile">{liens_mobile}
    <form action="{recherche}" data-recherche role="search"><input name="q" type="search" placeholder="Rechercher…" aria-label="Rechercher"></form>
  </div>
</header>
<main>
{contenu}
</main>
<footer class="pied">
  <div class="wrap">
    <div class="foot">
      <div>
        <div class="brand" style="margin-bottom:12px"><span class="brand-mark">{icone("star", 18)}</span> Dourous Abou Sirine</div>
        <p style="margin:0;max-width:300px">Cours et khutbas de l'imam Yacine Abou Sirine, à écouter et à partager librement.</p>
      </div>
      <div><h4>Écouter</h4><ul>
        <li><a href="{self.lien('cours/')}">Cours</a></li><li><a href="{self.lien('khutba-joumou3a/')}">Khutbas</a></li>
        <li><a href="{self.lien('conferences/')}">Conférences</a></li><li><a href="{self.lien('cours-enfants/')}">Cours enfants</a></li></ul></div>
      <div><h4>Suivre</h4><ul>
        <li><a href="{LIENS['youtube']}" target="_blank" rel="noopener">YouTube</a></li>
        <li><a href="{LIENS['telegram']}" target="_blank" rel="noopener">Telegram</a></li>
        <li><a href="{LIENS['instagram']}" target="_blank" rel="noopener">Instagram</a></li>
        <li><a href="{LIENS['spotify']}" target="_blank" rel="noopener">Spotify</a> · <a href="{LIENS['apple']}" target="_blank" rel="noopener">Apple Podcasts</a></li></ul></div>
      <div><h4>Partenaires</h4><ul>
        <li><a href="{LIENS['sadaqa']}" target="_blank" rel="noopener">Sadaqa Haramain</a></li>
        <li><a href="{LIENS['alsirate']}" target="_blank" rel="noopener">Al Sirate Voyage</a></li>
        <li><a href="mailto:{LIENS['contact']}">{LIENS['contact']}</a></li></ul></div>
    </div>
    <div class="copy">© {date.today().year} Dourous Abou Sirine · Tous droits réservés</div>
  </div>
</footer>
<div class="lecteur" aria-label="Lecteur audio">
  <div class="wrap">
    <div class="l-cover">{icone("mic", 20)}</div>
    <div class="l-info"><div class="l-titre"></div><div class="l-sous"></div></div>
    <div class="l-ctrl">
      <button class="l-prec l-saut" aria-label="Précédent">{icone("prev", 18)}</button>
      <button class="l-recul" aria-label="Reculer de 15 secondes">{icone("back")}</button>
      <button class="l-play" aria-label="Lecture">{icone("play", 18)}</button>
      <button class="l-avance" aria-label="Avancer de 15 secondes">{icone("fwd")}</button>
      <button class="l-suiv l-saut" aria-label="Suivant">{icone("next", 18)}</button>
    </div>
    <div class="l-barre"><span class="l-cur">0:00</span><input type="range" min="0" max="1000" value="0" aria-label="Position"><span class="l-tot">0:00</span></div>
    <div class="l-extra"><button class="l-vitesse" data-v="1" aria-label="Vitesse de lecture">1×</button><a class="l-dl" href="#" download aria-label="Télécharger">{icone("dl", 14)}</a></div>
  </div>
</div>
<script src="{self.lien('static/app.js')}?v={self.version}"></script>
</body>
</html>
"""

    # --- morceaux réutilisables ---
    def liste_episodes(self, eps, numeros=False, colonnes=False, sous_titre=True, ident=""):
        lignes = []
        # Si tous les épisodes portent la même série (« Tafsir - Fatiha »), inutile de la répéter.
        series_communes = len({ep.get("serie") for ep in eps}) <= 1
        for ep in eps:
            num = f'<span class="ep-num">{ep["numero"]}</span>' if numeros and ep.get("numero") is not None else ""
            sous = []
            if sous_titre:
                sous.append(self.sous_titre(ep))
            elif ep.get("serie") and not series_communes:
                sous.append(ep["serie"])
            # Pas de date affichée : beaucoup de fichiers ont été renvoyés en bloc sur le serveur,
            # leur date FTP n'est donc pas celle du cours.
            meta = format_duree(ep.get("duree"))
            dl = "" if colonnes else (f'<a class="ep-dl" href="{e(ep["url"])}" download aria-label="Télécharger">'
                                      f'{icone("dl", 16)}</a>')
            lignes.append(f"""<li class="ep" {self.ep_attrs(ep)}>
  {num}<button class="ep-play" aria-label="Écouter">{icone("play", 14)}</button>
  <div class="ep-texte"><div class="ep-titre">{e(ep["titre"])}</div>{f'<div class="ep-sous">{e(" · ".join(sous))}</div>' if any(sous) else ""}</div>
  <div class="ep-meta">{meta}</div>{dl}
</li>""")
        classe = "episodes deux-colonnes" if colonnes else "episodes"
        return f'<ul class="{classe}" data-file{f" id={ident}" if ident else ""}>{"".join(lignes)}</ul>'

    def carte_theme(self, r):
        tags = "".join(f'<span class="tag">{e(s["nom"].split(" · ")[-1])}</span>' for s in r["rubriques"][:3])
        return f"""<a class="theme" href="{self.lien(r['url'])}">
  <div class="theme-tete"><span class="ico">{icone(icone_rubrique(r))}</span><span class="compte">{self.nb(r)} audios</span></div>
  <h3>{e(r['nom'])}</h3><p>{e(r.get('description'))}</p><div class="tags">{tags}</div></a>"""

    def carte_serie(self, r):
        m = re.match(r"^(\d+)\s*·\s*(.*)$", r["nom"])
        num, nom = (m.group(1), m.group(2)) if m else (icone(icone_rubrique(r), 22), r["nom"])
        n = self.nb(r)
        return (f'<a class="serie" href="{self.lien(r["url"])}"><span class="serie-num">{num}</span>'
                f'<div><h3>{e(nom)}</h3><span>{n} épisode{"s" if n > 1 else ""}</span></div></a>')

    # --- pages ---
    def page_accueil(self):
        khutbas = self.rubrique("Khutba joumou3a")
        a_la_une = self.recents(khutbas, 1)[0] if khutbas else self.recents(self.racine, 1)[0]
        autres = []
        for chemin, label in [("Cours", "Cours"), ("Conferences", "Conférence"), ("Cours Enfants", "Enfants")]:
            r = self.rubrique(chemin)
            if r:
                autres += [(label, ep) for ep in self.recents(r, 1)]

        direct = "".join(f'<li {self.ep_attrs(ep)}><small>{label}</small> {e(ep["titre"])}</li>' for label, ep in autres)

        themes_chemins = ["Cours/Tafsir", "Cours/Croyance", "Cours/Fiqh - Jurisprudence", "Cours/Rappels",
                          "Cours/Histoire des Prophètes", "Cours/Hajj", "Khutba joumou3a", "Conferences", "Cours Enfants"]
        themes = "".join(self.carte_theme(self.index[c]) for c in themes_chemins if c in self.index)

        onglets, panneaux = [], []
        for i, (chemin, label) in enumerate([("Cours", "Cours"), ("Khutba joumou3a", "Khutbas"),
                                             ("Conferences", "Conférences"), ("Cours Enfants", "Enfants")]):
            r = self.rubrique(chemin)
            if not r:
                continue
            ident = "recent-" + r["slug"]
            onglets.append(f'<button role="tab" aria-selected="{"true" if i == 0 else "false"}" data-cible="{ident}">{label}</button>')
            panneaux.append(f'<div class="onglet" id="{ident}"{"" if i == 0 else " hidden"}>'
                            f'{self.liste_episodes(self.recents(r, 8), colonnes=True)}</div>')

        tafsir = self.rubrique("Cours/Tafsir")
        series = ""
        if tafsir:
            choix = sorted(tafsir["rubriques"], key=lambda r: -self.nb(r))[:6]
            choix.sort(key=lambda r: tafsir["rubriques"].index(r))
            series = f"""<section>
  <div class="wrap">
    <div class="sec-head"><div><div class="eyebrow">Séries</div><h2>Tafsir, sourate par sourate</h2></div>
      <a class="lien-plus" href="{self.lien(tafsir['url'])}">Toutes les séries →</a></div>
    <div class="series">{"".join(self.carte_serie(r) for r in choix)}</div>
  </div>
</section>"""

        contenu = f"""<div class="hero">
  <div class="wrap hero-grid">
    <div>
      <div class="arabic">طلب العلم فريضة على كل مسلم</div>
      <h1>Apprendre sa religion, <em>un cours à la fois.</em></h1>
      <p>Khutbas, tafsir, fiqh, croyance et cours pour enfants, par l'imam Yacine Abou Sirine. {self.nb(self.racine)} audios à écouter en ligne ou à télécharger, gratuitement.</p>
      <div class="btns">
        <a class="btn btn-plein" href="#themes">{icone("play", 16)} Explorer les cours</a>
        <a class="btn btn-contour" href="#sadaqa">Sadaqa Haramain</a>
      </div>
    </div>
    <div class="carte-direct" data-file>
      <div class="label"><span class="dot"></span> Dernière khutba</div>
      <h3>{e(a_la_une['titre'])}</h3>
      <div class="meta">{e(self.sous_titre(a_la_une))}{' · ' + format_duree(a_la_une.get('duree')) if a_la_une.get('duree') else ''}</div>
      <div class="wave" aria-hidden="true">{''.join(f'<span style="height:{20 + abs(round(60 * math.sin(i * .7))) + (i * 37 % 20)}%"></span>' for i in range(48))}</div>
      <div class="direct-controles">
        <button class="play-lg" {self.ep_attrs(a_la_une)} aria-label="Écouter">{icone("play", 22)}</button>
        <span>Écouter maintenant</span>
      </div>
      <ul class="direct-liste">{direct}</ul>
    </div>
  </div>
</div>

<section id="themes">
  <div class="wrap">
    <div class="sec-head"><div><div class="eyebrow">Bibliothèque</div><h2>Parcourir par thème</h2></div>
      <a class="lien-plus" href="{self.lien('recherche/')}">Rechercher un audio →</a></div>
    <div class="themes">{themes}</div>
  </div>
</section>

<section class="bande" id="dernieres">
  <div class="wrap">
    <div class="sec-head"><div><div class="eyebrow">Nouveautés</div><h2>Derniers ajouts</h2></div>
      <div class="onglets" role="tablist" data-onglets="#dernieres .onglet">{"".join(onglets)}</div></div>
    {"".join(panneaux)}
  </div>
</section>

{series}

<section id="sadaqa"{' style="padding-top:0"' if series else ''}>
  <div class="wrap">
    <div class="sadaqa">
      <img src="{IMAGE_SADAQA}" alt="Le dôme vert de la mosquée du Prophète ﷺ à Médine" loading="lazy">
      <div>
        <h2>Sadaqa <span>Haramain</span><br>&amp; Dourous Abousirine</h2>
        <p><strong>Dourous Abou Sirine</strong> a le plaisir de vous présenter « Sadaqa Haramain » qui offre une opportunité unique aux donateurs de faire des Sadaqa à distance directement à <strong>Makkah et à Madinah</strong>.</p>
        <p>Vous pouvez offrir de l'eau, des repas, des exemplaires de Coran, un Ihram, une Omra pour un défunt...</p>
        <a class="btn btn-plein" href="{LIENS['sadaqa']}" target="_blank" rel="noopener">Découvrir l'association !</a>
      </div>
    </div>
  </div>
</section>

<section id="apropos" style="padding-top:0">
  <div class="wrap about">
    <div class="portrait">{icone("mosque", 48)}</div>
    <div>
      <div class="eyebrow">L'enseignant</div>
      <h2>Qui est Yacine Abou Sirine&nbsp;?</h2>
      <p>Originaire du nord de la France, Yacine Abou Sirine est imam et conférencier. Il a étudié en Égypte, où il a obtenu plusieurs certificats et diplômes en sciences islamiques.</p>
      <div class="roles">
        <div class="role"><span class="ico">{icone("mosque", 20)}</span><div><h3>Imam et conférencier</h3><p>Khutbas du vendredi, cours et conférences partout en France.</p></div></div>
        <div class="role"><span class="ico">{icone("heart", 20)}</span><div><h3>Président de l'association Al Fardh</h3><p>Lavages mortuaires bénévoles dans la région lilloise et partout en France, pour les hommes, les femmes et les fœtus à partir de 4 mois. L'association organise aussi des démonstrations gratuites dans toute la France.</p></div></div>
        <div class="role"><span class="ico">{icone("plane", 20)}</span><div><h3>Responsable des guides, Al Sirate Voyage</h3><p>Il accompagne les pèlerins à La Mecque et à Médine. <a href="{LIENS['alsirate']}" target="_blank" rel="noopener">Agence agréée omra et hajj depuis 2015 →</a></p></div></div>
      </div>
    </div>
  </div>
</section>"""
        return self.page("", contenu, actif="")

    def fil_ariane(self, r):
        morceaux, chemin = [], r["parent"]
        while chemin:
            p = self.index[chemin]
            morceaux.insert(0, f'<a href="{self.lien(p["url"])}">{e(p["nom"])}</a>')
            chemin = p["parent"]
        morceaux.insert(0, f'<a href="{self.lien()}">Accueil</a>')
        sep = '<span aria-hidden="true">/</span>'
        return f'<nav class="fil" aria-label="Fil d\'Ariane">{sep.join(morceaux)}</nav>'

    def page_rubrique(self, r):
        eps_tous = list(tous_les_episodes(r))
        duree = sum(ep.get("duree") or 0 for ep in eps_tous)
        stats = [f"<span><b>{len(eps_tous)}</b> audio{'s' if len(eps_tous) > 1 else ''}</span>"]
        if r["rubriques"]:
            stats.append(f"<span><b>{len(r['rubriques'])}</b> sous-rubrique{'s' if len(r['rubriques']) > 1 else ''}</span>")
        if duree:
            stats.append(f"<span><b>{format_duree(duree)}</b> d'écoute</span>")
        bouton = (f'<div class="btns"><button class="btn btn-plein" data-tout-ecouter="#episodes">{icone("play", 16)} '
                  f'Tout écouter</button></div>') if r["episodes"] else ""

        blocs = []
        if r["rubriques"]:
            series_numerotees = all(re.match(r"^\d+\s*·", s["nom"]) for s in r["rubriques"][:3])
            if series_numerotees or all(not s["rubriques"] for s in r["rubriques"]):
                cartes = "".join(self.carte_serie(s) for s in r["rubriques"])
                grille = f'<div class="series">{cartes}</div>'
            else:
                grille = f'<div class="themes">{"".join(self.carte_theme(s) for s in r["rubriques"])}</div>'
            titre_bloc = "Séries" if r["episodes"] else "Rubriques"
            blocs.append(f'<div class="bloc"><div class="wrap"><h2>{titre_bloc}</h2>{grille}</div></div>')
        if r["episodes"]:
            titre_bloc = f"Tous les audios" if r["rubriques"] else ("Épisodes" if r.get("tri") == "numero" else "Audios")
            liste = self.liste_episodes(r["episodes"], numeros=r.get("tri") == "numero", sous_titre=False, ident="episodes")
            blocs.append(f'<div class="bloc"><div class="wrap"><h2>{titre_bloc}</h2><div class="carte-liste">{liste}</div></div></div>')
        if r["rubriques"] and not r["episodes"]:
            recents = self.recents(r, 10)
            blocs.append(f'<div class="bloc"><div class="wrap"><h2>Derniers ajouts</h2><div class="carte-liste">'
                         f'{self.liste_episodes(recents)}</div></div></div>')

        contenu = f"""<div class="page-tete">
  <div class="wrap">
    {self.fil_ariane(r)}
    <div class="eyebrow">{e(self.index[r['parent']]['nom'] if r['parent'] else 'Rubrique')}</div>
    <h1>{e(r['nom'])}</h1>
    {f"<p>{e(r['description'])}</p>" if r.get('description') else ''}
    <div class="stats">{''.join(stats)}</div>
    {bouton}
  </div>
</div>
{''.join(blocs)}"""
        racine = r["url"].split("/")[0] + "/"
        return self.page(r["nom"], contenu, actif=racine,
                         description=r.get("description") or f"{r['nom']} : {len(eps_tous)} audios de l'imam Yacine Abou Sirine.")

    def page_recherche(self):
        contenu = f"""<div class="page-tete">
  <div class="wrap">
    {f'<nav class="fil"><a href="{self.lien()}">Accueil</a></nav>'}
    <h1>Rechercher</h1>
    <label class="champ-recherche">{icone("search", 20)}<span class="sr">Rechercher</span>
      <input id="q" type="search" placeholder="Fatiha, prière, ramadan, jour dernier…" autocomplete="off"></label>
  </div>
</div>
<div class="bloc"><div class="wrap"><div id="resultats" data-index="{self.lien('recherche.json')}?v={self.version}"></div></div></div>"""
        return self.page("Rechercher", contenu, actif="recherche/")

    def page_404(self):
        contenu = f"""<div class="page-tete" style="padding:80px 0">
  <div class="wrap"><div class="eyebrow">Erreur 404</div><h1>Cette page n'existe pas</h1>
  <p>Le lien est peut-être ancien. Vous pouvez rechercher l'audio ou revenir à l'accueil.</p>
  <div class="btns"><a class="btn btn-plein" href="{self.lien()}">Accueil</a><a class="btn btn-contour" href="{self.lien('recherche/')}">Rechercher</a></div></div>
</div>"""
        return self.page("Page introuvable", contenu)

    # --- écriture ---
    def ecrire(self, url_relative, html_page):
        chemin = self.sortie / url_relative / "index.html" if not url_relative.endswith(".html") else self.sortie / url_relative
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(html_page, encoding="utf-8")

    def construire(self):
        self.version = date.today().strftime("%Y%m%d")
        if self.sortie.exists():
            shutil.rmtree(self.sortie)
        self.sortie.mkdir()
        shutil.copytree(self.projet / "static", self.sortie / "static")

        self.ecrire("", self.page_accueil())
        nb_pages = 1
        for chemin, r in self.index.items():
            if chemin:
                self.ecrire(r["url"], self.page_rubrique(r))
                nb_pages += 1
        self.ecrire("recherche/", self.page_recherche())
        self.ecrire("404.html", self.page_404())

        index = [{"t": ep["titre"], "s": self.sous_titre(ep), "u": ep["url"],
                  "d": format_duree(ep.get("duree")), "p": self.lien(self.index[ep["rubrique"]]["url"])}
                 for ep in tous_les_episodes(self.racine)]
        (self.sortie / "recherche.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (self.sortie / ".htaccess").write_text(
            f"ErrorDocument 404 {self.lien('404.html')}\nDirectoryIndex index.html index.php\n"
            "<IfModule mod_expires.c>\n  ExpiresActive On\n  ExpiresByType text/css \"access plus 1 month\"\n"
            "  ExpiresByType application/javascript \"access plus 1 month\"\n</IfModule>\n", encoding="utf-8")
        return nb_pages + 2, len(index)


SPRITE = """<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-play" viewBox="0 0 24 24"><path fill="currentColor" d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></symbol>
  <symbol id="i-pause" viewBox="0 0 24 24"><path fill="currentColor" d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></symbol>
  <symbol id="i-prev" viewBox="0 0 24 24"><path fill="currentColor" d="M6 5h2v14H6zM20 5.5v13a1 1 0 0 1-1.5.86L9 13.1a1.3 1.3 0 0 1 0-2.2l9.5-6.26A1 1 0 0 1 20 5.5z"/></symbol>
  <symbol id="i-next" viewBox="0 0 24 24"><path fill="currentColor" d="M16 5h2v14h-2zM4 5.5v13a1 1 0 0 0 1.5.86L15 13.1a1.3 1.3 0 0 0 0-2.2L5.5 4.64A1 1 0 0 0 4 5.5z"/></symbol>
  <symbol id="i-book" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/></symbol>
  <symbol id="i-mic" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3"/></symbol>
  <symbol id="i-mosque" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M12 2v2M7 12a5 5 0 0 1 10 0M5 12h14v9H5zM10 21v-4a2 2 0 0 1 4 0v4M2 21h20M3 21V10M21 21V10"/></symbol>
  <symbol id="i-star" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M12 2l2.6 6.4L21 11l-6.4 2.6L12 20l-2.6-6.4L3 11l6.4-2.6z"/></symbol>
  <symbol id="i-scale" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/></symbol>
  <symbol id="i-child" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" d="M12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8 22l1-8-3-3 3-2h6l3 2-3 3 1 8"/></symbol>
  <symbol id="i-scroll" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M8 3h11a2 2 0 0 1 2 2v2h-4M8 3a2 2 0 0 0-2 2v14a2 2 0 0 1-2 2h11a2 2 0 0 0 2-2V5a2 2 0 0 1 2-2M10 9h4M10 13h4"/></symbol>
  <symbol id="i-heart" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M12 21s-8-5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6-8 11-8 11z"/></symbol>
  <symbol id="i-plane" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M10 14l-7-3 2-2 9 1 5-5a2 2 0 0 1 3 3l-5 5 1 9-2 2-3-7-3 3v3l-2 1-1-4-4-1 1-2h3z"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.5-4.5"/></symbol>
  <symbol id="i-back" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5"/><text x="12" y="15.5" font-size="7" text-anchor="middle" fill="currentColor" font-family="Inter" font-weight="700">15</text></symbol>
  <symbol id="i-fwd" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"/><text x="12" y="15.5" font-size="7" text-anchor="middle" fill="currentColor" font-family="Inter" font-weight="700">15</text></symbol>
  <symbol id="i-dl" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M12 4v11M7 10l5 5 5-5M5 20h14"/></symbol>
  <symbol id="i-menu" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M4 7h16M4 12h16M4 17h16"/></symbol>
</svg>"""

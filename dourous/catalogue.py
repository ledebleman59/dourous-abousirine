"""Catalogue des audios : liste de fichiers -> arborescence de rubriques et d'épisodes.

Le catalogue est un fichier JSON (catalogue.json) qui contient, pour chaque MP3,
son chemin relatif au dossier audio, sa taille, sa date et sa durée. Tout le reste
(titres, numéros, rubriques) est déduit des noms de dossiers et de fichiers.
"""
import json
import re
import struct
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

USER_AGENT = "DourousSite/1.0"

# Préfixes qui indiquent seulement le type d'audio : on les retire du titre affiché.
PREFIXES_TYPE = re.compile(
    r"^(conf[ée]rence|khutba|khotba|cours enfants?|cours)\s*-\s*", re.IGNORECASE
)


def slugifier(texte):
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = re.sub(r"[^a-zA-Z0-9]+", "-", texte).strip("-").lower()
    return texte or "rubrique"


def analyser_titre(nom_fichier):
    """'Tafsir - Fatiha - 28 - Recherchez la guérison.mp3'
    -> {'numero': 28, 'titre': 'Recherchez la guérison', 'serie': 'Tafsir - Fatiha'}"""
    base = re.sub(r"\.mp3$", "", nom_fichier, flags=re.IGNORECASE).strip()
    base = PREFIXES_TYPE.sub("", base)
    morceaux = [m.strip() for m in re.split(r"\s+-\s+", base) if m.strip()]

    for i, morceau in enumerate(morceaux):
        # « 28 » ou « Tafsir (06) »
        m = re.fullmatch(r"(?:(.*?)\s*\()?(\d{1,3})\)?", morceau)
        if not m:
            continue
        numero = int(m.group(2))
        avant = morceaux[:i] + ([m.group(1)] if m.group(1) else [])
        apres = morceaux[i + 1:]
        if apres:
            return {"numero": numero, "titre": " - ".join(apres), "serie": " - ".join(avant)}
        return {"numero": numero, "titre": base, "serie": ""}
    return {"numero": None, "titre": base, "serie": ""}


def charger_affichage(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def construire_arbre(fichiers, affichage):
    """fichiers : liste de dicts {chemin, taille, date, duree}. Renvoie la rubrique racine."""
    renommer = affichage.get("renommer", {})
    masquer = set(affichage.get("masquer", []))
    fusionner = set(affichage.get("fusionner", []))
    descriptions = affichage.get("descriptions", {})
    ordre = affichage.get("ordre", [])

    racine = {"nom": "Accueil", "chemin": "", "slug": "", "url": "", "rubriques": [], "episodes": []}
    index = {"": racine}

    def rubrique(chemin_dossier):
        if chemin_dossier in index:
            return index[chemin_dossier]
        parent_chemin, _, nom = chemin_dossier.rpartition("/")
        parent = rubrique(parent_chemin)
        nom_affiche = renommer.get(chemin_dossier, re.sub(r"^-\s*", "", nom).strip())
        slug = slugifier(nom_affiche)
        r = {
            "nom": nom_affiche,
            "chemin": chemin_dossier,
            "slug": slug,
            "url": (parent["url"] + slug + "/"),
            "description": descriptions.get(chemin_dossier, ""),
            "rubriques": [],
            "episodes": [],
            "parent": parent_chemin,
        }
        parent["rubriques"].append(r)
        index[chemin_dossier] = r
        return r

    for f in fichiers:
        dossier, _, nom = f["chemin"].rpartition("/")
        if any(dossier == m or dossier.startswith(m + "/") for m in masquer):
            continue
        # Un dossier « fusionné » range ses audios directement dans son parent.
        while dossier in fusionner:
            dossier = dossier.rpartition("/")[0]
        infos = analyser_titre(nom)
        r = rubrique(dossier)
        r["episodes"].append({**f, **infos, "rubrique": dossier})

    for r in index.values():
        numerotes = sum(1 for e in r["episodes"] if e["numero"] is not None)
        if r["episodes"] and numerotes >= len(r["episodes"]) * 0.6:
            r["episodes"].sort(key=lambda e: (e["numero"] is None, e["numero"] or 0, e["titre"]))
            r["tri"] = "numero"
        else:
            r["episodes"].sort(key=lambda e: e.get("date") or "", reverse=True)
            r["tri"] = "date"
        rang = {c: i for i, c in enumerate(ordre)}
        r["rubriques"].sort(key=lambda s: (rang.get(s["chemin"], 999), _cle_naturelle(s["nom"])))
    return racine, index


def _cle_naturelle(texte):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", texte)]


def tous_les_episodes(rubrique):
    yield from rubrique["episodes"]
    for r in rubrique["rubriques"]:
        yield from tous_les_episodes(r)


# --- Informations audio (taille, date, durée) lues par HTTP sur le fichier public ---

def url_audio(base_url, chemin):
    return base_url.rstrip("/") + "/" + urllib.parse.quote(chemin)


def _requete(url, debut=None, fin=None, methode="GET"):
    req = urllib.request.Request(url, method=methode, headers={"User-Agent": USER_AGENT})
    if debut is not None:
        req.add_header("Range", f"bytes={debut}-{fin}")
    return urllib.request.urlopen(req, timeout=30)


BITRATES = {  # MPEG1 couche 3, MPEG2/2.5 couche 3
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
FREQUENCES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _duree_mp3(entete, debut_trame, taille):
    """Durée en secondes à partir de la première trame MP3 (gère l'en-tête VBR Xing/Info)."""
    for i in range(debut_trame, len(entete) - 4):
        if entete[i] != 0xFF or (entete[i + 1] & 0xE0) != 0xE0:
            continue
        version = (entete[i + 1] >> 3) & 3
        couche = (entete[i + 1] >> 1) & 3
        idx_br = entete[i + 2] >> 4
        idx_fr = (entete[i + 2] >> 2) & 3
        if version == 1 or couche != 1 or idx_br in (0, 15) or idx_fr == 3:
            continue
        frequence = FREQUENCES[version][idx_fr]
        echantillons = 1152 if version == 3 else 576
        xing = entete.find(b"Xing", i, i + 200)
        if xing < 0:
            xing = entete.find(b"Info", i, i + 200)
        if xing >= 0 and len(entete) >= xing + 12:
            drapeaux = struct.unpack(">I", entete[xing + 4:xing + 8])[0]
            if drapeaux & 1:
                trames = struct.unpack(">I", entete[xing + 8:xing + 12])[0]
                return round(trames * echantillons / frequence)
        debit = BITRATES[1 if version == 3 else 2][idx_br] * 1000
        return round((taille - i) * 8 / debit)
    return None


def infos_audio(url):
    infos = {"taille": None, "date": None, "duree": None}
    with _requete(url, methode="HEAD") as r:
        infos["taille"] = int(r.headers.get("Content-Length") or 0) or None
        if r.headers.get("Last-Modified"):
            infos["date"] = parsedate_to_datetime(r.headers["Last-Modified"]).strftime("%Y-%m-%d")
    with _requete(url, 0, 9) as r:
        tete = r.read(10)
    decalage = 0
    if tete[:3] == b"ID3":
        t = tete[6:10]
        decalage = 10 + ((t[0] << 21) | (t[1] << 14) | (t[2] << 7) | t[3])
    with _requete(url, decalage, decalage + 4095) as r:
        bloc = r.read()
    if infos["taille"]:
        infos["duree"] = _duree_mp3(bloc, 0, infos["taille"] - decalage)
    return infos


def completer_infos(fichiers, base_url, anciens=None, journal=print):
    """Ajoute taille/date/durée aux fichiers qui n'en ont pas encore (cache = ancien catalogue)."""
    anciens = {f["chemin"]: f for f in (anciens or [])}
    a_lire = []
    for f in fichiers:
        ancien = anciens.get(f["chemin"])
        if ancien and ancien.get("duree") and ancien.get("taille") == f.get("taille", ancien.get("taille")):
            f.update({k: ancien[k] for k in ("taille", "duree") if ancien.get(k)})
            f.setdefault("date", ancien.get("date"))
        else:
            a_lire.append(f)
    if not a_lire:
        return fichiers
    journal(f"Lecture des informations de {len(a_lire)} audio(s)…")

    def lire(f):
        try:
            infos = infos_audio(url_audio(base_url, f["chemin"]))
            for k, v in infos.items():
                if v and not f.get(k):
                    f[k] = v
        except Exception as e:  # un fichier illisible ne doit pas bloquer la publication
            journal(f"  ! {f['chemin']} : {e}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lire, a_lire))
    return fichiers


def lire_catalogue(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def ecrire_catalogue(chemin, fichiers):
    fichiers = sorted(fichiers, key=lambda f: f["chemin"])
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(fichiers, f, ensure_ascii=False, indent=1)

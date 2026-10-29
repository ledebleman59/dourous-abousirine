"""Import de la liste des audios depuis l'ancien site Joomla (pages jDownloads).

Sert pour la migration et pour travailler sans accès FTP : on parcourt les pages
de catégories et on relève les <source src="/jdownloads/....mp3">.
"""
import html
import re
import urllib.parse
import urllib.request
from collections import deque

from .catalogue import USER_AGENT

DEPARTS = [
    "/index.php/khutba-joumou3a/category/10-khutba-joumou3a",
    "/index.php/cours/category/17-cours",
    "/index.php/cours-enfants/category/4-enfants",
    "/index.php/conferences/category/3-conferences",
]


def importer_depuis_site(site_url, dossier_audio="jdownloads", journal=print, max_pages=500):
    site_url = site_url.rstrip("/")
    prefixe = "/" + dossier_audio.strip("/") + "/"
    vus, file, chemins = set(), deque(DEPARTS), []
    while file and len(vus) < max_pages:
        page = file.popleft()
        if page in vus:
            continue
        vus.add(page)
        req = urllib.request.Request(site_url + page, headers={"User-Agent": USER_AGENT})
        try:
            texte = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            journal(f"  ! {page} : {e}")
            continue
        for src in re.findall(r'<source src="([^"]+\.mp3)"', texte, re.IGNORECASE):
            src = urllib.parse.unquote(html.unescape(src))
            if src.startswith(prefixe):
                chemin = src[len(prefixe):]
                if chemin not in chemins:
                    chemins.append(chemin)
        for lien in re.findall(r'href="(/index\.php/[^"#]*category/\d+[^"#]*)"', texte):
            lien = html.unescape(lien)
            if lien not in vus:
                file.append(lien)
    journal(f"{len(vus)} pages parcourues, {len(chemins)} audios trouvés.")
    return [{"chemin": c} for c in chemins]

#!/usr/bin/env python3
"""Outil du site Dourous Abou Sirine.

  python3 outil.py apercu      Construit le site et l'ouvre en local (http://localhost:8000)
  python3 outil.py publier     Relit le FTP, reconstruit le site et l'envoie en ligne
  python3 outil.py verifier    Teste la connexion FTP et affiche les dossiers
  python3 outil.py scanner     Relit seulement la liste des audios sur le FTP
  python3 outil.py construire  Construit seulement le site dans dist/
  python3 outil.py importer    Récupère la liste des audios depuis l'ancien site Joomla
"""
import configparser
import functools
import http.server
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

from dourous import catalogue as cat  # noqa: E402
from dourous.generateur import Generateur  # noqa: E402

CONFIG = ICI / "config.ini"
CATALOGUE = ICI / "catalogue.json"
AFFICHAGE = ICI / "affichage.json"
ETAT = ICI / ".publication.json"


def lire_config(ftp_requis=False):
    config = configparser.ConfigParser()
    config.read(ICI / "config.exemple.ini", encoding="utf-8")
    if CONFIG.exists():
        config.read(CONFIG, encoding="utf-8")
    elif ftp_requis:
        shutil.copy(ICI / "config.exemple.ini", CONFIG)
        sys.exit("J'ai créé le fichier config.ini : ouvrez-le, remplissez la partie [ftp], puis relancez la commande.")
    if ftp_requis and not config["ftp"].get("mot_de_passe"):
        sys.exit("Le mot de passe FTP est vide dans config.ini.")
    return config


def construire(config, chemin_site=None):
    reglages = dict(config["site"])
    if chemin_site is not None:
        reglages["chemin_site"] = chemin_site
    fichiers = cat.lire_catalogue(CATALOGUE)
    if not fichiers:
        sys.exit("catalogue.json est vide : lancez d'abord « python3 outil.py scanner » (ou « importer »).")
    gen = Generateur(fichiers, cat.charger_affichage(AFFICHAGE), reglages, ICI)
    pages, audios = gen.construire()
    print(f"Site construit dans dist/ : {pages} pages, {audios} audios.")


def scanner(config, ftp=None):
    from dourous import ftp as ftp_outils
    fermer = ftp is None
    ftp = ftp or ftp_outils.connecter(config["ftp"])
    try:
        fichiers = ftp_outils.scanner_audios(ftp, config["site"]["dossier_audio_ftp"])
    finally:
        if fermer:
            ftp.quit()
    anciens = cat.lire_catalogue(CATALOGUE)
    cat.completer_infos(fichiers, config["site"]["url_audio"], anciens)
    ajoutes = {f["chemin"] for f in fichiers} - {f["chemin"] for f in anciens}
    retires = {f["chemin"] for f in anciens} - {f["chemin"] for f in fichiers}
    cat.ecrire_catalogue(CATALOGUE, fichiers)
    for c in sorted(ajoutes):
        print(f"  + {c}")
    for c in sorted(retires):
        print(f"  - {c}")
    print(f"Catalogue à jour : {len(fichiers)} audios ({len(ajoutes)} nouveaux, {len(retires)} retirés).")


def commande_importer(config):
    from dourous.importer import importer_depuis_site
    site = config["site"]["url_audio"].rsplit("/", 1)[0]
    fichiers = importer_depuis_site(site, config["site"]["url_audio"].rsplit("/", 1)[1])
    cat.completer_infos(fichiers, config["site"]["url_audio"], cat.lire_catalogue(CATALOGUE))
    cat.ecrire_catalogue(CATALOGUE, fichiers)
    print(f"catalogue.json : {len(fichiers)} audios.")


def commande_apercu(config):
    construire(config, chemin_site="/")
    port = 8000
    gestion = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ICI / "dist"))
    print(f"Aperçu : http://localhost:{port}  (Ctrl+C pour arrêter)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), gestion).serve_forever()


def commande_verifier(config):
    from dourous import ftp as ftp_outils
    ftp = ftp_outils.connecter(config["ftp"])
    print(f"Connexion réussie à {config['ftp']['hote']}.")
    print("Dossiers à la racine du FTP :", ", ".join(sorted(ftp.nlst())))
    for cle in ("dossier_audio_ftp", "dossier_site_ftp"):
        dossier = config["site"][cle]
        try:
            contenu = ftp.nlst(dossier)
            print(f"{cle} = {dossier} : trouvé ({len(contenu)} éléments)")
        except Exception:
            print(f"{cle} = {dossier} : introuvable (il sera créé à la publication)" if cle == "dossier_site_ftp"
                  else f"{cle} = {dossier} : INTROUVABLE, corrigez config.ini")
    ftp.quit()


def commande_publier(config):
    from dourous import ftp as ftp_outils
    # À la racine, le nouveau site remplacerait l'accueil et le .htaccess de Joomla : on exige une confirmation.
    if config["site"]["dossier_site_ftp"].strip("/") in ("", "www") and "--remplacer-ancien-site" not in sys.argv:
        sys.exit("dossier_site_ftp pointe vers la racine du site : cela remplacerait le site actuel.\n"
                 "Si c'est bien voulu, relancez avec : python3 outil.py publier --remplacer-ancien-site")
    ftp = ftp_outils.connecter(config["ftp"])
    try:
        scanner(config, ftp)
        construire(config)
        print("Envoi du site…")
        ftp_outils.envoyer_site(ftp, ICI / "dist", config["site"]["dossier_site_ftp"], ETAT)
    finally:
        ftp.quit()
    print("Publication terminée.")


def main():
    commande = sys.argv[1] if len(sys.argv) > 1 else ""
    if commande == "apercu":
        commande_apercu(lire_config())
    elif commande == "construire":
        construire(lire_config())
    elif commande == "importer":
        commande_importer(lire_config())
    elif commande == "scanner":
        scanner(lire_config(ftp_requis=True))
    elif commande == "verifier":
        commande_verifier(lire_config(ftp_requis=True))
    elif commande == "publier":
        commande_publier(lire_config(ftp_requis=True))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

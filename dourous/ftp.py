"""Accès FTP : lister les MP3 du dossier audio et envoyer le site généré."""
import ftplib
import hashlib
import json
import posixpath
from pathlib import Path


def connecter(config, journal=print):
    hote, utilisateur, mot_de_passe = config["hote"], config["utilisateur"], config["mot_de_passe"]
    chiffrement = config.get("chiffrement", "auto").lower()
    if chiffrement in ("auto", "oui"):
        try:
            ftp = ftplib.FTP_TLS(hote, timeout=60)
            ftp.login(utilisateur, mot_de_passe)
            ftp.prot_p()
            ftp.encoding = "utf-8"
            return ftp
        except ftplib.error_perm:
            raise
        except Exception as e:
            if chiffrement == "oui":
                raise
            journal(f"(connexion chiffrée impossible : {e} ; connexion FTP simple)")
    ftp = ftplib.FTP(hote, timeout=60)
    ftp.login(utilisateur, mot_de_passe)
    ftp.encoding = "utf-8"
    return ftp


def _lister(ftp, dossier):
    """Renvoie [(nom, est_dossier, taille, date_iso)] ; MLSD si possible, sinon NLST."""
    try:
        entrees = []
        for nom, faits in ftp.mlsd(dossier, facts=["type", "size", "modify"]):
            if nom in (".", ".."):
                continue
            date = faits.get("modify", "")
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) >= 8 else None
            entrees.append((nom, faits.get("type") == "dir", int(faits.get("size", 0) or 0), date))
        return entrees
    except ftplib.error_perm:
        entrees = []
        for chemin in ftp.nlst(dossier):
            nom = posixpath.basename(chemin)
            if nom in (".", ".."):
                continue
            try:
                taille = ftp.size(posixpath.join(dossier, nom))
                entrees.append((nom, False, taille, None))
            except ftplib.error_perm:
                entrees.append((nom, True, 0, None))
        return entrees


def scanner_audios(ftp, dossier_audio, journal=print):
    fichiers = []

    def parcourir(dossier, relatif):
        for nom, est_dossier, taille, date in _lister(ftp, dossier):
            chemin_rel = f"{relatif}/{nom}" if relatif else nom
            if est_dossier:
                parcourir(posixpath.join(dossier, nom), chemin_rel)
            elif nom.lower().endswith(".mp3"):
                fichiers.append({"chemin": chemin_rel, "taille": taille, "date": date})

    parcourir(dossier_audio, "")
    journal(f"{len(fichiers)} fichiers MP3 trouvés sur le FTP.")
    return fichiers


def _empreinte(chemin):
    return hashlib.sha1(chemin.read_bytes()).hexdigest()


def envoyer_site(ftp, dossier_local, dossier_distant, fichier_etat, journal=print):
    """Envoie seulement les fichiers nouveaux ou modifiés depuis la dernière publication.
    Ne supprime jamais rien sur le serveur."""
    dossier_local = Path(dossier_local)
    try:
        etat = json.loads(Path(fichier_etat).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        etat = {}
    cle_etat = f"{ftp.host}:{dossier_distant}"
    deja = etat.get(cle_etat, {})
    nouveaux, crees = {}, set()

    def creer_dossier(chemin):
        morceaux = chemin.strip("/").split("/")
        courant = "/" if chemin.startswith("/") else ""
        for m in morceaux:
            courant = posixpath.join(courant, m) if courant else m
            if courant in crees:
                continue
            try:
                ftp.mkd(courant)
            except ftplib.error_perm:
                pass  # existe déjà
            crees.add(courant)

    fichiers = sorted(p for p in dossier_local.rglob("*") if p.is_file())
    envoyes = 0
    for p in fichiers:
        rel = p.relative_to(dossier_local).as_posix()
        emp = _empreinte(p)
        nouveaux[rel] = emp
        if deja.get(rel) == emp:
            continue
        distant = posixpath.join(dossier_distant, rel)
        creer_dossier(posixpath.dirname(distant))
        with open(p, "rb") as f:
            ftp.storbinary(f"STOR {distant}", f)
        envoyes += 1
        if envoyes % 25 == 0:
            journal(f"  {envoyes} fichiers envoyés…")
    etat[cle_etat] = nouveaux
    Path(fichier_etat).write_text(json.dumps(etat, indent=1), encoding="utf-8")
    journal(f"{envoyes} fichier(s) envoyé(s), {len(fichiers) - envoyes} inchangé(s).")
    return envoyes

"""Moteur de jeu : avance l'horloge, applique le vieillissement en temps
réel, gère l'éclosion, la reproduction et construit l'état envoyé au front."""
import math
from datetime import datetime, timezone

from . import models
from .models import Animal, provision_depuis_type, tirer_provision_aleatoire
from .storage import now_iso

MINUTES_PAR_JOUR = 1440


def _parse_iso(s):
    return datetime.fromisoformat(s)


def heure_du_jour(minutes_jeu_ecoulees):
    return (minutes_jeu_ecoulees % MINUTES_PAR_JOUR) / 60


def est_nuit(heure):
    return heure >= models.NIGHT_START_HOUR or heure < models.NIGHT_END_HOUR


def tick(save):
    """Fait avancer la partie jusqu'à maintenant. Modifie `save` en place et
    retourne la liste des nouveaux messages générés à cette occasion."""
    maintenant = datetime.now(timezone.utc)
    dernier = _parse_iso(save["dernier_maj"])
    dt_reel_s = max((maintenant - dernier).total_seconds(), 0)
    if save.get("en_pause"):
        dt_jeu_min = 0.0
    else:
        vitesse = save.get("vitesse", 1.0)
        dt_jeu_min = dt_reel_s * models.GAME_MINUTES_PER_REAL_SECOND * vitesse

    minutes_avant = save["minutes_jeu_ecoulees"]
    minutes_apres = minutes_avant + dt_jeu_min

    heure_actuelle = heure_du_jour(minutes_apres)
    multiplicateur = models.NIGHT_DECAY_MULTIPLIER if est_nuit(heure_actuelle) else 1.0

    jour_avant = math.floor(minutes_avant / MINUTES_PAR_JOUR)
    jour_apres = math.floor(minutes_apres / MINUTES_PAR_JOUR)
    nouveau_jour = jour_apres > jour_avant

    messages = []
    animaux = [Animal.from_dict(a) for a in save["animaux"]]
    nouveaux_nes = []

    for animal in animaux:
        if not animal.est_vivant():
            continue
        etait_oeuf = animal.stage == "oeuf"
        resultat = animal.vieillir(dt_jeu_min, multiplicateur)
        if resultat == "mort":
            messages.append(f"💔 {animal.nom} n'a pas survécu...")
        elif etait_oeuf and animal.stage != "oeuf":
            messages.append(f"🐣 Un œuf a éclos : bienvenue {animal.nom} !")

        if nouveau_jour and animal.est_vivant():
            enfant = animal.essayer_creer_enfant()
            if enfant:
                nouveaux_nes.append(enfant)
                messages.append(f"🎉 {animal.nom} a pondu un œuf : {enfant.nom} !")

    animaux.extend(nouveaux_nes)
    if nouveau_jour:
        messages.append("🌅 Un nouveau jour se lève !")

    save["animaux"] = [a.to_dict() for a in animaux]
    save["minutes_jeu_ecoulees"] = minutes_apres
    save["dernier_maj"] = maintenant.isoformat()
    save["messages"] = save.get("messages", []) + horodater(messages, maintenant)
    return messages


def horodater(messages_texte, moment):
    """Associe à chaque message texte la date/heure réelle à laquelle il
    s'est produit, pour affichage côté client."""
    horodatage = moment.isoformat()
    return [{"texte": t, "horodatage": horodatage} for t in messages_texte]


def secondes_restantes(save, cle_cooldown, animal_id=None):
    if animal_id:
        animal = next((a for a in save["animaux"] if a["id"] == animal_id), None)
        iso = animal["cooldowns"].get(cle_cooldown) if animal else None
    else:
        iso = save.get(cle_cooldown)
    if not iso:
        return 0
    delta = (_parse_iso(iso) - datetime.now(timezone.utc)).total_seconds()
    return max(0, round(delta))


def poser_cooldown(dico_cooldowns, cle, secondes):
    from datetime import timedelta
    fin = datetime.now(timezone.utc) + timedelta(seconds=secondes)
    dico_cooldowns[cle] = fin.isoformat()


def construire_etat(save):
    minutes = save["minutes_jeu_ecoulees"]
    heure = heure_du_jour(minutes)
    nuit = est_nuit(heure)

    animaux_etat = []
    for a in save["animaux"]:
        etat = dict(a)
        etat["cooldowns_restants"] = {
            cle: secondes_restantes(save, cle, animal_id=a["id"])
            for cle in a.get("cooldowns", {})
        }
        animaux_etat.append(etat)

    provisions_par_type = {}
    for p in save["provisions"]:
        provisions_par_type.setdefault(p["type"], {"count": 0, **p})
        provisions_par_type[p["type"]]["count"] += 1

    messages = save.get("messages", [])
    save["messages"] = []

    return {
        "heure_du_jour": round(heure, 2),
        "est_nuit": nuit,
        "jour": math.floor(minutes / MINUTES_PAR_JOUR) + 1,
        "animaux": animaux_etat,
        "provisions": list(provisions_par_type.values()),
        "recolte_dans": secondes_restantes(save, "prochaine_recolte"),
        "messages": messages,
        "en_pause": save.get("en_pause", False),
        "vitesse": save.get("vitesse", 1.0),
    }

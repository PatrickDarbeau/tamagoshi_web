"""Serveur du jeu Tamagoshi : sert l'interface animée et expose une petite
API JSON utilisée par le front pour lire/faire évoluer l'état en temps réel."""
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, g, jsonify, render_template, request

from game import engine, models, storage
from game.models import Animal, provision_depuis_type, tirer_provision_aleatoire

app = Flask(__name__)

SID_COOKIE = "tamagoshi_sid"

COOLDOWN_NOURRIR = 12
COOLDOWN_SOIGNER = 45
COOLDOWN_CARESSER = 6
COOLDOWN_NETTOYER = 4
COOLDOWN_RECOLTE = 25
COOLDOWN_RECOLTE_PALIER = 5
COOLDOWN_RECOLTE_MIN = 10

POINTS_SOIGNER = 25
POINTS_CARESSER = 15


# --- gestion de la session (cookie -> fichier de sauvegarde) ------------

@app.before_request
def ensure_session():
    sid = request.cookies.get(SID_COOKIE)
    g.new_sid = None
    if not sid:
        sid = storage.nouveau_sid()
        g.new_sid = sid
    g.sid = sid


@app.after_request
def set_session_cookie(resp):
    if g.get("new_sid"):
        resp.set_cookie(SID_COOKIE, g.new_sid, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


# --- aides -----------------------------------------------------------------

def _charger_et_avancer():
    save = storage.charger(g.sid)
    engine.tick(save)
    return save


def _trouver_animal(save, aid):
    return next((a for a in save["animaux"] if a["id"] == aid), None)


def _appliquer_cooldown_animal(animal_dict, cle, secondes):
    fin = datetime.now(timezone.utc) + timedelta(seconds=secondes)
    animal_dict.setdefault("cooldowns", {})[cle] = fin.isoformat()


def _cooldown_recolte(save):
    """Plus il y a d'animaux vivants à nourrir, plus il faut réapprovisionner
    souvent : la recharge perd COOLDOWN_RECOLTE_PALIER secondes par animal
    au-delà du premier, jusqu'à COOLDOWN_RECOLTE_MIN. Sans aucun animal, on
    peut constituer des réserves à l'avance : la recharge tombe à 1s."""
    nb_vivants = len([a for a in save["animaux"] if a["vivant"]])
    if nb_vivants == 0:
        return 1
    return max(COOLDOWN_RECOLTE - COOLDOWN_RECOLTE_PALIER * (nb_vivants - 1), COOLDOWN_RECOLTE_MIN)


def _erreur(message, code=400):
    return jsonify({"erreur": message}), code


# --- pages -------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# --- API : lecture d'état ------------------------------------------------

@app.route("/api/state")
def api_state():
    save = _charger_et_avancer()
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


# --- API : créer un animal (nouvel œuf) --------------------------------

@app.route("/api/animaux", methods=["POST"])
def api_creer_animal():
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "").strip()
    if not nom:
        return _erreur("Merci de donner un nom à votre œuf.")
    if len(nom) > 30:
        nom = nom[:30]

    save = _charger_et_avancer()
    if len([a for a in save["animaux"] if a["vivant"]]) >= 6:
        return _erreur("Élevage complet (6 animaux vivants maximum).")

    animal = Animal(nom)
    save["animaux"].append(animal.to_dict())
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


@app.route("/api/animaux/<aid>/supprimer", methods=["POST"])
def api_supprimer_animal(aid):
    save = _charger_et_avancer()
    animal = _trouver_animal(save, aid)
    if not animal:
        return _erreur("Animal introuvable.", 404)
    if animal["vivant"]:
        return _erreur("Impossible de retirer un animal encore vivant.")
    save["animaux"] = [a for a in save["animaux"] if a["id"] != aid]
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


# --- API : actions sur un animal ----------------------------------------

@app.route("/api/animaux/<aid>/nourrir", methods=["POST"])
def api_nourrir(aid):
    data = request.get_json(silent=True) or {}
    provision_id = data.get("provision_id")

    save = _charger_et_avancer()
    animal_dict = _trouver_animal(save, aid)
    if not animal_dict or not animal_dict["vivant"]:
        return _erreur("Animal introuvable ou décédé.", 404)

    restant = engine.secondes_restantes(save, "nourrir", animal_id=aid)
    if restant > 0:
        return _erreur(f"Patientez encore {restant}s avant de nourrir à nouveau.", 429)

    item = next((p for p in save["provisions"] if p["id"] == provision_id), None)
    if not item:
        return _erreur("Cette provision n'est plus disponible.")

    animal = Animal.from_dict(animal_dict)
    animal.nourrir(provision_depuis_type(item["type"]))
    nouveau_dict = animal.to_dict()
    nouveau_dict["cooldowns"] = animal_dict.get("cooldowns", {})
    _appliquer_cooldown_animal(nouveau_dict, "nourrir", COOLDOWN_NOURRIR)

    save["provisions"] = [p for p in save["provisions"] if p["id"] != provision_id]
    save["animaux"] = [nouveau_dict if a["id"] == aid else a for a in save["animaux"]]
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


def _action_simple(aid, cle_cooldown, secondes_cooldown, appliquer):
    save = _charger_et_avancer()
    animal_dict = _trouver_animal(save, aid)
    if not animal_dict or not animal_dict["vivant"]:
        return _erreur("Animal introuvable ou décédé.", 404)

    restant = engine.secondes_restantes(save, cle_cooldown, animal_id=aid)
    if restant > 0:
        return _erreur(f"Patientez encore {restant}s.", 429)

    animal = Animal.from_dict(animal_dict)
    appliquer(animal)
    nouveau_dict = animal.to_dict()
    nouveau_dict["cooldowns"] = animal_dict.get("cooldowns", {})
    _appliquer_cooldown_animal(nouveau_dict, cle_cooldown, secondes_cooldown)

    save["animaux"] = [nouveau_dict if a["id"] == aid else a for a in save["animaux"]]
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


@app.route("/api/animaux/<aid>/soigner", methods=["POST"])
def api_soigner(aid):
    return _action_simple(aid, "soigner", COOLDOWN_SOIGNER, lambda a: a.soigner(POINTS_SOIGNER))


@app.route("/api/animaux/<aid>/caresser", methods=["POST"])
def api_caresser(aid):
    return _action_simple(aid, "caresser", COOLDOWN_CARESSER, lambda a: a.caresser(POINTS_CARESSER))


@app.route("/api/animaux/<aid>/nettoyer", methods=["POST"])
def api_nettoyer(aid):
    return _action_simple(aid, "nettoyer", COOLDOWN_NETTOYER, lambda a: a.nettoyer())


# --- API : provisions ----------------------------------------------------

@app.route("/api/provisions/recolter", methods=["POST"])
def api_recolter():
    save = _charger_et_avancer()
    restant = engine.secondes_restantes(save, "prochaine_recolte")
    if restant > 0:
        return _erreur(f"Patientez encore {restant}s avant de chercher à nouveau.", 429)

    import uuid
    provision = tirer_provision_aleatoire()
    item = provision.to_dict()
    item["id"] = uuid.uuid4().hex
    save["provisions"].append(item)
    texte = f"{item['emoji']} Vous avez trouvé : {item['nom']} !"
    save["messages"] = save.get("messages", []) + engine.horodater(
        [texte], datetime.now(timezone.utc)
    )

    fin = datetime.now(timezone.utc) + timedelta(seconds=_cooldown_recolte(save))
    save["prochaine_recolte"] = fin.isoformat()

    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


# --- API : horloge (pause / vitesse / réinitialisation) -------------------

@app.route("/api/pause", methods=["POST"])
def api_pause():
    data = request.get_json(silent=True) or {}
    save = _charger_et_avancer()
    save["en_pause"] = bool(data.get("en_pause"))
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


@app.route("/api/vitesse", methods=["POST"])
def api_vitesse():
    data = request.get_json(silent=True) or {}
    try:
        valeur = float(data.get("valeur"))
    except (TypeError, ValueError):
        return _erreur("Vitesse invalide.")
    valeur = max(models.VITESSE_MIN, min(models.VITESSE_MAX, valeur))

    save = _charger_et_avancer()
    save["vitesse"] = valeur
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


@app.route("/api/reinitialiser", methods=["POST"])
def api_reinitialiser():
    save = storage.sauvegarde_par_defaut()
    etat = engine.construire_etat(save)
    storage.enregistrer(g.sid, save)
    return jsonify(etat)


if __name__ == "__main__":
    port = int(os.environ.get("GAME_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

"""
Modèles du jeu, inspirés des classes PHP du prototype (Animal, Provision et
ses sous-classes Coca / Eau / Hamburger / Pastèque), adaptés à une évolution
en temps réel plutôt qu'à des actions comptées.
"""
import random
import uuid

# --- Constantes de rythme et d'équilibrage -------------------------------

GAME_MINUTES_PER_REAL_SECOND = 2      # 1 jour en jeu (1440 min) ~= 12 min réelles
VITESSE_MIN = 0.25
VITESSE_MAX = 5.0
EGG_HATCH_MINUTES = 120                # un œuf éclot après 2h de jeu
STAGE_ADO_DAYS = 2
STAGE_ADULTE_DAYS = 5

NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
NIGHT_DECAY_MULTIPLIER = 0.4

FAIM_PAR_HEURE = 4
SOIF_PAR_HEURE = 5
HUMEUR_PAR_HEURE = -3
PROPRETE_PAR_HEURE = 6

SANTE_REGEN_PAR_HEURE = 2
SANTE_PENALITE_FAIM = 8
SANTE_PENALITE_SOIF = 8
SANTE_PENALITE_HUMEUR = 5
SANTE_PENALITE_SALETE = 5

SEUIL_FAIM_CRITIQUE = 90
SEUIL_SOIF_CRITIQUE = 90
SEUIL_HUMEUR_CRITIQUE = 15
SEUIL_SALETE_CRITIQUE = 90

REPRODUCTION_CHANCE = 0.2  # par jour en jeu, si adulte en bonne santé


def clamp(valeur, mini=0, maxi=100):
    return max(mini, min(maxi, valeur))


class Provision:
    """Équivalent de la classe PHP Provision."""
    nom = "Provision"
    emoji = "🍽️"
    impact_faim = 0
    impact_soif = 0
    impact_sante = 0
    impact_humeur = 0

    def to_dict(self):
        return {
            "type": type(self).__name__,
            "nom": self.nom,
            "emoji": self.emoji,
            "impact_faim": self.impact_faim,
            "impact_soif": self.impact_soif,
            "impact_sante": self.impact_sante,
            "impact_humeur": self.impact_humeur,
        }

    def appliquer(self, animal):
        """Applique l'effet de la provision à l'animal (par défaut, ajoute
        les impacts aux jauges courantes ; une sous-classe peut surcharger
        pour imposer des valeurs absolues, cf. Croquettes)."""
        animal.faim += self.impact_faim
        animal.soif += self.impact_soif
        animal.sante += self.impact_sante
        animal.humeur += self.impact_humeur


class Coca(Provision):
    nom = "Coca"
    emoji = "🥤"
    impact_humeur = 30
    impact_soif = -10


class Eau(Provision):
    nom = "Eau"
    emoji = "💧"
    impact_humeur = -20
    impact_soif = -40


class Hamburger(Provision):
    nom = "Hamburger"
    emoji = "🍔"
    impact_faim = -100
    impact_soif = 30
    impact_sante = -10


class Pasteque(Provision):
    nom = "Pastèque"
    emoji = "🍉"
    impact_faim = -20
    impact_soif = -30


class Croquettes(Provision):
    """Provision rare et complète : régale l'animal. Contrairement aux
    autres provisions (impacts additionnés aux jauges courantes), les
    Croquettes imposent des valeurs absolues, y compris pour la propreté
    qui n'est normalement pas affectée par un repas."""
    nom = "Croquettes"
    emoji = "🥣"
    impact_faim = -100
    impact_soif = -100
    impact_sante = 100
    impact_humeur = 100

    def appliquer(self, animal):
        animal.faim = 0
        animal.soif = 0
        animal.sante = 100
        animal.humeur = 100
        animal.proprete = 90


PROVISION_CLASSES = {
    "Coca": Coca,
    "Eau": Eau,
    "Hamburger": Hamburger,
    "Pasteque": Pasteque,
    "Croquettes": Croquettes,
}

# Poids de tirage : le Hamburger est plus rare que les autres provisions
# (il pénalise la santé, on évite qu'il tombe aussi souvent que le reste).
PROVISION_POIDS = {
    "Coca": 3,
    "Eau": 3,
    "Hamburger": 2,
    "Pasteque": 4,
}
# Les Croquettes sont exceptionnelles : 1 tirage sur 20 en moyenne, quel
# que soit le réglage des poids ci-dessus (w tel que w / (S + w) = 1/20).
PROVISION_POIDS["Croquettes"] = sum(PROVISION_POIDS.values()) / 19


def provision_depuis_type(type_nom):
    classe = PROVISION_CLASSES[type_nom]
    return classe()


def tirer_provision_aleatoire():
    types = list(PROVISION_CLASSES.keys())
    poids = [PROVISION_POIDS[t] for t in types]
    type_nom = random.choices(types, weights=poids, k=1)[0]
    return provision_depuis_type(type_nom)


class Animal:
    """Équivalent de la classe PHP Animal, avec vieillissement en continu."""

    def __init__(self, nom, id=None, parent_nom=None):
        self.id = id or uuid.uuid4().hex
        self.nom = nom
        self.faim = 50
        self.soif = 50
        self.humeur = 100
        self.sante = 100
        self.proprete = 0
        self.age_minutes = 0.0
        self.nb_enfants = 0
        self.vivant = True
        self.dernier_jour_traite = 0
        self.parent_nom = parent_nom
        self.cooldowns = {}

    # -- état / étage --------------------------------------------------

    @property
    def age_jours(self):
        return self.age_minutes / 1440

    @property
    def stage(self):
        if self.age_minutes < EGG_HATCH_MINUTES:
            return "oeuf"
        jours = self.age_jours
        if jours < STAGE_ADO_DAYS:
            return "bebe"
        if jours < STAGE_ADULTE_DAYS:
            return "ado"
        return "adulte"

    def est_vivant(self):
        return self.vivant and self.sante > 0

    def _verifier_etat(self):
        self.sante = clamp(self.sante)
        self.faim = clamp(self.faim)
        self.soif = clamp(self.soif)
        self.humeur = clamp(self.humeur)
        self.proprete = clamp(self.proprete)
        if self.sante <= 0:
            self.vivant = False

    # -- actions du joueur ----------------------------------------------

    def soigner(self, points):
        if self.est_vivant():
            self.sante += points
            self._verifier_etat()

    def caresser(self, points):
        if self.est_vivant():
            self.humeur += points
            self._verifier_etat()

    def nourrir(self, provision):
        if self.est_vivant():
            provision.appliquer(self)
            self._verifier_etat()

    def nettoyer(self):
        if self.est_vivant():
            self.proprete = 0

    # -- vieillissement en continu --------------------------------------

    def vieillir(self, dt_minutes, multiplicateur_nuit=1.0):
        """Fait avancer l'animal de dt_minutes de jeu (décroissance continue,
        adaptation en temps réel du Animal::vieillir() PHP d'origine)."""
        if not self.est_vivant() or self.stage == "oeuf" or dt_minutes <= 0:
            self.age_minutes += max(dt_minutes, 0)
            self._verifier_etat()
            return None

        heures = (dt_minutes / 60) * multiplicateur_nuit

        self.faim += FAIM_PAR_HEURE * heures
        self.soif += SOIF_PAR_HEURE * heures
        self.humeur += HUMEUR_PAR_HEURE * heures
        self.proprete += PROPRETE_PAR_HEURE * heures
        self._verifier_etat()

        if self.faim >= SEUIL_FAIM_CRITIQUE:
            self.sante -= SANTE_PENALITE_FAIM * heures
        if self.soif >= SEUIL_SOIF_CRITIQUE:
            self.sante -= SANTE_PENALITE_SOIF * heures
        if self.humeur <= SEUIL_HUMEUR_CRITIQUE:
            self.sante -= SANTE_PENALITE_HUMEUR * heures
        if self.proprete >= SEUIL_SALETE_CRITIQUE:
            self.sante -= SANTE_PENALITE_SALETE * heures

        if (self.faim < 70 and self.soif < 70 and self.humeur > 50
                and self.proprete < 70):
            self.sante += SANTE_REGEN_PAR_HEURE * heures

        etait_vivant = self.vivant
        self._verifier_etat()
        self.age_minutes += dt_minutes

        if etait_vivant and not self.vivant:
            return "mort"
        return None

    def essayer_creer_enfant(self):
        """Adaptation de essayerCreerEnfant() : tentée une fois par jour en
        jeu écoulé plutôt qu'à chaque action."""
        if self.stage != "adulte" or not self.est_vivant():
            return None
        if self.sante > 70 and self.humeur > 70 and random.random() < REPRODUCTION_CHANCE:
            self.nb_enfants += 1
            return Animal(f"Bébé de {self.nom}", parent_nom=self.nom)
        return None

    # -- sérialisation ----------------------------------------------------

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "faim": round(self.faim, 1),
            "soif": round(self.soif, 1),
            "humeur": round(self.humeur, 1),
            "sante": round(self.sante, 1),
            "proprete": round(self.proprete, 1),
            "age_minutes": self.age_minutes,
            "age_jours": round(self.age_jours, 2),
            "stage": self.stage,
            "vivant": self.vivant,
            "nb_enfants": self.nb_enfants,
            "parent_nom": self.parent_nom,
            "cooldowns": self.cooldowns,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["nom"], id=data["id"], parent_nom=data.get("parent_nom"))
        obj.faim = data.get("faim", 50)
        obj.soif = data.get("soif", 50)
        obj.humeur = data.get("humeur", 100)
        obj.sante = data.get("sante", 100)
        obj.proprete = data.get("proprete", 0)
        obj.age_minutes = data.get("age_minutes", 0.0)
        obj.nb_enfants = data.get("nb_enfants", 0)
        obj.vivant = data.get("vivant", True)
        obj.cooldowns = data.get("cooldowns", {})
        return obj

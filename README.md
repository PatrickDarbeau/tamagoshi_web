<h1></center>🥚 Tamagoshi</center></h1>
 <center>par Patrick DARBEAU © 2026 - Version 1.0</center>
</br>

Découvrez les Tamagoshi, de petites créatures virtuelles venues de la lointaine planète du même nom. Depuis leur arrivée sur Terre en 1996, elles ont conquis des millions d’utilisateurs grâce à leur personnalité unique et leur charme irrésistible.

Les Tamagoshi adorent qu’on prenne soin d’eux : les nourrir, jouer avec eux et les accompagner dans leur évolution. Parfois un peu capricieux ou maladroits, ils restent toujours attachants et remplissent chaque journée de surprises.

Étranges, farfelus, mais incroyablement mignons, les Tamagoshi grandissent avec vous et deviennent rapidement une véritable présence dans votre quotidien.
Un compagnon virtuel à choyer, à découvrir… et à aimer.

# Tamagoshi Web

Un Tamagoshi jouable dans le navigateur, en temps réel : un jour de jeu dure
environ **12 minutes réelles**. L'état de vos animaux évolue même quand vous
n'avez pas la page ouverte — le temps écoulé est rattrapé à votre prochaine
visite. 

## Prérequis

- Python 3.10+
- pip

## Installation

```bash
git clone https://github.com/PatrickDarbeau/tamagoshi_web
cd tamagoshi_web
pip install -r requirements.txt
```

## Lancer le jeu

```bash
python app.py
```

Le serveur écoute par défaut sur le port **5000**. Pour changer de port :

```bash
GAME_PORT=8080 python app.py       # bash
$env:GAME_PORT=8080; python app.py # PowerShell
```

Puis ouvrez `http://localhost:<port>/` dans un navigateur. Votre partie est
liée à un cookie de session : rechargez la page depuis le même navigateur
pour la retrouver, elle est sauvegardée automatiquement.

## Comment jouer

### Cycle de vie

Chaque animal traverse quatre stades, en fonction de son âge en jeu :

| Stade | Condition |
|---|---|
| 🥚 Œuf | de 0 à 2h de jeu |
| 👶 Bébé | jusqu'à 2 jours de jeu |
| 🧒 Ado | jusqu'à 5 jours de jeu |
| 🦖 Adulte | au-delà |

Un adulte en bonne santé et de bonne humeur peut pondre un nouvel œuf de
façon spontanée (jusqu'à **6 animaux vivants** simultanément dans l'élevage).

### Statistiques

Cinq jauges (0-100) évoluent en continu, plus vite la nuit calme (21h-6h,
décroissance ×0,4) que le jour :

- **Faim** et **Soif** montent avec le temps ; au-delà de 90, la santé
  chute.
- **Humeur** baisse avec le temps ; en dessous de 15, la santé chute.
- **Propreté** (en fait la saleté) monte avec le temps ; au-delà de 90, la
  santé chute.
- **Santé** régénère toute seule si les quatre autres jauges restent dans
  des valeurs correctes, sinon elle diminue. **Si la santé tombe à 0,
  l'animal meurt.**

### Actions

| Action | Effet | Recharge |
|---|---|---|
| 🍔 Nourrir | selon la provision utilisée (voir ci-dessous) | 12 s |
| 💉 Soigner | +25 santé | 45 s |
| 🤗 Caresser | +15 humeur | 6 s |
| 🧹 Nettoyer | remet la propreté à 0 | 4 s |
| 🔎 Chercher des provisions | ajoute une provision aléatoire à l'inventaire | 25 s − 5 s par animal au-delà du premier (min. 10 s ; 1 s sans aucun animal, pour faire des réserves à l'avance) |

### Provisions

| Provision | Faim | Soif | Santé | Humeur | Saleté |
|---|---|---|---|---|---|
| 🥤 Coca | — | -10 | — | +30 | — |
| 💧 Eau | — | -40 | — | -20 | — |
| 🍔 Hamburger | -100 | +30 | -10 | — | — |
| 🍉 Pastèque | -20 | -30 | — | — | — |
| 🥣 Croquettes *(rare, 1 chance sur 20)* | = 0 % | = 0 % | = 100 % | = 100 % | = 90 % |

Les Croquettes sont les seules provisions qui peuvent régénérer l'animal et le sauver d'une mort certaine, — et aussi les seules à salir l'animal.

### Horloge du jeu

La barre du haut affiche le jour et l'heure en jeu, et permet de :

- ⏸️ **Mettre en pause** l'écoulement du temps ;
- régler la **vitesse** de 0,25× à 5× ;
- 🔄 **Réinitialiser** la partie (repart de zéro, sans animal).

## Structure du projet

```
app.py                 Serveur Flask : pages + API JSON
game/
  models.py            Animal, Provision et sous-classes, règles d'équilibrage
  engine.py            Avancement du temps (tick), construction de l'état envoyé au front
  storage.py            Sauvegarde/chargement d'une partie par session (JSON)
templates/index.html   Page unique du jeu
static/js/game.js      Logique front (appels API, rendu, minuterie)
static/css/style.css   Habillage visuel
data/saves/            Sauvegardes JSON, une par session (généré automatiquement)
```

## Sauvegarde

Chaque partie est stockée dans `data/saves/<id_session>.json` et persiste
entre les redémarrages du serveur. Il n'y a pas de compte ni de base de
données : l'identifiant de session vit dans le cookie `tamagoshi_sid` de
votre navigateur.

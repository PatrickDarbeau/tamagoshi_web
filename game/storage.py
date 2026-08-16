"""Sauvegarde persistante d'une partie dans un fichier JSON par session."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

SAVE_DIR = Path(__file__).resolve().parent.parent / "data" / "saves"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _chemin(sid):
    return SAVE_DIR / f"{sid}.json"


def sauvegarde_par_defaut():
    return {
        "cree_le": now_iso(),
        "dernier_maj": now_iso(),
        "minutes_jeu_ecoulees": 0.0,
        "animaux": [],
        "provisions": [],
        "prochaine_recolte": now_iso(),
        "messages": [],
        "en_pause": False,
        "vitesse": 1.0,
    }


def charger(sid):
    chemin = _chemin(sid)
    if not chemin.exists():
        return sauvegarde_par_defaut()
    with chemin.open("r", encoding="utf-8") as f:
        return json.load(f)


def enregistrer(sid, save):
    chemin = _chemin(sid)
    tmp = chemin.with_suffix(f".{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(save, f, ensure_ascii=False, indent=2)
    tmp.replace(chemin)


def nouveau_sid():
    return uuid.uuid4().hex

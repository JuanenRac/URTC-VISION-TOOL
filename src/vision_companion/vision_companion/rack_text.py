# =============================================================================
# URTC-VISION-TOOL - vision_companion texts of the rack check in eight languages: rack_text.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# The verdicts of rack_check.py are identifiers (they go to JSON and to the exit code unchanged); this table only gives a person the
# same words in their own language. Every language has every key: a test fails when one is missing.
from __future__ import annotations

LANGUAGES = ("en", "es", "de", "fr", "it", "ja", "zh", "pt")

KEYS = (
    "unknown", "empty_ok", "heater_in_empty_slot", "idle_ok", "still_hot", "heating", "reached", "not_reached", "overshoot",
    "occupied", "empty", "ordered", "read", "no_reading", "fault", "swap_ok", "swap_wait", "swap_blocked",
    "reached_after", "never_reached", "slot",
)

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "unknown": "no reading", "empty_ok": "empty and cold", "heater_in_empty_slot": "heater on in an empty slot", "idle_ok": "idle and cold",
        "still_hot": "still hot, told to stay cold", "heating": "heating", "reached": "target reached", "not_reached": "target not reached in time",
        "overshoot": "too hot", "occupied": "occupied", "empty": "empty", "ordered": "ordered", "read": "read", "no_reading": "no reading",
        "fault": "FAULT", "swap_ok": "the tool can be swapped", "swap_wait": "wait: the tip is not stable at the target yet",
        "swap_blocked": "do not swap: a fault in this slot", "reached_after": "reached after {s} s", "never_reached": "never reached", "slot": "slot",
    },
    "es": {
        "unknown": "sin lectura", "empty_ok": "vacío y frío", "heater_in_empty_slot": "calentador encendido en un hueco vacío", "idle_ok": "en reposo y frío",
        "still_hot": "aún caliente, debía estar frío", "heating": "calentando", "reached": "objetivo alcanzado", "not_reached": "objetivo no alcanzado a tiempo",
        "overshoot": "demasiado caliente", "occupied": "ocupado", "empty": "vacío", "ordered": "ordenado", "read": "leído", "no_reading": "sin lectura",
        "fault": "FALLO", "swap_ok": "se puede cambiar la herramienta", "swap_wait": "espera: la punta aún no es estable en el objetivo",
        "swap_blocked": "no cambiar: hay un fallo en este hueco", "reached_after": "alcanzado a los {s} s", "never_reached": "nunca alcanzado", "slot": "hueco",
    },
    "de": {
        "unknown": "kein Messwert", "empty_ok": "leer und kalt", "heater_in_empty_slot": "Heizung an in einem leeren Fach", "idle_ok": "im Leerlauf und kalt",
        "still_hot": "noch heiß, sollte kalt bleiben", "heating": "heizt auf", "reached": "Ziel erreicht", "not_reached": "Ziel nicht rechtzeitig erreicht",
        "overshoot": "zu heiß", "occupied": "belegt", "empty": "leer", "ordered": "befohlen", "read": "gelesen", "no_reading": "kein Messwert",
        "fault": "FEHLER", "swap_ok": "das Werkzeug kann gewechselt werden", "swap_wait": "warten: die Spitze ist noch nicht stabil auf Zieltemperatur",
        "swap_blocked": "nicht wechseln: Fehler in diesem Fach", "reached_after": "erreicht nach {s} s", "never_reached": "nie erreicht", "slot": "Fach",
    },
    "fr": {
        "unknown": "pas de mesure", "empty_ok": "vide et froid", "heater_in_empty_slot": "chauffage allumé dans un emplacement vide", "idle_ok": "au repos et froid",
        "still_hot": "encore chaud, devait rester froid", "heating": "en chauffe", "reached": "cible atteinte", "not_reached": "cible non atteinte à temps",
        "overshoot": "trop chaud", "occupied": "occupé", "empty": "vide", "ordered": "commandé", "read": "lu", "no_reading": "pas de mesure",
        "fault": "DÉFAUT", "swap_ok": "l'outil peut être changé", "swap_wait": "attendre : la pointe n'est pas encore stable à la cible",
        "swap_blocked": "ne pas changer : défaut dans cet emplacement", "reached_after": "atteinte après {s} s", "never_reached": "jamais atteinte", "slot": "emplacement",
    },
    "it": {
        "unknown": "nessuna lettura", "empty_ok": "vuoto e freddo", "heater_in_empty_slot": "riscaldatore acceso in uno slot vuoto", "idle_ok": "a riposo e freddo",
        "still_hot": "ancora caldo, doveva restare freddo", "heating": "in riscaldamento", "reached": "obiettivo raggiunto", "not_reached": "obiettivo non raggiunto in tempo",
        "overshoot": "troppo caldo", "occupied": "occupato", "empty": "vuoto", "ordered": "ordinato", "read": "letto", "no_reading": "nessuna lettura",
        "fault": "GUASTO", "swap_ok": "l'utensile può essere cambiato", "swap_wait": "attendere: la punta non è ancora stabile sull'obiettivo",
        "swap_blocked": "non cambiare: guasto in questo slot", "reached_after": "raggiunto dopo {s} s", "never_reached": "mai raggiunto", "slot": "slot",
    },
    "ja": {
        "unknown": "読み取りなし", "empty_ok": "空で低温", "heater_in_empty_slot": "空のスロットでヒーターが作動中", "idle_ok": "待機中で低温",
        "still_hot": "まだ高温（低温のはず）", "heating": "加熱中", "reached": "目標に到達", "not_reached": "時間内に目標へ未到達",
        "overshoot": "高温すぎる", "occupied": "使用中", "empty": "空", "ordered": "指令", "read": "測定", "no_reading": "読み取りなし",
        "fault": "異常", "swap_ok": "工具を交換できます", "swap_wait": "待機：先端はまだ目標温度で安定していません",
        "swap_blocked": "交換不可：このスロットに異常があります", "reached_after": "{s} 秒で到達", "never_reached": "未到達", "slot": "スロット",
    },
    "zh": {
        "unknown": "无读数", "empty_ok": "空位且为冷态", "heater_in_empty_slot": "空槽位的加热器已开启", "idle_ok": "待机且为冷态",
        "still_hot": "仍然很热，应保持冷态", "heating": "加热中", "reached": "已达目标", "not_reached": "未在时限内达到目标",
        "overshoot": "过热", "occupied": "有工具", "empty": "空", "ordered": "指令", "read": "读数", "no_reading": "无读数",
        "fault": "故障", "swap_ok": "可以更换工具", "swap_wait": "请等待：烙铁头尚未稳定在目标温度",
        "swap_blocked": "请勿更换：此槽位有故障", "reached_after": "{s} 秒后达到", "never_reached": "从未达到", "slot": "槽位",
    },
    "pt": {
        "unknown": "sem leitura", "empty_ok": "vazio e frio", "heater_in_empty_slot": "aquecedor ligado numa posição vazia", "idle_ok": "em repouso e frio",
        "still_hot": "ainda quente, devia estar frio", "heating": "a aquecer", "reached": "objetivo atingido", "not_reached": "objetivo não atingido a tempo",
        "overshoot": "demasiado quente", "occupied": "ocupada", "empty": "vazia", "ordered": "ordenado", "read": "lido", "no_reading": "sem leitura",
        "fault": "AVARIA", "swap_ok": "a ferramenta pode ser trocada", "swap_wait": "aguarde: a ponta ainda não está estável no objetivo",
        "swap_blocked": "não trocar: há uma avaria nesta posição", "reached_after": "atingido após {s} s", "never_reached": "nunca atingido", "slot": "posição",
    },
}


def text(key: str, lang: str = "en", **values: object) -> str:
    """The words for ``key`` in ``lang`` (English when the language is unknown)."""
    table = TEXTS.get(lang) or TEXTS["en"]
    return table.get(key, TEXTS["en"].get(key, key)).format(**values)

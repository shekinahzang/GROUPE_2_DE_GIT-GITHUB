# converters/units.py

from typing import Dict

def convertir_longueur(valeur: float, de: str, vers: str) -> float:
    conversions: Dict[str, float] = {
        'm': 1.0,
        'cm': 0.01,
        'mm': 0.001,
        'km': 1000.0,
        'in': 0.0254,
        'ft': 0.3048,
        'yd': 0.9144,
        'mi': 1609.34
    }
    if de not in conversions or vers not in conversions:
        raise ValueError(f"Unité de longueur non reconnue : {de} ou {vers}")
    return valeur * conversions[de] / conversions[vers]


def convertir_masse(valeur: float, de: str, vers: str) -> float:
    conversions: Dict[str, float] = {
        'kg': 1.0,
        'g': 0.001,
        'mg': 0.000001,
        'lb': 0.453592,
        'oz': 0.0283495,
        't': 1000.0
    }
    if de not in conversions or vers not in conversions:
        raise ValueError(f"Unité de masse non reconnue : {de} ou {vers}")
    return valeur * conversions[de] / conversions[vers]


def convertir_temperature(valeur: float, de: str, vers: str) -> float:
    if de == vers:
        return valeur

    if de == 'C':
        if vers == 'F':
            return valeur * 9 / 5 + 32
        elif vers == 'K':
            return valeur + 273.15

    elif de == 'F':
        if vers == 'C':
            return (valeur - 32) * 5 / 9
        elif vers == 'K':
            return (valeur - 32) * 5 / 9 + 273.15

    elif de == 'K':
        if vers == 'C':
            return valeur - 273.15
        elif vers == 'F':
            return (valeur - 273.15) * 9 / 5 + 32

    raise ValueError(f"Unité de température non reconnue : {de} ou {vers}")
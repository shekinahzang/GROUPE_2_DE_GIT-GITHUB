# converters/currency.py

import requests
from typing import Optional

def convertir_devise(montant: float, de: str, vers: str) -> Optional[float]:
    url: str = f"https://api.exchangerate.host/convert?from={de}&to={vers}&amount={montant}"
    try:
        reponse: requests.Response = requests.get(url)
        data: dict = reponse.json()
        taux: Optional[float] = data.get("result")
        return taux
    except Exception as e:
        print(f"Erreur lors de la conversion de devise : {e}")
        return None
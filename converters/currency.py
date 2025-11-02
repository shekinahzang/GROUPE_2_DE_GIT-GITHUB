def convertir_devise(montant, de, vers):
    taux = {
        "EUR": 1.00,
        "USD": 1.08,   # 1 EUR = 1.08 USD
        "XAF": 655.96, # 1 EUR = 655.96 FCFA
        "GBP": 0.86,   # 1 EUR = 0.86 GBP
        "CAD": 1.47,   # 1 EUR = 1.47 CAD
        "JPY": 162.50  # 1 EUR = 162.50 JPY
    }

    if de not in taux or vers not in taux:
        raise ValueError("Devise non supportée")

    # Convertir en EUR puis vers la devise cible
    montant_eur = montant / taux[de]
    return montant_eur * taux[vers]

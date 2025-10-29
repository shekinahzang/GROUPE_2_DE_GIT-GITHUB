# ui/interface.py

import tkinter as tk
from tkinter import ttk, messagebox

from calculator.safe_eval import evaluer_expression
from converters.units import convertir_longueur, convertir_masse, convertir_temperature
from converters.currency import convertir_devise


def lancer_interface() -> None:
    fenetre = tk.Tk()
    fenetre.title("Calculatrice & Convertisseur")
    fenetre.geometry("500x400")

    onglets = ttk.Notebook(fenetre)
    onglet_calc = ttk.Frame(onglets)
    onglet_unites = ttk.Frame(onglets)
    onglet_devises = ttk.Frame(onglets)

    onglets.add(onglet_calc, text="Calculatrice")
    onglets.add(onglet_unites, text="Convertisseur d'unités")
    onglets.add(onglet_devises, text="Convertisseur de devises")
    onglets.pack(expand=1, fill="both")

    # 🧮 Onglet Calculatrice
    champ_expr = tk.Entry(onglet_calc, width=40)
    champ_expr.pack(pady=10)

    label_resultat_calc = tk.Label(onglet_calc, text="Résultat :")
    label_resultat_calc.pack()

    def calculer_expression() -> None:
        expr = champ_expr.get()
        try:
            resultat = evaluer_expression(expr)
            label_resultat_calc.config(text=f"Résultat : {resultat}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Expression invalide : {e}")

    bouton_calc = tk.Button(onglet_calc, text="Calculer", command=calculer_expression)
    bouton_calc.pack(pady=5)

    # 📏 Onglet Unités
    types_unites = ["longueur", "masse", "température"]
    unite_type = tk.StringVar(value=types_unites[0])
    menu_type = ttk.Combobox(onglet_unites, textvariable=unite_type, values=types_unites)
    menu_type.pack(pady=5)

    champ_valeur = tk.Entry(onglet_unites)
    champ_valeur.pack(pady=5)

    champ_de = tk.Entry(onglet_unites)
    champ_de.pack(pady=5)
    champ_de.insert(0, "m")

    champ_vers = tk.Entry(onglet_unites)
    champ_vers.pack(pady=5)
    champ_vers.insert(0, "cm")

    label_resultat_unite = tk.Label(onglet_unites, text="Résultat :")
    label_resultat_unite.pack()

    def convertir_unite() -> None:
        try:
            valeur = float(champ_valeur.get())
            de = champ_de.get()
            vers = champ_vers.get()
            type_u = unite_type.get()

            if type_u == "longueur":
                resultat = convertir_longueur(valeur, de, vers)
            elif type_u == "masse":
                resultat = convertir_masse(valeur, de, vers)
            elif type_u == "température":
                resultat = convertir_temperature(valeur, de, vers)
            else:
                raise ValueError("Type d'unité inconnu")

            label_resultat_unite.config(text=f"Résultat : {resultat:.4f}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Conversion impossible : {e}")

    bouton_convertir_unite = tk.Button(onglet_unites, text="Convertir", command=convertir_unite)
    bouton_convertir_unite.pack(pady=5)

    # 💱 Onglet Devises
    champ_montant = tk.Entry(onglet_devises)
    champ_montant.pack(pady=5)
    champ_montant.insert(0, "100")

    champ_devise_de = tk.Entry(onglet_devises)
    champ_devise_de.pack(pady=5)
    champ_devise_de.insert(0, "EUR")

    champ_devise_vers = tk.Entry(onglet_devises)
    champ_devise_vers.pack(pady=5)
    champ_devise_vers.insert(0, "USD")

    label_resultat_devise = tk.Label(onglet_devises, text="Résultat :")
    label_resultat_devise.pack()

    def convertir_devise_action() -> None:
        try:
            montant = float(champ_montant.get())
            de = champ_devise_de.get().upper()
            vers = champ_devise_vers.get().upper()
            resultat = convertir_devise(montant, de, vers)
            if resultat is not None:
                label_resultat_devise.config(text=f"{montant} {de} = {resultat:.2f} {vers}")
            else:
                raise ValueError("Conversion échouée")
        except Exception as e:
            messagebox.showerror("Erreur", f"Conversion impossible : {e}")

    bouton_convertir_devise = tk.Button(onglet_devises, text="Convertir", command=convertir_devise_action)
    bouton_convertir_devise.pack(pady=5)

    fenetre.mainloop()
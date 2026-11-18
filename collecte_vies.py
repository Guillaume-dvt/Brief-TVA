import argparse
import logging
import os
import time
import requests
import pandas as pd

FICHIER_REFERENTIEL = "referentiel_nettoye.csv"
FICHIER_SORTIE_DEFAUT = "resultats_vies_200.csv"
FICHIER_LOG = "collecte_vies.log"

TIMEOUT_SEC = 20          # Justifié par les ~10 s observées sur le Danemark
PAUSE_ENTRE_APPELS = 1.0  # Temporisation polie entre appels
MAX_RETRIES = 3           # Relances en cas d'indisponibilité temporaire

ERREURS_TEMPORAIRES = {
    "MS_MAX_CONCURRENT_REQ",
    "MS_UNAVAILABLE",
    "SERVICE_UNAVAILABLE",
    "SERVER_BUSY",
    "GLOBAL_MAX_CONCURRENT_REQ",
}


def configurer_logger(fichier_log: str) -> logging.Logger:
    """Configure le journal de collecte (fichier + console)."""
    logger = logging.getLogger("collecte_vies")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatteur = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(fichier_log, encoding="utf-8")
    fh.setFormatter(formatteur)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatteur)
    logger.addHandler(ch)

    return logger


def tirer_echantillon(fichier_ref: str, taille: int, seed: int = 42) -> list[str]:
    """Tire un échantillon stratifié par pays et alterne les pays (round-robin)."""
    df = pd.read_csv(fichier_ref, keep_default_na=False)
    ok_uniques = df[df["motif_propre"] == "ok"].drop_duplicates(subset=["tva_propre"]).copy()
    ok_uniques["pays"] = ok_uniques["tva_propre"].str[:2]

    if taille <= 0 or taille >= len(ok_uniques):
        ech = ok_uniques
    else:
        nb_pays = ok_uniques["pays"].nunique()
        par_pays = max(1, taille // nb_pays)
        ech = (
            ok_uniques.groupby("pays", group_keys=False)
            .sample(n=par_pays, random_state=seed)
            .copy()
        )
        # Compléter si taille n'est pas un multiple de 10
        if len(ech) < taille:
            reste = ok_uniques[~ok_uniques["tva_propre"].isin(ech["tva_propre"])]
            ech = pd.concat([ech, reste.sample(n=taille - len(ech), random_state=seed)])

    # Alterner les pays (1 BE, 1 DK, 1 FI...) pour éviter de saturer un même serveur national
    ech["rang_pays"] = ech.groupby("pays").cumcount()
    ech = ech.sort_values(["rang_pays", "pays"])
    return ech["tva_propre"].tolist()


def interroger_vies(tva: str, logger: logging.Logger) -> dict:
    """Interroge l'API REST VIES pour un numéro normalisé avec relances."""
    pays, numero = tva[:2], tva[2:]
    url = f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{pays}/vat/{numero}"

    for tentative in range(1, MAX_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            resp = requests.get(url, timeout=TIMEOUT_SEC)
            duree = round(time.perf_counter() - t0, 3)

            if resp.status_code != 200:
                user_error = f"HTTP_{resp.status_code}"
                logger.warning(
                    f"Appel {tva} | HTTP {resp.status_code} | {duree}s | essai {tentative}/{MAX_RETRIES} | erreur={user_error}"
                )
                if resp.status_code >= 500 and tentative < MAX_RETRIES:
                    time.sleep(3 * tentative)
                    continue
                return {
                    "tva_propre": tva,
                    "pays": pays,
                    "statut_vies": "indisponible",
                    "is_valid": False,
                    "user_error": user_error,
                    "nom_vies": "",
                    "adresse_vies": "",
                    "date_requete": "",
                    "duree_s": duree,
                    "tentatives": tentative,
                }

            data = resp.json()
            is_valid = bool(data.get("isValid", False))
            user_error = str(data.get("userError", ""))

            if not is_valid and user_error in ERREURS_TEMPORAIRES:
                logger.warning(
                    f"Appel {tva} | HTTP {resp.status_code} | {duree}s | essai {tentative}/{MAX_RETRIES} | erreur={user_error}"
                )
                if tentative < MAX_RETRIES:
                    time.sleep(3 * tentative)
                    continue
                statut_vies = "indisponible"
            elif is_valid:
                statut_vies = "valide"
            elif user_error == "INVALID":
                statut_vies = "invalide"
            else:
                statut_vies = "indisponible"

            logger.info(
                f"Appel {tva} | HTTP {resp.status_code} | {duree}s | statut={statut_vies} | userError={user_error}"
            )
            return {
                "tva_propre": tva,
                "pays": pays,
                "statut_vies": statut_vies,
                "is_valid": is_valid,
                "user_error": user_error,
                "nom_vies": str(data.get("name", "")).strip(),
                "adresse_vies": str(data.get("address", "")).replace("\n", " ").strip(),
                "date_requete": str(data.get("requestDate", "")),
                "duree_s": duree,
                "tentatives": tentative,
            }

        except requests.RequestException as exc:
            duree = round(time.perf_counter() - t0, 3)
            err_nom = type(exc).__name__
            logger.warning(
                f"Appel {tva} | ERREUR_RESEAU ({err_nom}) | {duree}s | essai {tentative}/{MAX_RETRIES}"
            )
            if tentative < MAX_RETRIES:
                time.sleep(3 * tentative)
                continue
            return {
                "tva_propre": tva,
                "pays": pays,
                "statut_vies": "indisponible",
                "is_valid": False,
                "user_error": f"ERREUR_RESEAU:{err_nom}",
                "nom_vies": "",
                "adresse_vies": "",
                "date_requete": "",
                "duree_s": duree,
                "tentatives": tentative,
            }


def main():
    parser = argparse.ArgumentParser(description="Collecte VIES sur échantillon de numéros de TVA.")
    parser.add_argument("--echantillon", type=int, default=200, help="Nombre de numéros à vérifier (0 = tout)")
    parser.add_argument("--sortie", type=str, default=FICHIER_SORTIE_DEFAUT, help="Fichier CSV de sortie")
    args = parser.parse_args()

    logger = configurer_logger(FICHIER_LOG)
    logger.info(f"=== DÉBUT DE CAMPAGNE VIES | mode_echantillon={args.echantillon} | sortie={args.sortie} ===")

    numeros = tirer_echantillon(FICHIER_REFERENTIEL, args.echantillon)

    deja_faits = set()
    if os.path.exists(args.sortie):
        df_existant = pd.read_csv(args.sortie)
        deja_faits = set(df_existant["tva_propre"].tolist())

    nb_sautes = 0
    nb_appels = 0

    for tva in numeros:
        if tva in deja_faits:
            nb_sautes += 1
            logger.info(f"Numéro déjà vérifié, ignoré : {tva}")
            continue

        res = interroger_vies(tva, logger)
        df_ligne = pd.DataFrame([res])
        ecrire_entete = not os.path.exists(args.sortie)
        df_ligne.to_csv(args.sortie, mode="a", header=ecrire_entete, index=False)
        nb_appels += 1
        time.sleep(PAUSE_ENTRE_APPELS)

    logger.info(
        f"=== FIN DE CAMPAGNE VIES | nouveaux_appels={nb_appels} | deja_verifies_sautes={nb_sautes} ==="
    )


if __name__ == "__main__":
    main()
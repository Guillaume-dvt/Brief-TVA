# Journal de bord — Audit du référentiel TVA (Meridian Distribution)

## Jour 1 — Exploration et nettoyage du référentiel

### Matin : Phase 1 — Exploration brute (`01_exploration.ipynb`)
* **Actions réalisées :** comparaison entre `numeros_tva.csv` et `numeros_tva.xlsx`, inventaire des pays déclarés, des formats de saisie, des valeurs manquantes et des écarts entre `pays_declare` et préfixe du numéro.
* **Blocage / Point de vigilance :** lors du chargement standard avec `pandas.read_csv()`, certaines chaînes comme `"N/A"` ou `"null"` sont converties automatiquement en `NaN`, contrairement à `"NU.LL"` ou `"-"`, ce qui crée un décalage entre le CSV et l'Excel.
* **Résolution :** chargement systématique avec `keep_default_na=False`, choix du **CSV** comme source de vérité unique (format texte brut sans risque de reformatage Excel des zéros initiaux) et recensement explicite des 6 formes de vide (`261` lignes).

### Après-midi : Phase 2 — Normalisation, filtrage et entonnoir (`02_analyse.ipynb`)
* **Actions réalisées :** lecture et intégration de `validation_structure.py` (`normaliser()` et `valider()`), rattrapage des numéros sans préfixe via `pays_declare`, définition de la règle de dédoublonnage et calcul de l'entonnoir de réduction.
* **Décisions métier prises :**
  * Conservation de la première occurrence non vide de chaque `tva_propre` comme référence et marquage des `438` occurrences suivantes comme doublons.
  * Élimination préalable de `3 385` lignes structurellement invalides (`2 605` clés fausses, `519` pays non couverts, `261` vides), ramenant le volume à **`6 302` numéros uniques** à interroger sur VIES (**-37 % d'appels API économisés**).
* **Estimation de charge :** sur la base d'un temps de réponse moyen observé autour de `0,6 s` à `1,0 s` et d'une temporisation de `1,2 s` entre appels, une campagne complète sur les `6 302` numéros prendrait environ **2 h 15 à 2 h 30**.

---

## Jour 2 — Collecte VIES, analyse statistique et restitution

### Matin : Phase 3 — Appels API et script de collecte (`collecte_vies.py`)
* **Actions réalisées :** tests manuels sur l'API REST VIES, analyse de la structure complète du JSON retourné (`isValid`, `requestDate`, `userError`), puis développement du script `collecte_vies.py`.
* **Blocage rencontré :** lors des premiers tests en rafale sur un même pays, l'API VIES renvoie le code `userError: "MS_MAX_CONCURRENT_REQ"` (saturation des serveurs nationaux, notamment sur `FR`, `NL` et `BE`). Confondre cette erreur technique avec un numéro invalide fausserait l'audit fiscal.
* **Résolution :**
  1. Distinction explicite entre le statut `invalide` (`isValid == False` sans erreur serveur) et `indisponible` (classé en **Non tranché** dans le rapport DAF).
  2. Mise en place d'un ordonnancement en **tourniquet (round-robin)** par pays, d'une temporisation paramétrable (`--delai 1.2`), d'une journalisation structurée via `logging` (`collecte_vies.log`) et d'une **reprise idempotente** ignorant les numéros déjà traités.
  3. Exécution réussie sur l'échantillon stratifié de **200 numéros** (`20` par pays) : `3` valides, `163` invalides et `34` indisponibles.

### Après-midi : Phase 4 & 5 — Réconciliation, graphiques WCAG et livrables
* **Actions réalisées :** croisement des `10 000` lignes dans `02_analyse.ipynb` (`rapport_reconciliation.csv`), analyse par canal et trimestre (taux d'anomalie constant autour de `33,85 %`), génération des 4 graphiques accessibles (`figures/`) et rédaction de `note_daf.md` et `README.md`.
* **Blocage rencontré :** erreur `ImportError: cannot import name '_api' from partially initialized module 'matplotlib'` dans le notebook sous Python 3.14, suivie d'une erreur `pip` (`uninstall-no-record-file`) due à une installation interrompue de `matplotlib 3.11.2`.
* **Résolution :** redémarrage du noyau Jupyter pour libérer les fichiers verrouillés, suppression manuelle du dossier corrompu dans `site-packages/matplotlib*`, puis réinstallation propre avec `pip install --no-cache-dir matplotlib`.
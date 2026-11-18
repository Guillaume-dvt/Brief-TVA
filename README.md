# Audit d'un référentiel de TVA intracommunautaire avec l'API VIES

**Auteur :** [Guillaume]  
**Formation :** Concepteur développeur en IA et analyse big data (RNCP 38616 — Option Data Analyse)  

---

## 1. Contexte et objectif du projet

À la suite d'un contrôle fiscal ayant sanctionné des factures émises hors taxe (autoliquidation intracommunautaire) sur la base de numéros de TVA invalides, **Meridian Distribution** souhaite auditer son référentiel clients composé de **10 000 lignes** accumulées sur huit ans via cinq canaux distincts (CRM, import fournisseur, saisie manuelle, portail client, reprise ERP).

L'objectif de ce projet est de répondre de manière chiffrée, reproductible et opposable à la question de la Direction Administrative et Financière (DAF) :
> **« Parmi nos 10 000 numéros, lesquels sont valides, lesquels ne le sont pas — et lesquels n'ont pas pu être tranchés ? »**

### Principaux résultats de l'audit
* **37 % d'appels API économisés** avant toute interrogation externe grâce à la normalisation, au dédoublonnage (**438 doublons** non vides) et au filtrage structurel/mathématique (`6 302` numéros uniques conformes sur `10 000` lignes).
* **Réconciliation des 10 000 lignes :**
  * **4 lignes (0,04 %)** confirmées **valides** par l'API officielle VIES ;
  * **3 565 lignes (35,65 %)** prouvées **invalides** (`3 385` rejets structurels avant VIES + `180` rejets par l'API VIES) ;
  * **6 431 lignes (64,31 %)** **non tranchées** (`6 395` hors échantillon de 200 numéros + `36` bloquées par saturation temporaire des serveurs nationaux `MS_MAX_CONCURRENT_REQ`).

---

## 2. Architecture du dépôt

```text
Brief-TVA/
├── starter-kit/
│   ├── data/
│   │   ├── numeros_tva.csv          # Source de vérité brute (10 000 lignes)
│   │   └── numeros_tva.xlsx         # Doublon Excel (écart de typage détecté en Phase 1)
│   ├── validation_structure.py      # Module fourni : normalisation et contrôle des clés nationales
│   └── README.md                    # Documentation initiale du jeu de données
├── notebooks/
│   ├── 01_exploration.ipynb         # Phase 1 : exploration brute sans modification
│   └── 02_analyse.ipynb             # Phases 2 & 4 : nettoyage, entonnoir, réconciliation et graphiques WCAG
├── figures/                         # Graphiques haute définition (300 DPI, conformes WCAG 1.4.1 & 1.4.4)
│   ├── fig1_entonnoir_nettoyage.png
│   ├── fig2_reconciliation_10000.png
│   ├── fig3_echantillon_vies_pays.png
│   └── fig4_origine_erreurs.png
├── collecte_vies.py                 # Phase 3 : script automatisé d'interrogation de l'API REST VIES
├── collecte_vies.log                # Journal d'exécution structuré (module logging)
├── referentiel_nettoye.csv          # Référentiel enrichi des statuts structurels et doublons
├── echantillon_200.csv              # Échantillon stratifié (20 numéros × 10 pays UE)
├── resultats_vies_200.csv           # Réponses horodatées de la campagne VIES (200 appels)
├── rapport_reconciliation.csv       # Table de synthèse finale pour la direction financière
├── note_daf.md                      # Note de synthèse d'une page à destination de la DAF
├── journal_de_bord.md               # Suivi chronologique, blocages techniques et résolutions
└── README.md                        # Documentation principale du projet
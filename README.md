# PPC Project – The Circle of Life 🦊🌱🐑

## 📌 Présentation générale

**The Circle of Life** est un projet de programmation concurrente (PPC) visant à implémenter une **simulation multiprocessus d’un écosystème** en Python.

L’écosystème est composé de :

* **Prédateurs** (carnivores),
* **Proies** (herbivores),
* **Herbe** (ressource environnementale).

Chaque individu est simulé par un **processus indépendant**. Les interactions sont gérées via des mécanismes complets d’**IPC** (mémoire partagée, sockets, files de messages, signaux). Une **interface web** permet l’observation et le contrôle en temps réel.

---

# 🧠 Modèle de simulation

## Énergie et états

* Chaque individu possède une **énergie**
* L’énergie diminue à chaque tick
* Deux états possibles :

  * **Actif** : l’individu peut tenter de se nourrir
  * **Passif** : l’individu n’interagit pas

Le passage actif ↔ passif dépend du seuil d’énergie H = 30.

---
## ☠️ Mort

* Si l’énergie devient négative :

  * le processus meurt,
  * l’environnement est notifié,
  * les compteurs partagés sont mis à jour proprement.

---

## 🌱 Herbe et sécheresse

* L’herbe repousse automatiquement à chaque tick
* Lors d’une **sécheresse** :

  * la croissance est stoppée
  * l’événement est déclenché par **signal**
  * géré exclusivement par `env`

---

## 🍽️ Configurations probabilistes

### Nourriture : 

Les interactions dans notre projet sont **probabilistes** :

* Une **proie active** ne mange pas systématiquement de l’herbe (Une probabilité de 80%)
* Un **prédateur actif** ne réussit pas systématiquement à manger une proie (Une probabilité de 60%)
* Chaque tentative est soumise à une **probabilité de succès** différente du tick précédent. 

Ces probabilités permettent :

* d’éviter des dynamiques trop rigides,
* d’introduire de l’aléatoire réaliste,
* de favoriser des comportements émergents.

Les probabilités sont :

* **configurables** (via `config.py`)
* **mesurées et affichées** (moyennes globales dans les snapshots envoyés au display)

---

### 🧬 Reproduction probabiliste

La reproduction est également **non déterministe** :

* Un individu doit :

  * être vivant,
  * avoir une énergie supérieure à un seuil `R`
* Même si ces conditions sont réunies, la reproduction :

  * **n’est pas garantie**
  * dépend d’une **probabilité de reproduction**

Ce choix permet :

* de limiter les explosions démographiques,
* d’introduire une variabilité naturelle,
* de rendre la simulation plus stable à long terme.

---

## 🏗️ Architecture multiprocessus

| Processus  | Rôle                                              |
| ---------- | ------------------------------------------------- |
| `env`      | État global, populations, climat, statistiques    |
| `prey`     | Simulation d’une proie (1 processus = 1 individu) |
| `predator` | Simulation d’un prédateur                         |
| `display`  | Interface web et contrôle utilisateur             |

---

## 🔄 Communications inter-processus (IPC)

### Mémoire partagée

* Compteurs globaux (prédateurs, proies, herbe)
* Accès protégé par **Locks**
* Lecture par individus, écriture centralisée

### Sockets

* Connexion des processus `prey` et `predator` à `env`
* Handshake de démarrage
* Transmission des actions probabilistes (succès/échec)

### File de messages

* Communication `display → env`
* Envoi de commandes utilisateur
* Envoi périodique de **snapshots**, incluant :

  * statistiques d’énergie,
  * probabilités moyennes de nourriture,
  * probabilités moyennes de reproduction.

### Signaux

* Gestion des sécheresses
* Réception uniquement par le processus `env`

---

## 🖥️ Interface Web

* Visualisation temps réel :

  * populations,
  * herbe,
  * état climatique,
  * statistiques probabilistes
* Contrôle dynamique de la simulation
* Observation des effets des probabilités sur le long terme

---

## ▶️ Exécution

```bash
python3 main.py
```

Interface web :

```
https://anassfar.github.io/Circle-Of-Life/
```

---

## 🧪 Concepts PPC illustrés

* Multiprocessing Python
* Synchronisation (sections critiques)
* IPC complexe et réaliste
* Modélisation probabiliste
* Robustesse et cohérence globale

---

## 👥 Auteurs

Projet réalisé dans le cadre du cours **Programmation Parallèle et Concurrente (PPC)**.

* Anas Sfar
* Farah Gattoufi

---

## 📄 Licence

Projet académique – usage pédagogique uniquement.

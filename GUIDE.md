# 🚀 Guide complet — Bot 6-Man Rocket League

---

## 📁 Fichiers fournis

| Fichier | Rôle |
|---|---|
| `bot.py` | Le bot Discord (code principal) |
| `requirements.txt` | Dépendances Python |
| `Procfile` | Indique à Railway comment lancer le bot |
| `runtime.txt` | Version Python utilisée |
| `.gitignore` | Fichiers à ne pas envoyer sur GitHub |

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ÉTAPE 1 — Créer le bot Discord
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Va sur https://discord.com/developers/applications
2. Clique **"New Application"** → donne un nom (ex: "6Man RL")
3. Va dans l'onglet **"Bot"** (menu gauche)
4. Clique **"Reset Token"** → confirme → **copie le token** (garde-le précieusement)
5. Sur la même page, active ces deux options :
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Va dans **"OAuth2"** → **"URL Generator"** (menu gauche)
   - Coche **"bot"** et **"applications.commands"**
   - Dans "Bot Permissions", coche :
     - ✅ Send Messages
     - ✅ Manage Messages (pour épingler)
     - ✅ Read Message History
     - ✅ Use Slash Commands
   - Copie l'URL tout en bas et ouvre-la dans ton navigateur
   - Sélectionne ton serveur → Autoriser

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ÉTAPE 2 — Mettre les fichiers sur GitHub
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Crée un compte sur https://github.com si tu n'en as pas
2. Clique **"New repository"** (bouton vert)
   - Nom : `6man-bot` (ou ce que tu veux)
   - Mets-le en **Privé** (pour ne pas exposer ton code)
   - Clique **"Create repository"**
3. Sur ton PC, ouvre un terminal dans le dossier qui contient les fichiers du bot et tape :

```bash
git init
git add .
git commit -m "premier commit"
git branch -M main
git remote add origin https://github.com/TON_USERNAME/6man-bot.git
git push -u origin main
```

> Si tu n'as pas Git : télécharge-le sur https://git-scm.com/downloads

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ÉTAPE 3 — Héberger sur Railway (gratuit)
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Va sur https://railway.app et connecte-toi avec ton compte GitHub
2. Clique **"New Project"**
3. Choisis **"Deploy from GitHub repo"**
4. Sélectionne ton repo `6man-bot`
5. Railway détecte Python automatiquement et lance le déploiement
6. Une fois déployé, va dans l'onglet **"Variables"** et ajoute :
   - Clé : `BOT_TOKEN`
   - Valeur : ton token Discord copié à l'étape 1
7. Puis ouvre `bot.py`, remplace la ligne :
   ```python
   BOT_TOKEN = "TON_TOKEN_ICI"
   ```
   par :
   ```python
   import os
   BOT_TOKEN = os.environ.get("BOT_TOKEN")
   ```
   Re-commit et push → Railway redéploie automatiquement.

8. Va dans l'onglet **"Deployments"** → tu dois voir le bot connecté dans les logs ✅

> Railway offre 5$/mois de crédits gratuits, ce qui équivaut à environ 500h de runtime.
> Pour un bot léger comme celui-ci c'est ~0.50$/mois, donc largement dans les clous.

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## ÉTAPE 4 — Configurer Discord
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sur ton serveur Discord, crée ces deux salons textuels :
- `#6man-queue` → le panneau de file apparaîtra ici
- `#6man-logs` → les logs des actions (optionnel)

Ensuite tape `/setup` dans `#6man-queue` → le panneau apparaît, c'est prêt ! 🎉

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## COMMANDES DISPONIBLES
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Joueurs
| Commande | Description |
|---|---|
| `/join` | Rejoindre la file |
| `/leave` | Quitter la file |
| `/queue` | Voir la file actuelle |
| `/rank` | Voir ton profil ELO |
| `/rank @joueur` | Voir le profil d'un autre joueur |
| `/leaderboard` | Classement ELO du serveur |
| `/win orange` | Reporter victoire équipe orange |
| `/win blue` | Reporter victoire équipe bleue |

### Admins (nécessite "Gérer le serveur")
| Commande | Description |
|---|---|
| `/setup` | Créer le panneau de file |
| `/clear` | Vider la file |
| `/kick @joueur` | Retirer un joueur de la file |
| `/add @joueur` | Ajouter un joueur à la file |
| `/shuffle` | Forcer un nouveau tirage |
| `/setelo @joueur 1200` | Définir l'ELO manuellement |
| `/resetelo @joueur` | Remettre un joueur à 800 ELO |

---

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━
## SYSTÈME ELO & RANGS
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Rang | ELO requis |
|---|---|
| 🔵 C3 | 0 |
| 🔵 C2 | 200 |
| 🔵 C1 | 400 |
| 🟣 B3 | 600 |
| 🟣 B2 | 800 ← départ |
| 🟣 B1 | 1000 |
| 🟡 A3 | 1200 |
| 🟡 A2 | 1500 |
| 🟡 A1 | 1800 |
| 🏆 SSL | 2200 |

**Gain moyen par match :** ±16 ELO sur des équipes équilibrées.
Les équipes sont formées automatiquement par snake draft ELO pour être équilibrées.
Les données ELO sont sauvegardées dans `elo_data.json` (persistant entre les redémarrages).

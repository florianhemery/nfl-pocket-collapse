# 🔴 MISTRAL - GUIDE DE DÉPANNAGE

## ❌ Erreur: "Invalid model: mistral"

### Problème
L'API Mistral rejette le nom de modèle "mistral" car ce n'est pas un nom de modèle valide.

### Solution
**Laisse le champ "Model" VIDE** ou utilise un nom de modèle complet.

---

## ✅ Configuration correcte

### Étape par étape :

1. **Clique sur ⚙️** (AI Settings)

2. **Sélectionne** "🔴 Mistral (Large, Small)"

3. **Entre ta clé API** Mistral

4. **Champ "Model" : LAISSE VIDE** ⬅️ C'EST IMPORTANT !
   - Vide = utilise `mistral-large-latest` (défaut, recommandé)
   - OU tape un nom complet : `mistral-small-latest`, `open-mixtral-8x7b`

5. **Clique "Connect AI"**

---

## 📋 Noms de modèles valides

### Modèles Mistral disponibles :

| Nom du modèle | Quand l'utiliser |
|---------------|------------------|
| `mistral-large-latest` | **Par défaut** - Le plus puissant, meilleur pour analyses complexes |
| `mistral-small-latest` | Plus rapide, moins cher, parfait pour questions simples |
| `mistral-medium-latest` | Équilibre entre vitesse et qualité |
| `open-mixtral-8x7b` | Open source, très rapide |
| `open-mistral-7b` | Plus petit, ultra-rapide |

### ❌ NE FONCTIONNE PAS :
- ❌ `mistral` (trop vague)
- ❌ `large` (incomplet)
- ❌ `mistral-large` (manque `-latest`)

### ✅ FONCTIONNE :
- ✅ Vide (utilise mistral-large-latest automatiquement)
- ✅ `mistral-large-latest`
- ✅ `mistral-small-latest`
- ✅ `open-mixtral-8x7b`

---

## 🔧 Correction automatique (maintenant active)

Le code corrige maintenant automatiquement certaines erreurs :

1. **"mistral"** → converti en `mistral-large-latest`
2. **"mistral-large"** → converti en `mistral-large-latest`
3. **"mistral-small"** → converti en `mistral-small-latest`
4. **Vide** → utilise `mistral-large-latest`

---

## 💡 Recommandation

**Pour la plupart des usages : LAISSE LE CHAMP VIDE**

Le modèle par défaut (`mistral-large-latest`) est le meilleur choix pour :
- Analyses de données NFL
- Insights stratégiques
- Explications détaillées
- Réponses en français

---

## 🚀 Maintenant ça marche !

1. **Rafraîchis la page** (Cmd+R / Ctrl+R)
2. **Configure Mistral** en laissant le champ Model **vide**
3. **Teste** avec : `analyze SEA`

---

## 📸 Exemple de configuration correcte

```
Provider: Mistral (Large, Small)  ✅
API Key: [ta clé]                 ✅
Model: [LAISSE VIDE]              ✅ ← Important !
```

Ou si tu veux un modèle spécifique :

```
Provider: Mistral (Large, Small)  ✅
API Key: [ta clé]                 ✅
Model: mistral-small-latest       ✅
```

---

**Le problème est résolu ! Rafraîchis et réessaie.**

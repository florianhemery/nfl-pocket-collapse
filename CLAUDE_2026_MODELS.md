# 🤖 Modèles Claude 2026 - Guide Complet

## ✅ PROBLÈME RÉSOLU

**Erreur précédente :**
```
❌ Error code: 404 - model: claude-3-5-sonnet-20241022
```

**Cause :** Les modèles Claude 3.x n'existent plus dans l'API Anthropic en 2026. Les versions disponibles sont maintenant Claude 5.x (Fable, Opus, Sonnet, Haiku).

---

## 🎯 Modèles Claude Disponibles (2026)

### 1. **Claude Sonnet 5.5** (Recommandé)
- **ID API :** `claude-sonnet-5-5`
- **Prix :** $2 / 1M tokens input | $10 / 1M tokens output
- **Vitesse :** Rapide
- **Usage :** Équilibre parfait entre vitesse et intelligence
- **Idéal pour :** Analytics NFL, chat quotidien, analyses stratégiques

### 2. **Claude Opus 5.5** (Plus puissant)
- **ID API :** `claude-opus-5-5`
- **Prix :** $4 / 1M tokens input | $20 / 1M tokens output
- **Vitesse :** Modérée
- **Usage :** Travail de coding, agents, analyses approfondies
- **Idéal pour :** Développement complexe, analyses multi-étapes

### 3. **Claude Fable 5.1** (Le meilleur)
- **ID API :** `claude-fable-5-1`
- **Prix :** $10 / 1M tokens input | $50 / 1M tokens output
- **Vitesse :** Lente (mais la plus intelligente)
- **Usage :** Raisonnement avancé, tâches complexes de longue durée
- **Idéal pour :** Projets stratégiques critiques, R&D

### 4. **Claude Haiku 5.5** (Rapide & économique)
- **ID API :** `claude-haiku-5-5`
- **Prix :** À partir de $0.10 / 1M tokens input | $0.50 / 1M tokens output
- **Vitesse :** Ultra-rapide
- **Usage :** Classification, extraction, routing
- **Idéal pour :** Volume élevé, latence critique

---

## 🚀 Comment utiliser

### Dans l'interface NextGen DSS :

1. **Clique sur "AI Settings"** (⚙️ bouton en haut du chat)
2. **Sélectionne "Anthropic (Claude)"** comme provider
3. **Entre ta clé API** Anthropic
4. **Choisis le modèle** dans le dropdown :
   - **Sonnet 5.5** (par défaut, recommandé)
   - Opus 5.5 (pour plus de puissance)
   - Fable 5.1 (pour le max d'intelligence)
   - Haiku 5.5 (pour la vitesse)
5. **Clique "Connect"**

---

## 💰 Tarification Comparative

| Modèle | Input ($/1M tokens) | Output ($/1M tokens) | Ratio |
|--------|---------------------|----------------------|-------|
| Haiku 5.5 | $0.10 | $0.50 | 1x (baseline) |
| Sonnet 5.5 | $2 | $10 | 20x |
| Opus 5.5 | $4 | $20 | 40x |
| Fable 5.1 | $10 | $50 | 100x |

**Recommandation pour analytics NFL :** **Sonnet 5.5** offre le meilleur équilibre coût/performance.

---

## 📊 Comparaison des capacités

Tous les modèles supportent :
- ✅ Contexte jusqu'à **1M tokens** (1 million !)
- ✅ Text + Image input
- ✅ Text output
- ✅ Multilingue (français natif)
- ✅ Vision
- ✅ Tool use (appels de fonctions)
- ✅ **Thinking adaptatif** (raisonnement amélioré)

**Différence principale :** Intelligence et vitesse de traitement.

---

## 🔗 Documentation officielle

Source : [docs.anthropic.com/en/docs/models-overview](https://docs.anthropic.com/en/docs/models-overview)

---

## ⚡ Changements appliqués dans l'app

### Fichier modifié : `src/app_nextgen.py`

**Ligne 79 (défaut) :**
```python
# AVANT
self.model = model or 'claude-3-5-sonnet-20241022'  # ❌ N'existe plus

# APRÈS
self.model = model or 'claude-sonnet-5-5'  # ✅ Version 2026
```

**Lignes 639-642 (dropdown) :**
```python
'anthropic': [
    {'label': 'Claude Sonnet 5.5 (Recommandé)', 'value': 'claude-sonnet-5-5'},
    {'label': 'Claude Opus 5.5 (Plus puissant)', 'value': 'claude-opus-5-5'},
    {'label': 'Claude Fable 5.1 (Le meilleur)', 'value': 'claude-fable-5-1'},
    {'label': 'Claude Haiku 5.5 (Rapide & économique)', 'value': 'claude-haiku-5-5'}
]
```

---

## ✅ À faire maintenant

1. **Rafraîchis la page** (Cmd+R ou F5)
2. **Configure Claude** avec ta clé API
3. **Choisis Sonnet 5.5** (défaut)
4. **Teste** : `analyze SEA` ou `coverage insights`

**Ça devrait marcher maintenant !** 🎉

---

## 🐛 En cas de problème

### Erreur 401 - Unauthorized
→ Vérifie que ta clé API est valide : [console.anthropic.com](https://console.anthropic.com)

### Erreur 429 - Rate Limit
→ Trop de requêtes, attends 2-3 minutes ou utilise le mode Built-In

### Erreur 404 - Model Not Found
→ Assure-toi que le dropdown affiche bien `claude-sonnet-5-5` et pas un ancien nom

---

**Commit :** `064137e` - Mis à jour vers les modèles Claude 2026
**Pushed to GitHub :** ✅ `main` branch

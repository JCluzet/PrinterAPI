# PrinterAPI — Documentation

Imprimante thermique 80mm connectée à un Raspberry Pi, accessible via HTTP depuis n'importe où.

## Base URL

```
https://printer.cluzhub.com
```

## Authentification

Tous les endpoints requièrent deux headers Cloudflare Access :

```
CF-Access-Client-Id: 3f410ca892b75421c8db9239126c564d.access
CF-Access-Client-Secret: b8a5cdb1b07dbf043281c3199b7588240eaadfe8f99a4c1511ee2b8e7cd65efb
```

---

## Endpoints

### GET /health

Vérifie que le service est en ligne. Pas besoin d'authentification.

**Réponse :**
```json
{ "status": "ok" }
```

---

### POST /print/document ✅ Recommandé

Imprime un document structuré. C'est l'endpoint principal à utiliser depuis n8n, un script, ou tout autre outil.

**Headers :**
```
Content-Type: application/json
CF-Access-Client-Id: <client-id>
CF-Access-Client-Secret: <client-secret>
```

**Body :**
```json
{
  "elements": [ ... ]
}
```

**Réponse success :**
```json
{ "status": "ok" }
```

**Réponse erreur imprimante :**
```json
{ "detail": "..." }   // HTTP 500
```

---

## Types d'éléments

### `title` — Titre en double taille, centré, gras

```json
{ "type": "title", "text": "Mon Titre" }
```

---

### `text` — Texte normal

```json
{
  "type": "text",
  "content": "Mon texte",
  "align": "left",
  "bold": false,
  "size": "normal"
}
```

| Champ | Valeurs | Défaut |
|-------|---------|--------|
| `align` | `"left"` · `"center"` · `"right"` | `"left"` |
| `bold` | `true` · `false` | `false` |
| `size` | `"normal"` · `"large"` · `"wide"` · `"tall"` | `"normal"` |

---

### `kv` — Ligne clé / valeur

```json
{ "type": "kv", "key": "Ajouts", "value": "+247 lignes" }
```

Rendu : `Ajouts.................+247 lignes`

---

### `separator` — Ligne de séparation

```json
{ "type": "separator" }
{ "type": "separator", "char": "=" }
```

Caractère par défaut : `-`. Répété sur toute la largeur du ticket.

---

### `feed` — Sauts de ligne

```json
{ "type": "feed", "lines": 2 }
```

| Champ | Défaut |
|-------|--------|
| `lines` | `1` |

---

### `qr` — QR code

```json
{
  "type": "qr",
  "url": "https://example.com",
  "size": 6
}
```

| Champ | Valeurs | Défaut |
|-------|---------|--------|
| `size` | `1` – `16` | `6` |

---

### `image` — Image (logo, graphe, photo)

```json
// Depuis une URL :
{ "type": "image", "url": "https://example.com/logo.png" }

// Encodée en base64 :
{ "type": "image", "data": "<base64-string>" }
```

- L'image est automatiquement redimensionnée à **384px** de large maximum
- Hauteur max : **2000px**
- Convertie en **noir et blanc**
- Formats supportés : PNG, JPEG, GIF, BMP, WebP

---

### `cut` — Coupe le papier

```json
{ "type": "cut" }
```

À mettre en dernier élément de chaque ticket.

---

## Exemple complet — Reçu de PR GitHub

```json
{
  "elements": [
    { "type": "title",     "text": "Pull Request mergée !" },
    { "type": "separator" },
    { "type": "kv",        "key": "PR",       "value": "#42" },
    { "type": "kv",        "key": "Auteur",   "value": "Jo Cluzet" },
    { "type": "kv",        "key": "Repo",     "value": "PrinterAPI" },
    { "type": "kv",        "key": "Ajouts",   "value": "+247" },
    { "type": "kv",        "key": "Suppres.", "value": "-18" },
    { "type": "separator" },
    { "type": "text",      "content": "Bien joué !", "align": "center", "bold": true },
    { "type": "feed",      "lines": 1 },
    { "type": "qr",        "url": "https://github.com/JCluzet/PrinterAPI/pull/42" },
    { "type": "feed",      "lines": 2 },
    { "type": "cut" }
  ]
}
```

---

## Exemple curl

```bash
curl -X POST https://printer.cluzhub.com/print/document \
  -H "Content-Type: application/json" \
  -H "CF-Access-Client-Id: <client-id>" \
  -H "CF-Access-Client-Secret: <client-secret>" \
  -d '{
    "elements": [
      { "type": "title",     "text": "Hello !" },
      { "type": "text",      "content": "Ca marche.", "align": "center" },
      { "type": "separator" },
      { "type": "kv",        "key": "Statut", "value": "OK" },
      { "type": "cut" }
    ]
  }'
```

---

## Exemple Python

```python
import requests

requests.post(
    'https://printer.cluzhub.com/print/document',
    headers={
        'CF-Access-Client-Id': '<client-id>',
        'CF-Access-Client-Secret': '<client-secret>',
    },
    json={
        'elements': [
            {'type': 'title',     'text': 'Hello !'},
            {'type': 'separator'},
            {'type': 'kv',        'key': 'Statut', 'value': 'OK'},
            {'type': 'cut'},
        ]
    }
)
```

---

## Exemple n8n (nœud HTTP Request)

| Champ | Valeur |
|-------|--------|
| Method | `POST` |
| URL | `https://printer.cluzhub.com/print/document` |
| Authentication | `Header Auth` |
| Header Name | `CF-Access-Client-Id` |
| Header Value | `<client-id>` |
| Body | `JSON` |

Ajouter un second header `CF-Access-Client-Secret` dans les options.

Dans le corps, construire le JSON avec un nœud **Code** ou **Set** en amont.

---

## Endpoint avancé — POST /print

Pour les cas où le document model ne suffit pas : envoi de bytes ESC/POS bruts.

**Body :**
```json
{ "raw": "<base64-encoded ESC/POS bytes>" }
```

```python
import base64, requests

ESC = b'\x1b'
GS  = b'\x1d'
data = ESC + b'@' + b'Hello\n\n\n' + GS + b'V\x41\x03'

requests.post(
    'https://printer.cluzhub.com/print',
    headers={'CF-Access-Client-Id': '...', 'CF-Access-Client-Secret': '...'},
    json={'raw': base64.b64encode(data).decode()}
)
```

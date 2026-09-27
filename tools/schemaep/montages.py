# tools/schemaep/montages.py
"""Montages types intégrés aux favoris (repris de la page HTML SchemAEP).

Chaque montage : id, nom, items (pièces au format .json). Sans « a », la
pose s'accroche à la première extrémité libre du montage.
"""
import json

MONTAGES = json.loads(r'''[
 {
  "id": "j-bi",
  "nom": "Bouche d’incendie",
  "items": [
   {
    "t": "te",
    "x": -102.7,
    "y": 7.3,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 100,
     "ext": "BBB",
     "but": true,
     "verr": false,
     "tb": 10
    }
   },
   {
    "t": "tuyau",
    "x": -102.7,
    "y": -72.7,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "EU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": -102.7,
    "y": 87.3,
    "r": 270,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "EU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "bi",
    "x": 87.3,
    "y": -36.7,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100
    }
   },
   {
    "t": "tuyau",
    "x": -92.7,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "vanne",
    "x": -12.7,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "ext": "BB",
     "man": "Carré de manœuvre",
     "bac": true,
     "reg": false
    }
   },
   {
    "t": "tuyau",
    "x": 7.3,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "patin",
    "x": 87.3,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "but": true
    }
   }
  ]
 },
 {
  "id": "j-branchement_prise_en_charge",
  "nom": "Branchement sur prise en charge",
  "items": [
   {
    "t": "prise",
    "x": 0,
    "y": 0,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 25,
     "typ": "Collier + robinet",
     "bac": true
    }
   },
   {
    "t": "tuyau",
    "x": -0.0,
    "y": -20,
    "r": 270,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "UU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": 0.0,
    "y": 20,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "UU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": 44,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "pe",
     "dn": 25,
     "ext": "UU",
     "L": 6,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "compteur",
    "x": 124,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 40,
     "typ": "Volumétrique",
     "log": "Regard de comptage",
     "tete": false
    }
   },
   {
    "t": "abonne",
    "x": 164,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "txt": ""
    }
   }
  ]
 },
 {
  "id": "j-branchement_prise_en_charge_precis",
  "nom": "Branchement sur prise en charge (détaillé)",
  "items": [
   {
    "t": "prise",
    "x": 10,
    "y": 0,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 25,
     "typ": "Collier + robinet",
     "bac": true
    }
   },
   {
    "t": "tuyau",
    "x": 10.0,
    "y": -20,
    "r": 270,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "UU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": 10.0,
    "y": 20,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "UU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "cfem",
    "x": 68,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "pe",
     "dn": 25,
     "fil": 20
    }
   },
   {
    "t": "tuyau",
    "x": 82,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "pe",
     "dn": 25,
     "ext": "UU",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "cfem",
    "x": 156,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "pe",
     "dn": 25,
     "fil": 20
    }
   },
   {
    "t": "compteur",
    "x": 190,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 20,
     "typ": "Volumétrique",
     "log": "Regard de comptage",
     "tete": false
    }
   },
   {
    "t": "abonne",
    "x": 230,
    "y": -0.0,
    "r": 0,
    "f": 1,
    "p": {
     "txt": ""
    }
   }
  ]
 },
 {
  "id": "j-pi",
  "nom": "Poteau d’incendie",
  "items": [
   {
    "t": "te",
    "x": -102.7,
    "y": 7.3,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 100,
     "ext": "BBB",
     "but": true,
     "verr": false,
     "tb": 10
    }
   },
   {
    "t": "tuyau",
    "x": -102.7,
    "y": -72.7,
    "r": 90,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": -102.7,
    "y": 87.3,
    "r": 270,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "tuyau",
    "x": -92.7,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "vanne",
    "x": -12.7,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "ext": "BB",
     "man": "Carré de manœuvre",
     "bac": true,
     "reg": false
    }
   },
   {
    "t": "tuyau",
    "x": 7.3,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "patin",
    "x": 87.3,
    "y": 7.3,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "but": true
    }
   },
   {
    "t": "poteau",
    "x": 87.3,
    "y": -36.7,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "typ": "Incongelable"
    }
   }
  ]
 },
 {
  "id": "j-purge",
  "nom": "Purge",
  "items": [
   {
    "t": "tuyau",
    "x": 0,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    }
   },
   {
    "t": "bred",
    "x": 68,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "dn2": 40
    },
    "lo": [
     -75.2,
     8
    ]
   },
   {
    "t": "rob14",
    "x": 92,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 40,
     "ext": "FF"
    }
   },
   {
    "t": "purge",
    "x": 108,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 40,
     "L": 0,
     "dl": 0,
     "exu": "Fossé / exutoire"
    }
   }
  ]
 },
 {
  "id": "j-reducteur-de-pression",
  "nom": "Réducteur de pression",
  "items": [
   {
    "t": "tuyau",
    "x": -20,
    "y": 0,
    "r": 180,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     -71,
     14
    ]
   },
   {
    "t": "tuyau",
    "x": 20,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     76,
     45
    ]
   },
   {
    "t": "rp",
    "x": 0,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "pav": 3,
     "reg": true
    }
   }
  ]
 },
 {
  "id": "j-ventouse",
  "nom": "Ventouse",
  "items": [
   {
    "t": "te",
    "x": 0,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 100,
     "ext": "BBB",
     "but": true,
     "verr": false,
     "tb": 10
    }
   },
   {
    "t": "ventouse",
    "x": 0,
    "y": -30,
    "r": 0,
    "f": 1,
    "p": {
     "dn": 100,
     "typ": "Trifonctionnelle",
     "iso": true,
     "reg": true
    }
   },
   {
    "t": "tuyau",
    "x": -20,
    "y": 0,
    "r": 180,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     -71,
     14
    ]
   },
   {
    "t": "tuyau",
    "x": 20,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     76,
     45
    ]
   }
  ]
 },
 {
  "id": "j-vidange",
  "nom": "Vidange",
  "items": [
   {
    "t": "tuyau",
    "x": -20,
    "y": 0,
    "r": 180,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     -71,
     14
    ]
   },
   {
    "t": "tuyau",
    "x": 20,
    "y": 0,
    "r": 0,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "ext": "BB",
     "L": 0,
     "dl": 0,
     "verr": false,
     "grill": true,
     "fou": false
    },
    "lo": [
     76,
     45
    ]
   },
   {
    "t": "te",
    "x": 0,
    "y": 0,
    "r": 180,
    "f": 1,
    "p": {
     "mat": "fd",
     "dn": 100,
     "dn2": 100,
     "ext": "BBB",
     "but": true,
     "verr": false,
     "tb": 10
    }
   },
   {
    "t": "vidange",
    "x": 0.0,
    "y": 30,
    "r": 90,
    "f": 1,
    "p": {
     "dn": 100,
     "exu": "Fossé / exutoire",
     "bac": true,
     "reg": false
    },
    "lo": [
     -3.2,
     27.6
    ]
   }
  ]
 }
]''')

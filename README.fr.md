# Routage sélectif multi-modèles pour Claude Code

[English](README.md)

Une configuration Claude Code à portée projet qui confie le travail à des rôles
spécialisés uniquement quand la délégation préserve la qualité tout en réduisant
le coût total ou le délai. L'agent principal reste responsable des décisions, de
l'intégration et de la communication avec l'utilisateur.

## Politique de routage

Priorités, dans cet ordre :

1. Préserver la qualité et la pertinence du résultat.
2. Réduire le coût total, coordination et reprises comprises.
3. Réduire le délai.

Un coût total plus bas obtenu avec davantage de tokens sur un palier moins cher
est un bon échange. Une qualité dégradée ou un délai multiplié ne l'est pas.

Les tâches petites et bornées restent à l'agent principal. La délégation sert
quand un rôle clairement cadré peut abattre un travail substantiel plus
efficacement, ou apporter une analyse indépendante utile.

| Rôle | Modèle | Effort | $/1M entrée | $/1M sortie | Responsabilité |
| --- | --- | --- | --- | --- | --- |
| Principal | `opus` | `xhigh` | 4 | 20 | Triage, décisions, intégration, petites tâches locales |
| `scout` | `sonnet` | `medium` | 2 | 10 | Exploration en lecture seule du code et des logs |
| `researcher` | `sonnet` | `medium` | 2 | 10 | Recherche documentaire multi-sources |
| `runner` | `haiku` | *(non supporté)* | 1 | 5 | Validations longues et lots mécaniques |
| `builder` | `sonnet` | `xhigh` | 2 | 10 | Implémentation bornée avec validation ciblée |
| `architect` | `opus`, ou `fable` sur accès confirmé | `xhigh` | 4 → 10 | 20 → 50 | Décisions d'architecture, rares et bornées |

`opus` désigne Opus 5.5 sur l'API Anthropic et les abonnements, ce qui exige
Claude Code 2.1.280 ou plus récent ; un CLI plus ancien ou un autre fournisseur
sert un autre modèle.

Trois choix méritent une justification :

- **`runner` sur le palier le moins cher.** Le rôle exécute et rapporte, il ne
  conçoit pas. Ses bornes — trois cycles correction/test, arrêt au premier signal
  répété, deux tentatives sur un problème d'environnement — sont précisément ce
  qui rend ce palier sûr ici. Haiku ne supporte pas `effort` : le champ est
  volontairement absent de son rôle.
- **`scout` et `researcher` n'y descendent pas.** Tous deux produisent des faits
  que l'agent principal croira sans les revérifier ; un palier trop bas y produit
  des affirmations assurées et fausses, dont la reprise coûte plus que
  l'économie. Leur effort reste `medium` : leur travail est borné par les entrées
  et sorties plus que par le raisonnement, et un effort plus bas consolide les
  appels d'outils — moins cher et plus rapide, à qualité tenue.
- **`builder` monte en effort plutôt qu'en palier.** L'effort est le premier
  levier de qualité à l'intérieur d'un modèle ; `sonnet`/`xhigh` coûte deux fois
  moins que le palier au-dessus en entrée et en sortie, et autant en lecture de
  cache.

Deux escalades, décidées explicitement et passées à l'invocation, sans modifier
aucun fichier de rôle : `builder` vers `opus` pour une tâche difficile,
`architect` vers `fable` sur accès confirmé, en second appel lorsque l'avis
Opus 5.5 laisse une contradiction décisive. Un problème d'environnement ne fait
jamais monter d'un palier.

## Accès à Fable 5.1

Fable n'est pas accessible à tout le monde, et il coûte deux fois et demie Opus 5.5. Selon
le plan et le siège, son usage peut être débité en *usage credits* ; une session
interactive demande alors un consentement avant de facturer, mais un lancement
non interactif (`-p`) facture sans demander.

La configuration ne met donc **jamais** `fable` dans un fichier de rôle.
`architect` embarque `opus` en `xhigh` : il fonctionne sur tous les plans et ne
bloque jamais une session. L'escalade vers Fable est dynamique et conditionnée.

L'accès est **présumé indisponible**, et sa détermination est déterministe :

```bash
claude auth status --json
```

`apiProvider`, `authMethod` et `subscriptionType` suffisent à trancher dans la
quasi-totalité des cas, complétés par `claude --version` (Fable 5.1 exige
2.1.257 ou plus récent) et par `availableModels` s'il est défini. La table de
décision complète est dans le skill. Une valeur de plan inconnue ne s'interprète
pas : elle se demande.

Disponible ne vaut pas autorisé pour autant. Sur abonnement, Fable peut être
débité en usage credits — de l'argent en plus de l'abonnement. L'agent principal
demande donc une fois avant la première consultation, en nommant le plan
constaté et le surcoût, et consigne la réponse dans
`.claude/settings.local.json` — gitignoré, donc propre à chaque poste.

Sans accès ou sur refus, `architect` répond en Opus 5.5 `xhigh` et **annonce
explicitement qu'il ne s'agit pas d'un avis Fable**. Après coup, le modèle
effectif est vérifié dans le résultat d'appel (`resolvedModel`) : sans
correspondance, le résultat est écarté comme non conforme.

## Structure du projet

```text
.
├── CLAUDE.md
├── extract_claude_jsonl.ps1
├── test_extract_claude_jsonl.py
└── .claude/
    ├── settings.json
    ├── skills/quota-orchestrator/SKILL.md
    └── agents/
        ├── architect.md
        ├── builder.md
        ├── researcher.md
        ├── runner.md
        └── scout.md
```

- `CLAUDE.md` porte les règles de routage et de sécurité du dépôt.
- `quota-orchestrator` décide si une délégation vaut son coût complet.
- `.claude/settings.json` fixe les efforts par défaut et par modèle.
- `.claude/agents/*.md` définit modèle, effort, outils, bornes et contrat de
  rapport de chaque rôle.
- `extract_claude_jsonl.ps1` mesure ce que tout cela consomme réellement.

## Utilisation

### Héritage et précédence

Claude Code construit sa chaîne d'instructions, de la plus faible à la plus forte
précédence : les instructions gérées par l'organisation, puis `~/.claude/CLAUDE.md`,
puis le `CLAUDE.md` à la racine du dépôt, puis `CLAUDE.local.md`. Le `CLAUDE.md`
d'un sous-dossier est chargé à la demande, quand Claude y travaille. La syntaxe
`@chemin` importe un autre fichier ; les chemins relatifs se résolvent depuis le
fichier qui importe, pas depuis le répertoire courant.

Si votre projet a déjà un `CLAUDE.md`, **ne le remplacez pas** : gardez son
contenu et ajoutez-y les règles de routage. Pour restreindre des instructions à
un sous-dossier, placez-y un autre `CLAUDE.md`.

Pour les réglages, `~/.claude/settings.json` fournit vos valeurs personnelles.
`.claude/settings.json` du projet passe au-dessus, `.claude/settings.local.json`
au-dessus encore, et les réglages gérés par l'organisation priment sur tout.

### Installation

1. Python 3.11 ou plus récent est requis. Depuis ce dépôt, lancez :

   ```text
   python install.py chemin/vers/votre/projet
   ```

   `--dry-run` affiche le plan sans rien écrire. L'installateur ajoute les
   règles de routage à un `CLAUDE.md` existant entre des marqueurs
   `claudeskills:routing`, n'ajoute que les clés manquantes de
   `.claude/settings.json`, sauvegarde les fichiers modifiés sous
   `.claudeskills-backup/`, et avertit au lieu d'écraser un fichier de rôle ou
   de skill divergent.
2. Relisez les avertissements, puis les modèles, les efforts et les règles de
   permission pour votre environnement, puis `/agents` pour confirmer que les
   cinq rôles sont vus avec le bon modèle et le bon effort.
3. Démarrez une nouvelle session depuis le dépôt pour que la chaîne
   d'instructions soit reconstruite.
4. Demandez à Claude de résumer ses instructions actives si vous voulez vérifier
   la détection.

Claude Code découvre les instructions de dépôt dans `CLAUDE.md`, les skills dans
`.claude/skills`, les rôles dans `.claude/agents` et les réglages dans
`.claude/settings.json`. Voir la documentation officielle :
[CLAUDE.md](https://code.claude.com/docs/en/memory),
[skills](https://code.claude.com/docs/en/skills),
[sous-agents](https://code.claude.com/docs/en/sub-agents),
[modèles](https://code.claude.com/docs/en/model-config),
[réglages](https://code.claude.com/docs/en/settings).

## Mesure

Sans mesure, un gain est attendu, pas démontré. `extract_claude_jsonl.ps1` lit
les transcripts JSONL de session et agrège tokens, durées et **coût en dollars**
par modèle, par effort et par rôle.

```powershell
.\extract_claude_jsonl.ps1
```

Le rapport porte un champ `Complete`. Il ne vaut `true` qu'en l'absence de tout
diagnostic. Un rapport incomplet a exactement le statut *non observable* : ses
tokens, coûts et durées ne doivent jamais servir dans un ratio, une médiane, une
comparaison ou une recommandation économique. Comparer au moins deux rapports
complets, sinon conclure qu'aucune comparaison n'est possible.

Le script lit deux niveaux : le transcript de la session pour l'agent principal,
et `<session>/subagents/agent-*.jsonl` pour chaque rôle délégué. Cette seconde
source est indispensable — le résultat de l'appel qui a lancé un sous-agent ne
porte que son **tour final**, pas son cumul. S'y fier sous-compte massivement.
Un sous-agent de fond est mesuré comme les autres ; ce qui rend un run non
observable, c'est un transcript manquant, un modèle absent de la table de prix,
ou une écriture de cache dont la durée de vie est inconnue.

Autre piège, également corrigé : un même message apparaît une fois par bloc de
contenu et son `usage` est **cumulatif**. Le script retient le maximum par
identifiant de message ; retenir le premier perdrait la majeure partie des
tokens de sortie.

Une écriture de cache se tarife selon sa durée de vie : 1,25× l'entrée pour un
cache de 5 minutes, **2× pour un cache d'une heure**. Claude Code utilise les
deux dans une même session — typiquement 1 heure pour l'agent principal et
5 minutes pour un sous-agent. Confondre les deux sous-estime la facture d'un
tiers ; le script lit donc la ventilation par durée de vie, et refuse de chiffrer
une écriture dont le TTL est inconnu.

Les tarifs vivent dans une seule table en tête du script ; c'est le seul endroit
à mettre à jour quand ils changent. `python test_extract_claude_jsonl.py` vérifie
le contrat du script sur des transcripts synthétiques, sans aucun appel de modèle.

## Limites de sécurité

- Ne jamais lancer sous `--dangerously-skip-permissions` ni en mode
  `bypassPermissions`.
- Ne pas élargir les permissions de la session pour consulter `architect` ; si
  ses restrictions ne tiennent plus, isoler la décision dans une autre session.
- `architect` n'explore pas, n'exécute aucune commande, n'écrit aucun fichier et
  ne délègue pas.
- Les rôles restent dans leur périmètre et ne font pas de routage eux-mêmes :
  `Agent` est absent de la liste d'outils de chacun, ce qui l'empêche
  effectivement de déléguer.

## Personnalisation

Modifiez `.claude/settings.json` pour les efforts par défaut, et le fichier
correspondant sous `.claude/agents/` pour changer un rôle. Gardez modèles,
efforts et frontières de rôle synchronisés entre `CLAUDE.md`,
`quota-orchestrator/SKILL.md` et ce README.

Les paliers proposés ici sont défendables, pas mesurés sur votre travail. Le
script de mesure existe précisément pour que vous les régliez sur vos propres
tâches — et la doctrine interdit d'annoncer un gain démontré tant que deux runs
complets ne le montrent pas.

La disponibilité des modèles dépend de votre compte et de votre environnement.

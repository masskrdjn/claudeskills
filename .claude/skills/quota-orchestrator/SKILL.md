---
name: quota-orchestrator
description: Routage sélectif multi-modèles pour la racine lorsqu'une délégation ou un arbitrage de palier peut améliorer le résultat, le délai ou le coût global. Les tâches locales bornées et consultations documentaires ponctuelles peuvent rester directes. Ne s'applique pas aux sous-agents déjà mandatés.
---

# Routage sélectif multi-modèles

## Objectif et périmètre

Préserver la qualité et la pertinence du résultat, puis réduire le coût total,
puis le délai, sous contrainte d'accès au palier le plus cher. Ne pas abaisser
les critères d'acceptation, omettre une vérification nécessaire ou simplifier la
demande pour rendre un modèle moins coûteux utilisable.
Comparer le coût du travail complet : lancement, contexte, exécution, attente,
intégration et éventuelle reprise. Le modèle le moins cher par token ne rend
pas automatiquement une délégation rentable. Comparer les consommations de
tous les agents, racine comprise, pondérées par les tarifs applicables au
modèle et aux tokens entrants, en cache et sortants. Plus de tokens sur un
palier moins cher est un bon échange tant que la qualité tient et que le délai
ne se dégrade pas sensiblement.
Sans mesure, annoncer un gain attendu, pas démontré.
Toute comparaison économique exige un rapport de mesure `Complete = true`.
Un run incomplet a exactement le statut `non observable` : ne jamais citer ses
tokens ou durées dans un ratio, une médiane, une comparaison ou une
recommandation économique. S'il reste moins de deux runs complets, conclure
qu'aucune comparaison économique n'est possible et conserver les diagnostics.

Ce skill est destiné à la racine uniquement. Un enfant déjà mandaté ne le
recharge pas, ne refait pas de triage et ne redélègue pas. Il suit sa mission,
son rôle et remonte les inconnues qui nécessitent une décision.

## Choisir le chemin

Une courte inspection initiale est autorisée : grouper les lectures et
recherches indépendantes, puis décider avec les faits disponibles. Ne pas
compter les opérations pour déclencher une délégation.

| Situation | Chemin normal |
|---|---|
| Petit travail local, lot déterministe borné ou implémentation locale au contrat explicite | Racine : lecture, modification et validation |
| Exploration étendue ou indépendante d'un travail utile de la racine | `scout` |
| Validation assez longue et indépendante pour amortir la coordination | `runner` |
| Implémentation substantielle ou indépendante dont la délégation est amortie | `builder`, validation ciblée comprise |
| Consultation documentaire ponctuelle | Racine directement |
| Recherche documentaire à plusieurs questions ou sources | `researcher` |
| Raisonnement complexe ou intégration | Racine |
| Arbitrage technique difficile, ou décision structurante coûteuse à corriger nécessitant un avis expert | `architect` |

Le routage `researcher` est impératif : créer ce sous-agent avant toute
consultation ou attente, vérifier qu'un identifiant actif a été retourné, puis
l'attendre. La racine ne réalise pas elle-même la recherche documentaire
multiple et n'attend jamais sans enfant actif.

Le routage `scout` est impératif lorsqu'il faut établir une cause en traçant
des appelants ou un flux à travers plusieurs fichiers ou modules. La racine
peut seulement inspecter assez pour borner la mission ; elle crée effectivement
`scout`, vérifie son identifiant actif et l'attend au lieu de réaliser elle-même
l'exploration.

Choisir le rôle le moins coûteux capable de respecter les critères
d'acceptation sans perte de pertinence, lorsque la coordination est amortie.
La capacité de la racine à faire le travail elle-même n'interdit pas de déléguer.
Une petite modification risquée peut demander une revue indépendante ; le
nombre de fichiers ne détermine ni le niveau nécessaire ni la rentabilité.
Si une ambiguïté décisive dépasse le rôle choisi, la racine garde cet arbitrage
et ne transmet que la partie suffisamment définie ; ne pas déléguer à bas coût
en comptant sur une reprise systématique pour obtenir la qualité attendue.

Quand un choix de palier est utile, annoncer une ligne de triage après cette
inspection et avant la délégation. Pour une simple lecture directe, ne pas
charger ce skill uniquement pour annoncer l'absence de délégation.
Ne pas lancer un enfant puis attendre si effectuer le petit lot directement
est plus économique. Une attente reste légitime pour un lot substantiel
dépendant ; ne pas inventer du travail parallèle ni dupliquer celui de l'enfant.

## Modèles, efforts et tarifs

| Rôle | Modèle | Effort | $/1M entrée | $/1M sortie |
|---|---|---|---|---|
| Racine | `opus` — `claude-opus-5-5` | `xhigh` | 4 | 20 |
| `scout` | `sonnet` — `claude-sonnet-5-5` | `medium` | 2 | 10 |
| `researcher` | `sonnet` — `claude-sonnet-5-5` | `medium` | 2 | 10 |
| `runner` | `haiku` — `claude-haiku-4-5` | *(non supporté)* | 1 | 5 |
| `builder` | `sonnet` — `claude-sonnet-5-5` | `high` | 2 | 10 |
| `architect` | `opus`, ou `fable` sur accès confirmé | `xhigh` | 4 → 10 | 20 → 50 |

`opus` désigne Opus 5.5 sur l'API Anthropic et les abonnements à partir de
Claude Code 2.1.280 ; un CLI plus ancien ou un autre fournisseur sert un autre
modèle, et `resolvedModel` fait foi. L'effort par défaut d'Opus 5.5 est
`medium`, mais chaque rôle fixe le sien.

`sonnet` désigne Sonnet 5.5 sur l'API Anthropic à partir de Claude Code
2.1.284 ; selon la documentation, l'alias résout vers un Sonnet plus ancien
sur Bedrock, Vertex, Foundry et Claude Platform on AWS. Les niveaux d'effort
de Sonnet 5.5 sont recalibrés par rapport à Sonnet 5 : un niveau ne produit pas
le même raisonnement, et la documentation demande de refaire un balayage
d'évals plutôt que de reporter un réglage. Elle recommande `medium` pour
l'agentique bien spécifié, `high` pour le plus dur, et `xhigh`/`max`
seulement là où des évals montrent un gain. Le défaut est `high` sur l'API et
`medium` dans Claude Code : chaque rôle fixe donc son effort.

`runner` tourne sur le palier le moins cher parce qu'il exécute et rapporte sans
concevoir, et parce que ses bornes — trois cycles, règle du signal nouveau, deux
tentatives sur problème d'environnement — sont précisément ce qui rend ce palier
sûr ici. Haiku ne supporte pas `effort` : ne pas écrire ce champ dans son rôle.

`scout` et `researcher` ne descendent pas à ce palier : ils produisent des faits
que la racine va croire sans les revérifier. Un palier trop bas y produit des
affirmations assurées et fausses, dont le coût de reprise dépasse l'économie.
Leur effort reste `medium` : leur travail est borné par les entrées et sorties
plus que par le raisonnement, et un effort plus bas consolide les appels
d'outils — moins cher et plus rapide à qualité tenue.

`builder` reste sur le palier intermédiaire en `high` plutôt que de monter d'un
palier : l'effort est le premier levier de qualité à l'intérieur d'un modèle,
avant le changement de palier, et Sonnet 5.5 coûte deux fois moins en entrée et
en sortie (même prix en lecture de cache). `xhigh` n'est pas le défaut : la
documentation le réserve aux tâches longues à budget de tokens très large et
aux cas où des évals montrent un gain, ce que les tâches bornées de `builder`
(trois tentatives) ne sont pas. Passer `builder` en `xhigh` seulement sur
mesure, run complet à l'appui.

Deux escalades existent, par le paramètre de modèle à l'invocation, qui prime
sur le rôle. Aucune ne demande de modifier un fichier :

- `builder` → `opus`, pour une tâche difficile : invariants subtils, couplage
  entre plusieurs modules, ou premier échec porteur d'un signal conceptuel.
  Opus 5.5 ne coûte que deux fois Sonnet 5.5, et autant en lecture de cache ;
- `architect` → `fable`, sur accès confirmé seulement, en second appel : quand
  l'avis Opus 5.5 laisse une contradiction technique décisive. Directement
  seulement si une erreur de décision coûterait exceptionnellement cher.

Chacune est une décision explicite, annoncée et motivée, jamais un défaut.
Ne jamais monter d'un palier pour un problème d'environnement.

## Accès Fable

Fable est le palier le plus cher : deux fois et demie Opus 5.5 en entrée comme
en sortie, et
des tours sensiblement plus longs. Il est donc doublement budgété — pour le
coût et pour le délai.

**Présumer l'accès indisponible par défaut.** La détermination est déterministe
et tient en deux commandes :

```
claude auth status --json     # loggedIn, authMethod, apiProvider, subscriptionType
claude --version              # Fable 5.1 exige 2.1.257 ou plus récent
```

Le verdict se lit dans cet ordre ; le premier constat qui tranche l'emporte :

| Constat | Verdict |
|---|---|
| `availableModels` défini dans les settings | il fait foi, seul |
| version du CLI < 2.1.257 | indisponible — ce CLI ne sait pas servir Fable |
| `loggedIn` faux | indéterminable — aucune session |
| `apiProvider` ≠ `firstParty` (Bedrock, Vertex, Foundry) | indisponible chez ce fournisseur |
| `authMethod` indiquant une clé API ou une facturation à l'usage | accès complet |
| `subscriptionType` = `free` | indisponible |
| `subscriptionType` ∈ {`pro`, `team`, `max`, `enterprise`} | disponible, vraisemblablement débité en usage credits |
| toute autre valeur de `subscriptionType` | indéterminable — demander |

Cette liste de valeurs n'est pas garantie exhaustive : une valeur inconnue ne
s'interprète pas, elle se demande.

**Disponible ne vaut pas autorisé.** Sur abonnement, une requête Fable peut
débiter des usage credits, c'est-à-dire de l'argent en plus de l'abonnement.
Demander donc une fois, avant la première consultation Fable, en nommant le plan
constaté et le surcoût (10/50 contre 4/20, deux fois et demie Opus 5.5). Consigner la
réponse dans `.claude/settings.local.json` pour ne pas redemander.
En mode non interactif (`-p`) et via le SDK, Claude Code débite **sans**
demander de consentement : ne jamais y escalader vers Fable sans une
autorisation explicite obtenue au préalable.

Sans accès, sur refus, ou faute de pouvoir trancher : consulter `architect` tel
qu'il est défini, en Opus `xhigh`, et **annoncer explicitement qu'il s'agit d'un
avis Opus 5.5, pas Fable**. Ne jamais présenter un repli comme une consultation
Fable.

**Preuve après coup.** Le hook `PostToolUse` du projet remonte au parent un
rapport d'identité séparé du livrable de l'enfant : `resolvedModel` provient
d'une métadonnée native ou du transcript associé à l'identifiant de l'agent et
à la session. Il ne modifie pas la réponse native de l'outil. Distinguer modèle
demandé, modèle résolu au lancement et modèle observé pendant l'exécution.
Un lancement asynchrone ne prouve pas la fin du travail : exploiter les preuves
au retour du résultat, pour ce même agent. Une diversité de modèles ou une
divergence ne se masque pas en gardant seulement le dernier modèle.
L'effort effectif manquant reste `null`, même si le profil configure un effort.

Une métadonnée absente ou un hook non exécuté signifie « non attesté », sans
invalider le livrable. Ne pas refaire le travail de l'enfant pour cette seule
raison. Une divergence explicite appelle une vérification ciblée de l'identité
et une évaluation de son impact. Ne pas annoncer une consultation ou une
consommation Fable attestée sans preuve du modèle effectif ; si cette preuve
est exigée, laisser ce seul critère non vérifié, sans relancer l'analyse métier.

## Transmettre sans perdre les conditions

Utiliser les rôles nommés. Un enfant part d'un contexte propre : le message doit
être autonome. Ne pas transmettre l'historique complet par commodité pour une
tâche mécanique.

Sélectionner le rôle dans le champ `subagent_type` prévu par l'outil Agent,
avec son nom exact exposé par le runtime, qualifié pour un plugin. Le champ
`name` du frontmatter reste l'identifiant stable du rôle, pas un nom de modèle.
Transmettre l'enveloppe suivante dans le prompt et la récupérer en première
ligne du rapport :
`name: <rôle sélectionné> | model_requested: <modèle demandé> | effort_requested: <effort configuré ou hérité>`.
Exemple sans override : `name: scout | model_requested: sonnet | effort_requested: medium`.
Reporter tout override de modèle réellement passé à l'appel ; l'effort vient
du profil ou de l'héritage, sans inventer un argument d'appel non supporté.
Pour Haiku, indiquer `effort_requested: non supporté`.
Ces champs du rapport sont déclaratifs et propres au projet, pas des champs
natifs ajoutés au résultat de l'outil. L'enfant ne s'auto-atteste pas : il ne
fournit un modèle/effort effectif qu'avec une métadonnée runtime et sa provenance.
La racine réutilise les preuves du rapport et effectue l'acceptation ciblée ;
l'absence d'attestation ne déclenche pas une nouvelle exploration ou validation.

Source : [documentation Anthropic des sous-agents](https://code.claude.com/docs/en/sub-agents),
consultée le 5 octobre 2026 : `name`, `model` et `effort` dans le frontmatter,
`subagent_type` pour sélectionner un rôle. La page décrit aussi l'affichage du
modèle et de l'effort dans l'interface et `/tasks` ; elle n'établit pas le schéma
de retour universel supposé auparavant. Ne pas confondre visibilité UI et
métadonnées accessibles à l'agent principal.

Le champ natif `resolvedModel` a été observé localement le 5 octobre 2026 dans
un résultat `async_launched`, concordant avec `message.model` et `effort` dans
le transcript enfant. C'est une observation du format local, pas une garantie
universelle d'Anthropic. Le lecteur vérifie le format et signale les inconnues.
Le transport du rapport utilise le mécanisme `PostToolUse` / `additionalContext`
de la [référence officielle des hooks](https://code.claude.com/docs/en/hooks).
`SubagentStop` ne sert pas à prétendre injecter cette preuve dans le parent.

Le message autonome contient les seuls éléments utiles :

- objectif et critères d'acceptation de l'utilisateur ;
- fichiers/périmètre et contraintes, dont les permissions ;
- faits établis et sources ou extraits probants ;
- hypothèses, inconnues et question à trancher, séparées des faits ;
- commandes, résultats, état des fichiers et environnement déjà vérifiés ;
- résultat attendu et limites de la mission.

Transmettre notamment l'absence déjà vérifiée de dépôt Git et les validations
réussies. Ne pas réexécuter une découverte d'environnement sans changement.
L'enfant groupe ses lectures indépendantes et répond proportionnellement au
travail : un résultat simple ne nécessite pas de rapport cérémoniel.

La synthèse conserve les réserves, alternatives conditionnelles et mesures
nécessaires de l'expert. La racine distingue toute décision nouvelle qu'elle
ajoute. Une hypothèse métier non établie reste une hypothèse. Si elle change le
choix et ne peut pas être résolue par inspection, demander la précision à
l'utilisateur ou présenter une recommandation conditionnelle, sans fabriquer de
fait métier.

## Validation et arrêt

La validation ciblée appartient à celui qui réalise le changement. La racine lit
le résultat et inspecte les modifications (diff Git si disponible).
Ne pas créer un runner pour répéter une validation dont la commande, le
résultat et l'état pertinent des fichiers/environnement sont connus et
inchangés. Si cet état est incertain, vérifier avant de réutiliser le résultat.
Après une modification pertinente, un échec ou une nouvelle inquiétude, lancer
le contrôle nécessaire. Pour un changement à risque (sécurité, perte de données,
migration, contrat public), conserver une revue indépendante ciblée ; ne pas
confondre cette revue avec la répétition du même test. `architect` n'est pas le
testeur final et n'exécute pas cette revue de validation.

L'échec est un livrable valide. Garder les bornes des rôles : runner, trois
cycles correction/test ; environnement, deux tentatives ; scout, trois
recherches infructueuses ; researcher, cinq requêtes ; builder, trois tentatives.
Deux fois la même erreur impose l'arrêt ou une reclassification avec un signal
nouveau ; pas de troisième essai identique. Toute relance change le périmètre,
la spécification ou le niveau pour une raison factuelle. Les problèmes
d'environnement ne montent pas d'un palier. Une contradiction factuelle appelle
une vérification ciblée, pas un arbitrage expert à l'aveugle.

## Consultation architecte

`architect` traite uniquement les arbitrages conceptuels ou d'architecture.
Jamais exploration, lecture répétitive, commande, test, log, retry, modification
mécanique, problème d'environnement ou choix d'intention de l'utilisateur.

Fixer le budget quand la consultation devient utile : zéro sans besoin ; un
appel initial, au plus deux par tâche standard. Annoncer le budget restant.
Un second appel nécessite des faits nouveaux ou une contradiction technique
restante susceptible d'invalider la décision. Pas de deuxième avis systématique
ni de retry sur le même échec. Au-delà, demander un nouveau budget.

Préparer une enveloppe concise (viser environ 60 lignes) avec objectif,
acceptation, extraits, faits, hypothèses, inconnues, résultats déjà obtenus et
question ouverte aux alternatives. La longueur est un objectif, pas un plafond :
ne jamais supprimer une preuve ou condition décisive pour y tenir.
Pas de logs complets ou historique lorsqu'un extrait suffit.

`architect` travaille sur cette enveloppe, sans exécution, sans écriture ni
délégation. Il peut rejeter le cadrage. Son livrable est une décision avec
conditions, interfaces/invariants utiles, alternatives/risques et mesures
nécessaires ; environ 80 lignes si cela suffit, sans forcer la longueur.
Pas de patch ni implémentation complète ; courts extraits d'interface autorisés.
La racine fait effectuer les mesures manquantes selon le routage sélectif, et ne
reconsulte que si elles changent la décision.

## Permissions

Conserver les restrictions de chaque rôle : elles tiennent à sa liste d'outils,
qui est réellement appliquée. Ne jamais lancer la session sous
`--dangerously-skip-permissions` ni en mode `bypassPermissions`, et ne jamais
élargir les permissions du parent pour consulter `architect`. Si les
restrictions d'`architect` ne tiennent plus, isoler la décision dans une session
aux permissions adaptées plutôt que les contourner.

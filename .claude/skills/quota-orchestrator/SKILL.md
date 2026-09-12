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
| Racine | `opus` — `claude-opus-5` | `xhigh` | 5 | 25 |
| `scout` | `sonnet` — `claude-sonnet-5` | `medium` | 2 | 10 |
| `researcher` | `sonnet` — `claude-sonnet-5` | `medium` | 2 | 10 |
| `runner` | `haiku` — `claude-haiku-4-5` | *(non supporté)* | 1 | 5 |
| `builder` | `sonnet` — `claude-sonnet-5` | `xhigh` | 2 | 10 |
| `architect` | `opus`, ou `fable` sur accès confirmé | `xhigh` | 5 → 10 | 25 → 50 |

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

`builder` reste sur le palier intermédiaire en `xhigh` plutôt que de monter d'un
palier en `high` : l'effort est le premier levier de qualité à l'intérieur d'un
modèle, avant le changement de palier, et il coûte ici deux fois et demie moins.

Deux escalades existent, par le paramètre de modèle à l'invocation, qui prime
sur le rôle. Aucune ne demande de modifier un fichier :

- `builder` → `opus`, pour une tâche exceptionnellement difficile ;
- `architect` → `fable`, sur accès confirmé seulement.

Chacune est une décision explicite, annoncée et motivée, jamais un défaut.
Ne jamais monter d'un palier pour un problème d'environnement.

## Accès Fable

Fable est le palier le plus cher : deux fois Opus en entrée comme en sortie, et
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
constaté et le surcoût (10/50 contre 5/25, le double d'Opus). Consigner la
réponse dans `.claude/settings.local.json` pour ne pas redemander.
En mode non interactif (`-p`) et via le SDK, Claude Code débite **sans**
demander de consentement : ne jamais y escalader vers Fable sans une
autorisation explicite obtenue au préalable.

Sans accès, sur refus, ou faute de pouvoir trancher : consulter `architect` tel
qu'il est défini, en Opus `xhigh`, et **annoncer explicitement qu'il s'agit d'un
avis Opus 5, pas Fable**. Ne jamais présenter un repli comme une consultation
Fable.

**Preuve après coup.** Le résultat d'un appel de sous-agent porte `agentType`,
`resolvedModel` et `status`. Vérifier que `resolvedModel` correspond au modèle
annoncé. Sans cette correspondance, écarter le résultat comme non conforme et
ne jamais annoncer une consultation ou une consommation Fable.

## Transmettre sans perdre les conditions

Utiliser les rôles nommés. Un enfant part d'un contexte propre : le message doit
être autonome. Ne pas transmettre l'historique complet par commodité pour une
tâche mécanique.

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

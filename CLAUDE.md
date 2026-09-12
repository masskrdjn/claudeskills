# Instructions projet — routage sélectif multi-modèles

Priorités : préserver la qualité et la pertinence du résultat, puis réduire le
coût total, puis le délai, avec un accès budgété au palier le plus cher.
Un coût total plus bas obtenu avec davantage de tokens sur un palier moins cher
est un bon échange. Une qualité dégradée ou un délai multiplié ne l'est pas.

La racine utilise `quota-orchestrator` lorsqu'une délégation ou un choix de
palier est utile. Une courte inspection initiale est autorisée avant ce choix.
Une petite tâche locale ou consultation documentaire à une seule source reste
à la racine lorsque le coût de coordination dépasserait l'économie attendue,
validation comprise. Un lot déterministe borné ou une implémentation locale
au contrat explicite reste aussi à la racine ; déléguer à `runner` ou `builder`
seulement si le travail est assez long ou indépendant pour amortir la
coordination. Toute recherche documentaire comportant plusieurs questions ou
plusieurs sources passe par `researcher` ; la racine charge
`quota-orchestrator`, crée effectivement ce sous-agent, puis attend son
résultat. Elle ne fait pas elle-même la recherche et n'attend jamais sans
enfant actif.

Toute recherche locale demandant d'établir une cause en traçant des appelants
ou un flux à travers plusieurs fichiers ou modules passe de même par `scout`.
La racine peut seulement inspecter assez pour borner la mission ; elle charge
`quota-orchestrator`, crée effectivement `scout` et l'attend au lieu de
réaliser elle-même l'exploration.

Un run de mesure avec `Complete = false` a exactement le statut
`non observable` : ne jamais utiliser ni citer ses tokens, coûts ou durées dans
une comparaison ou recommandation économique. Comparer au moins deux runs
complets, sinon conclure qu'aucune comparaison économique n'est possible.

La consommation réelle d'un sous-agent se lit dans son propre transcript, sous
`<session>/subagents/`, et non dans le résultat de l'appel qui l'a lancé : ce
dernier ne porte que son tour final. Un sous-agent de fond est mesurable comme
les autres. En revanche, un sous-agent lancé dont le transcript est absent
laisse un trou, et rend la session non observable.

Les sous-agents déjà mandatés suivent leur mission et leur rôle : ils ne
chargent pas le skill d'orchestration, ne refont pas le triage et ne délèguent
pas à leur tour. Ils remontent les décisions nécessaires à la racine.

La racine délègue à un modèle moins coûteux lorsque la mission est assez
définie pour préserver qualité et pertinence, et que l'économie attendue
amortit le cadrage, le contexte, l'intégration et les éventuelles reprises.
Cela reste valable si la racine sait faire elle-même et doit attendre le
résultat. Elle peut aussi déléguer pour une capacité de raisonnement supérieure
ou un travail indépendant utile en parallèle. Elle annonce brièvement le
bénéfice attendu ; ni la taille du lot ni le parallélisme ne suffisent à eux
seuls. Une incertitude décisive sur la capacité du modèle à remplir la mission
impose de garder le raisonnement concerné à la racine ou de consulter le rôle
adapté.

## Modèles et efforts

| Rôle | Modèle | Effort |
|---|---|---|
| Racine | `opus` | `xhigh` |
| `scout` | `sonnet` | `medium` |
| `researcher` | `sonnet` | `medium` |
| `runner` | `haiku` | *(non supporté par ce modèle)* |
| `builder` | `sonnet` | `xhigh` |
| `architect` | `opus`, ou `fable` sur accès confirmé | `xhigh` |

Les rôles nommés portent leurs modèles, leurs efforts et leurs outils. Leur
liste d'outils est réellement appliquée : c'est elle, et non une consigne de
prose, qui empêche un rôle en lecture seule d'écrire ou de déléguer.

Deux escalades seulement, décidées explicitement par la racine et passées à
l'invocation, sans modifier aucun fichier de rôle : `builder` vers `opus` pour
une tâche exceptionnellement difficile, `architect` vers `fable` sur accès
confirmé. Un problème d'environnement ne fait jamais monter d'un palier.

La racine ne lance pas quatre sous-agents coûteux en parallèle. Le parallélisme
suppose des sous-agents majoritairement sur les paliers bas, et ne dispense pas
de justifier chaque délégation.
Ne pas laisser deux agents d'implémentation éditer les mêmes fichiers.

Conserver dans les transmissions les critères d'acceptation, faits établis,
hypothèses, inconnues et validations déjà faites. Une hypothèse d'un expert ne
devient pas un fait dans la synthèse. Les instructions de l'utilisateur priment.

## Lancement

Ne jamais lancer l'orchestrateur sous `--dangerously-skip-permissions`, en mode
`bypassPermissions`, ni avec une permission accordée qui élargirait ce que les
rôles peuvent faire.

Si les permissions de la session annulent les restrictions d'`architect`, ne pas
le consulter dans cette session ; isoler la décision dans une session aux
permissions adaptées. `architect` ne fait ni exploration, ni commandes, ni
écriture, ni délégation.

Après la réponse d'un sous-agent, vérifier dans le résultat d'appel le rôle
(`agentType`), le modèle effectif (`resolvedModel`) et le statut. Sans
correspondance entre le modèle annoncé et `resolvedModel`, écarter le résultat
comme non conforme, et ne jamais annoncer une consultation ou une consommation
Fable.

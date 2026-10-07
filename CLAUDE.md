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
| `runner` | `claude-haiku-5-5` | `medium` |
| `builder` | `sonnet` | `high` |
| `architect` | `opus`, ou `fable` sur accès confirmé | `xhigh` |

Les rôles nommés portent leurs modèles, leurs efforts et leurs outils. Leur
liste d'outils est réellement appliquée : c'est elle, et non une consigne de
prose, qui empêche un rôle en lecture seule d'écrire ou de déléguer.

`runner` utilise l'identifiant fixe de Haiku 5.5. Ce modèle prend en charge
`effort` : `medium` est le point de départ recommandé pour le travail agentique,
et réduit les arrêts prématurés et vérifications omises par rapport à `low`.

Deux escalades seulement, décidées explicitement par la racine et passées à
l'invocation, sans modifier aucun fichier de rôle : `builder` vers `opus` pour
une tâche difficile, `architect` vers `fable` sur accès confirmé, en second
appel lorsque l'avis Opus 5.5 laisse une contradiction décisive. Un problème
d'environnement ne fait jamais monter d'un palier.

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

## Identité et acceptation d'une délégation

Sélectionner le rôle par le champ `subagent_type` de l'outil Agent, avec le nom
exact exposé par le runtime (qualifié pour un plugin). Le champ `name` du
frontmatter définit l'identifiant du rôle : ne pas le renommer pour y encoder
un modèle. Transmettre dans le prompt une enveloppe d'identité compacte :
`name: <rôle sélectionné> | model_requested: <modèle demandé> | effort_requested: <effort configuré ou hérité>`.
Y reporter l'override de modèle passé à l'appel s'il existe, et l'effort
configuré ou hérité ; Haiku 5.5 prend en charge `effort`. Ne pas inventer un paramètre d'appel
`effort` quand le schéma de l'outil ne l'expose pas.

L'enfant renvoie cette identité en tête de son rapport. Elle est déclarative.
Le hook `PostToolUse` du projet remonte séparément un rapport d'identité à
partir de la réponse native et du transcript lié à cet agent et cette session.
Utiliser son `resolvedModel` et sa provenance, pas une auto-déclaration de
l'enfant ni une résolution supposée d'alias. Le hook complète le contexte du
parent ; il ne modifie pas les champs natifs de l'outil Agent.

Conserver trois distinctions : modèle demandé, modèle résolu au lancement,
modèle observé dans les tours effectivement exécutés. Un lancement de fond
n'atteste ni la fin du travail ni l'absence de substitution ultérieure. À la
récupération du résultat, exploiter les nouvelles preuves liées au même agent.
L'effort observé est distinct de l'effort configuré : une valeur manquante reste
`null`, sans la remplacer par le profil. Plusieurs modèles observés ou une
divergence sont signalés, jamais réduits arbitrairement au dernier modèle.

Si le hook est absent, échoue ou signale des métadonnées incomplètes, ne jamais
présumer que l'identité est vérifiée. Une valeur absente signifie « non attesté »,
pas « non conforme ». Ne pas refaire l'exploration ou les tests pour cette
seule raison : vérifier uniquement les métadonnées de l'agent concerné, puis
accepter le fond sur ses preuves et sa couverture. Une divergence explicite
appelle un contrôle ciblé de l'identité et de son impact avant de conclure.
Ne jamais annoncer une consultation ou une consommation Fable attestée sans
preuve du modèle effectif ; si cette identité est un critère d'acceptation,
la laisser non vérifiée jusqu'à une preuve ciblée, sans refaire le fond.

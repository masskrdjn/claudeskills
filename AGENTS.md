# Instructions projet — routage B

Priorités : préserver la qualité et la pertinence du résultat, puis réduire le
coût total, puis le délai, avec quota Astra limité.
La racine utilise `quota-orchestrator` lorsqu'une délégation ou un choix de
palier est utile. Une courte inspection initiale est autorisée avant ce choix.
Une petite tâche locale ou consultation ponctuelle reste à Sol lorsque le
coût de coordination dépasserait l'économie attendue, validation comprise.

Les sous-agents déjà mandatés suivent leur mission et leur rôle : ils ne
chargent pas le skill d'orchestration, ne refont pas le triage et ne délèguent
pas à leur tour. Ils remontent les décisions nécessaires à la racine.

La racine délègue à un modèle moins coûteux lorsque la mission est assez
définie pour préserver qualité et pertinence, et que l'économie attendue
amortit le cadrage, le contexte, l'intégration et les éventuelles reprises.
Cela reste valable si Sol sait faire lui-même et doit attendre le résultat.
Elle peut aussi déléguer pour une capacité de raisonnement supérieure ou un
travail indépendant utile en parallèle. Elle annonce brièvement le bénéfice
attendu ; ni la taille du lot ni le parallélisme ne suffisent à eux seuls.
Une incertitude décisive sur la capacité du modèle à remplir la mission impose
de garder le raisonnement concerné à Sol ou de consulter le rôle adapté.

Les rôles nommés portent leurs modèles et leurs efforts. Leur `sandbox_mode`
n'est pas appliqué : le bac à sable du parent prévaut, ne pas compter sur un
rôle pour restreindre un sous-agent. Ne pas laisser deux agents
d'implémentation éditer les mêmes fichiers.

Conserver dans les transmissions les critères d'acceptation, faits établis,
hypothèses, inconnues et validations déjà faites. Une hypothèse d'un expert ne
devient pas un fait dans la synthèse. Les instructions de l'utilisateur priment.

## Lancement

Ne jamais lancer l'orchestrateur sous `--yolo`,
`--dangerously-bypass-approvals-and-sandbox`, ni avec une permission runtime
accordée via `/permissions` qui élargirait le bac à sable.

Les overrides runtime du parent sont réappliqués aux sous-agents et prévalent
sur leurs valeurs par défaut. Si les permissions du parent annulent les
restrictions d'`architect`, ne pas le consulter dans cette session ; isoler la
décision dans une session aux permissions adaptées.
Astra ne fait ni exploration, ni commandes, ni écriture, ni délégation.

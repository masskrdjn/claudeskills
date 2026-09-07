# Instructions projet — routage B

Priorités : qualité du résultat, puis vitesse, avec quota Astra limité.
La racine utilise `quota-orchestrator` lorsqu'une délégation ou un choix de
palier est utile. Une courte inspection initiale est autorisée avant ce choix.
Une tâche locale bornée, même multi-étapes, ou une consultation documentaire
ponctuelle reste normalement à Sol, validation comprise.

Les sous-agents déjà mandatés suivent leur mission et leur rôle : ils ne
chargent pas le skill d'orchestration, ne refont pas le triage et ne délèguent
pas à leur tour. Ils remontent les décisions nécessaires à la racine.

La racine délègue lorsque le travail exige une capacité dont elle ne dispose
pas dans sa propre session : un palier de raisonnement supérieur sur un point
de conception dont elle a établi qu'il la dépasse, un bac à sable différent, ou
une commande longue qui peut tourner pendant qu'elle poursuit autre chose. Elle
nomme la capacité manquante quand elle délègue ; si elle ne peut pas la nommer,
elle traite elle-même. La taille d'un lot n'est pas un motif de délégation.

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

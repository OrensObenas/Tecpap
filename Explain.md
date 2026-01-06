# Guide simple du projet

Ce document raconte en mots courants ce que fait le service et comment il prend ses decisions. Pas besoin de jargon technique pour suivre.

## Idee generale
- Le service lit des listes d ordres de fabrication et organise leur passage sur plusieurs machines.
- Il essaye de limiter les retards, de regrouper les formats proches pour eviter des changements frequents et de tenir compte de la vitesse reelle des machines.
- Il reagit aux imprevus (arrets, commandes urgentes, changement de vitesse) et remet le planning en ordre quand c est utile.


## D ou viennent les infos ?
- Ordres de fabrication : un tableau avec pour chaque commande une date limite, une importance, un format et une duree prevue.
- Matrice de changement de format : un tableau qui indique combien de minutes sont perdues quand on passe d un format a un autre.
- Historique machines : pour chaque machine et format, un taux de production moyen qui sert a estimer combien de temps prend vraiment le travail.

## Comment l outil choisit l ordre de passage
- Il classe d abord les ordres selon leur date limite et leur priorite.
- Il regroupe ceux qui partagent le meme format pour diminuer le temps perdu en changement.
- Pour chaque ordre, il choisit la machine qui devrait finir le plus tot en tenant compte du setup et de la vitesse habituelle.
- Il ajuste la duree attendue si la machine est plus ou moins rapide que la valeur nominale.
- Il ne relance un nouveau calcul apres une panne que si l arret estime atteint au moins 30 minutes, afin d eviter de tout chambouler pour des micro coupures.

## Gestion des evenements en direct
- Debut et fin de poste : le flux de production s ouvre ou se met en pause.
- Changement de vitesse : on applique un multiplicateur simple (plus rapide ou plus lent) sur le travail en cours.
- Commande urgente : elle est ajoutee aussitot dans la file et force une reorganisation.
- Debut/fin de panne : le temps s arrete pendant l arret; a la reprise on mesure la duree de la panne pour savoir si un recalcul est necessaire.
  
## Mode journee simulee
- On peut lancer une simulation qui fait avancer l horloge minute par minute sur une plage donnee.
- Les evenements prevus pour la journee sont appliques a l instant ou ils arrivent, puis le planning est ajuste si besoin.
- Des rapports horaires sont stockes pour suivre comment la file avance et combien de temps a ete perdu ou produit.

## Ce que produit le service
- Un etat instantane : temps simule, ordre en cours, file d attente, et compteurs de temps perdu ou productif.
- Un planning lisible : debut et fin prevus pour chaque ordre, format, machine choisie et minutes de preparation.
- Un journal d evenements recents pour comprendre pourquoi le planning a bouge (urgence, panne, changement de vitesse).
- Un export du planning pour l afficher ou l imprimer ailleurs.

## Points forts a retenir
- Reagit aux imprevus mais ne recalculer pas tout pour rien (seuil de 30 minutes pour les pannes).
- Reduit les changements de format pour economiser du temps.
- Utilise l experience passee des machines pour donner des estimations plus realistes.
- Permet de jouer des journees completes en mode accelere pour preparer ou expliquer un scenario.
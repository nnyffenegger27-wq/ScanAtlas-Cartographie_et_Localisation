"""Recalage d'un lot USB après lecture série ; aucune dépendance à Tk."""
from copy import deepcopy
from localisation import icp_scan, recherche_icp, sous_carte, valider_solution, points_filtres


def recaler_capture(scans, reference=None, methode='Recherche large + ICP',
                    annuler=None, progression=None, historique=None, **options):
    """Recalage successif ; historique fourni = sous-carte glissante. Entrées inchangées.

    Sans référence, le premier scan ancre le repère à sa pose actuelle.
    Après échec ou annulation, on conserve les scans sans propager une pose
    incertaine. Le statut est persistant ; valide signifie accepté numériquement.
    """
    if methode not in ('ICP local', 'Recherche large + ICP'):
        raise ValueError('Méthode de recalage inconnue.')
    resultat = deepcopy(list(scans))
    precedent = deepcopy(reference)
    acceptes = deepcopy(list(historique)) if historique is not None else None
    if acceptes is not None:
        acceptes = [s for s in acceptes if not s.suivi_recalage or s.suivi_recalage.get("valide", False)]
        if precedent is not None and not acceptes: acceptes.append(precedent)
    interrompu = False
    for i, scan in enumerate(resultat):
        info = dict(valide=False, etat='non_recale', methode=methode)
        scan.suivi_recalage = info
        if annuler is not None and annuler.is_set():
            interrompu = True
            info['message'] = 'Recalage annulé ; scan conservé sans nouvelle pose.'
            continue
        if interrompu:
            info['message'] = 'Non recalé : le scan précédent n’a pas été validé.'
            continue
        if precedent is None:
            info.update(valide=True, etat='ancrage', message='Premier scan : origine du repère, sans recalage.')
            precedent = scan
            if acceptes is not None: acceptes.append(scan)
            continue
        if progression:
            progression(f'Recalage automatique {i+1}/{len(resultat)} sur {precedent.nom}…')
        try:
            calcul = recherche_icp if methode == 'Recherche large + ICP' else icp_scan
            filtres = {k: options.get(k, v) for k, v in dict(mini=.05, maxi=12., intensite=0).items()}
            cible = sous_carte(acceptes[-5:], filtres) if acceptes else precedent
            r = calcul(scan, cible, pose_initiale=precedent.pose, annuler=annuler, **options)
            if acceptes is not None and r.applicable:
                valider_solution(r, points_filtres(scan, filtres, locaux=True),
                    points_filtres(cible, filtres), options.get('distance_max', .5))
            info.update(reference=cible.nom, pose_reference=list(precedent.pose),
                        rmse=r.rmse if r.rmse < float('inf') else None,
                        recouvrement=r.recouvrement, accord_fin=r.accord_fin, duree=r.duree, message=r.message)
            # Même décision que le bouton Localiser : aucun seuil caché
            # supplémentaire propre à l'acquisition.
            accepte = r.applicable and not (annuler is not None and annuler.is_set())
            if accepte:
                scan.pose = list(r.pose)
                info.update(valide=True, etat='recalage', message='Localisation automatique réussie : pose appliquée au nouveau scan.')
                precedent = scan
                if acceptes is not None: acceptes.append(scan)
            else:
                info['message'] = 'Échec de localisation automatique : '+r.message
                interrompu = True
        except Exception as exc:
            info['message'] = 'Pose non appliquée : '+str(exc)
            interrompu = True
    return resultat


def recaler_lot(scans, annuler=None, progression=None, **options):
    """Ordre de la liste = ordre d'acquisition ; première pose fixe.

    Référence glissante : jusqu'aux cinq derniers scans acceptés. Un échec
    conserve la pose d'entrée et n'entre jamais dans la sous-carte ; le suivant
    est essayé depuis la dernière pose acceptée. Aucun changement des entrées.
    """
    resultat = deepcopy(list(scans))
    if not resultat: raise ValueError('Choisis au moins deux scans dans Carte.')
    ancres = [resultat[0]]
    ancres[0].suivi_recalage = dict(valide=True, etat='ancrage', message='Ancre fixe du lot.')
    for i in range(1, len(resultat)):
        if progression: progression(f'Lot : scan {i+1}/{len(resultat)}…')
        resultat[i] = recaler_capture([resultat[i]], ancres[-1], historique=ancres[-5:],
            annuler=annuler, progression=progression, **options)[0]
        if resultat[i].suivi_recalage['valide']: ancres.append(resultat[i])
    return resultat

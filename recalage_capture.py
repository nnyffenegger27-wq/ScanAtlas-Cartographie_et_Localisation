"""Recalage d'un lot USB après lecture série ; aucune dépendance à Tk."""
from copy import deepcopy
from localisation import icp_scan, recherche_icp


def recaler_capture(scans, reference=None, methode='Recherche large + ICP',
                    annuler=None, progression=None, **options):
    """Chaque scan accepté devient la référence du suivant. Entrées inchangées.

    Sans référence, le premier scan ancre le repère à sa pose actuelle.
    Après échec ou annulation, on conserve les scans sans propager une pose
    incertaine. Le statut est persistant ; valide signifie accepté numériquement.
    """
    if methode not in ('ICP local', 'Recherche large + ICP'):
        raise ValueError('Méthode de recalage inconnue.')
    resultat = deepcopy(list(scans))
    precedent = deepcopy(reference)
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
            continue
        if progression:
            progression(f'Recalage automatique {i+1}/{len(resultat)} sur {precedent.nom}…')
        try:
            calcul = recherche_icp if methode == 'Recherche large + ICP' else icp_scan
            r = calcul(scan, precedent, pose_initiale=precedent.pose, annuler=annuler, **options)
            info.update(reference=precedent.nom, pose_reference=list(precedent.pose),
                        rmse=r.rmse if r.rmse < float('inf') else None,
                        recouvrement=r.recouvrement, duree=r.duree, message=r.message)
            # Même décision que le bouton Localiser : aucun seuil caché
            # supplémentaire propre à l'acquisition.
            accepte = r.applicable and not (annuler is not None and annuler.is_set())
            if accepte:
                scan.pose = list(r.pose)
                info.update(valide=True, etat='recalage', message='Localisation automatique réussie : pose appliquée au nouveau scan.')
                precedent = scan
            else:
                info['message'] = 'Échec de localisation automatique : '+r.message
                interrompu = True
        except Exception as exc:
            info['message'] = 'Pose non appliquée : '+str(exc)
            interrompu = True
    return resultat

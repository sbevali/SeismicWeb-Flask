// static/js/script.js

// Définition de la fonction de réinitialisation
function resetSubmitButton() {
    const submitButton = document.querySelector('button[type="submit"]');
    // S'assurer que le bouton existe avant d'essayer de le modifier
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Lancer le Traitement et Télécharger les Fichiers";
        submitButton.classList.remove('loading');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const submitButton = document.querySelector('button[type="submit"]');

    // 1. Réinitialisation du bouton au chargement/retour de page
    // Ceci corrige le problème du bouton bloqué après le téléchargement
    window.addEventListener('load', resetSubmitButton);
    resetSubmitButton(); // Appel immédiat au cas où l'événement 'load' ne se déclenche pas comme prévu

    // 2. Fonction pour obtenir la date et l'heure au format YYYY-MM-DDTHH:MM:SS
    function formatDateTime(date) {
        const yyyy = date.getFullYear();
        const mm = String(date.getMonth() + 1).padStart(2, '0'); // Mois 0-11
        const dd = String(date.getDate()).padStart(2, '0');
        const hh = String(date.getHours()).padStart(2, '0');
        const min = String(date.getMinutes()).padStart(2, '0');
        const ss = String(date.getSeconds()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}T${hh}:${min}:${ss}`;
    }

    // 3. Pré-remplir les dates si les champs sont vides
    const starttimeInput = document.getElementById('starttime');
    const endtimeInput = document.getElementById('endtime');
    const eventTimeInput = document.getElementById('event_time');
    
    if (starttimeInput && endtimeInput && eventTimeInput && 
        !starttimeInput.value && !endtimeInput.value && !eventTimeInput.value) {
        
        const now = new Date();
        
        // Début : maintenant moins 5 minutes (pour capturer l'événement)
        const startTime = new Date(now.getTime() - 5 * 60000); 
        starttimeInput.value = formatDateTime(startTime);

        // Fin : maintenant
        endtimeInput.value = formatDateTime(now);

        // Événement : maintenant moins 2 minutes (estimation)
        const eventTime = new Date(now.getTime() - 2 * 60000);
        eventTimeInput.value = formatDateTime(eventTime);
    }
    

    // 4. Gestion de la soumission du formulaire pour éviter les doubles clics
    form.addEventListener('submit', function() {
        // Désactiver le bouton pour éviter les soumissions multiples
        submitButton.disabled = true;
        
        // Changer le texte du bouton avec le nouveau message
        submitButton.textContent = "⚙️ Traitement en cours... Veuillez patienter pendant la récupération des données.";
        
        // Ajouter une classe pour styliser le bouton de chargement
        submitButton.classList.add('loading');
    });

});
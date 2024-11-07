let fontSize = 12;
        // Adjust font size based on device type
if (/Mobi|Android/i.test(navigator.userAgent)) {
    fontSize = 7; // size for mobile
}
function fetchCredentials() {
    fetch('/list_credentials')
        .then(response => response.text())
        .then(data => {
            document.getElementById('credentials-table').innerHTML = data;
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

document.addEventListener("DOMContentLoaded", function() {
    fetchCredentials();
    setInterval(fetchCredentials, 20000); // 20000 ms = 20 seconds
});
function adjustCredFontSize(change) {
    fontSize += change;
    document.getElementById('credentials-table').style.fontSize = fontSize + 'px';
}




function toggleCredToolbar() {
    const mainToolbar = document.querySelector('.toolbar');
    const toggleButton = document.getElementById('toggle-toolbar')
    const toggleIcon = document.getElementById('toggle-icon');
    if (mainToolbar.classList.contains('hidden')) {
        mainToolbar.classList.remove('hidden');
        toggleIcon.src = '/web/images/hide.png';
        toggleButton.setAttribute('data-open', 'false');
    } else {
        mainToolbar.classList.add('hidden');
        toggleIcon.src = '/web/images/reveal.png';
        toggleButton.setAttribute('data-open', 'true');

    }
}

document.addEventListener("DOMContentLoaded", function() {
    fetchCredentials(); // Initial fetch
    setInterval(fetchCredentials, 10000); // Refresh every 10 seconds
});




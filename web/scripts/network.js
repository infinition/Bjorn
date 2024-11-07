let fontSize = 12;
// Adjust font size based on device type
if (/Mobi|Android/i.test(navigator.userAgent)) {
    fontSize = 7; // size for mobile
}

function fetchNetworkData() {
    fetch('/network_data')
        .then(response => response.text())
        .then(data => {
            document.getElementById('network-table').innerHTML = data;
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function adjustNetworkFontSize(change) {
    fontSize += change;
    document.getElementById('network-table').style.fontSize = fontSize + 'px';
}

function toggleNetworkToolbar() {
    const mainToolbar = document.querySelector('.toolbar');
    const toggleButton = document.getElementById('toggle-toolbar');
    const toggleIcon = document.getElementById('toggle-icon');

    if (mainToolbar.classList.contains('hidden')) {
        mainToolbar.classList.remove('hidden');
        toggleIcon.src = '/web/images/hide.png';
        toggleButton.setAttribute('data-open', 'true');
    } else {
        mainToolbar.classList.add('hidden');
        toggleIcon.src = '/web/images/reveal.png';
        toggleButton.setAttribute('data-open', 'false');
    }
}






document.addEventListener("DOMContentLoaded", function() {
    fetchNetworkData(); // Initial fetch
    setInterval(fetchNetworkData, 60000); // Refresh every 60 seconds
});

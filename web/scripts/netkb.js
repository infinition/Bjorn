let fontSize = 12;
        // Adjust font size based on device type
if (/Mobi|Android/i.test(navigator.userAgent)) {
    fontSize = 7; // size for mobile
}
function fetchNetkbData() {
    fetch('/netkb_data')
        .then(response => response.text())
        .then(data => {
            document.getElementById('netkb-table').innerHTML = data;
        })
        .catch(error => {
            console.error('Error:', error);
        });
}
function adjustNetkbFontSize(change) {
    fontSize += change;
    document.getElementById('netkb-table').style.fontSize = fontSize + 'px';
}




function toggleNetkbToolbar() {
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
    fetchNetkbData(); // Initial fetch
    setInterval(fetchNetkbData, 10000); // Refresh every 10 seconds
});



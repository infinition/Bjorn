const logConsole = document.getElementById('log-console');
const mainToolbar = document.querySelector('.toolbar');
const toggleButton = document.getElementById('toggle-toolbar');
let fontSize = 16; // size for desktop
const maxLines = 2000; // Number of lines to keep in the console
const fileColors = new Map();
const levelClasses = {
    "DEBUG": "debug",
    "INFO": "info",
    "WARNING": "warning",
    "ERROR": "error",
    "CRITICAL": "critical",
    "SUCCESS": "success"
};

// Adjust font size based on device type
if (/Mobi|Android/i.test(navigator.userAgent)) {
    fontSize = 7; // size for mobile
}
logConsole.style.fontSize = fontSize + 'px';

function getRandomColor() {
    const letters = '89ABCDEF';  // Using only hex value for lighter colors
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * letters.length)];
    }
    return color;
}

let logInterval;
let isConsoleOn = false;

function fetchLogs() {
    fetch('/get_logs')
        .then(response => response.text())
        .then(data => {
            const lines = data.split('\n');
            const newContent = [];

            lines.forEach(line => {
                let modifiedLine = line;
                const regexFile = /(\w+\.py)/g;
                let matchFile;
                while ((matchFile = regexFile.exec(line)) !== null) {
                    const fileName = matchFile[1];
                    if (line.includes('==>') || line.includes('<==')) 
                    return;
                    if (!fileColors.has(fileName)) {
                        fileColors.set(fileName, getRandomColor());
                    }
                    modifiedLine = modifiedLine.replace(fileName, `<span style="color: ${fileColors.get(fileName)};">${fileName}</span>`);
                }

                const regexLevel = /\b(DEBUG|INFO|WARNING|ERROR|CRITICAL|SUCCESS)\b/g;
                modifiedLine = modifiedLine.replace(regexLevel, (match) => {
                    return `<span class="${levelClasses[match]}">${match}</span>`;
                });

                const regexLineNumber = /^\d+/;
                modifiedLine = modifiedLine.replace(regexLineNumber, (match) => {
                    return `<span class="line-number">${match}</span>`;
                });

                const regexNumbers = /\b\d+\b/g;
                modifiedLine = modifiedLine.replace(regexNumbers, (match) => {
                    return `<span class="number">${match}</span>`;
                });

                newContent.push(modifiedLine);
            });

            logConsole.innerHTML += newContent.join('<br>') + '<br>';

            let allLines = logConsole.innerHTML.split('<br>');
            if (allLines.length > maxLines) {
                allLines = allLines.slice(allLines.length - maxLines);
                logConsole.innerHTML = allLines.join('<br>');
            }
            logConsole.scrollTop = logConsole.scrollHeight;
        })
        .catch(error => console.error('Error fetching logs:', error));
}

// setInterval(fetchLogs, 1500); /
function startConsole() {
    // Start fetching logs every 1.5 seconds
    logInterval = setInterval(fetchLogs, 1500); // Fetch logs every 1.5 seconds
}
function stopConsole() {
    clearInterval(logInterval);
}
function toggleConsole() {
    const toggleImage = document.getElementById('toggle-console-image');
    
    if (isConsoleOn) {
        stopConsole();
        toggleImage.src = '/web/images/off.png';
    } else {
        startConsole();
        toggleImage.src = '/web/images/on.png';
    }
    
    isConsoleOn = !isConsoleOn;
}
function adjustFontSize(change) {
    fontSize += change;
    logConsole.style.fontSize = fontSize + 'px';
}

document.addEventListener('DOMContentLoaded', () => {
    const mainToolbar = document.getElementById('mainToolbar');
    const toggleButton = document.getElementById('toggle-toolbar');
    const toggleIcon = document.getElementById('toggle-icon');

    toggleButton.addEventListener('click', toggleToolbar);

    function toggleToolbar() {
        const isOpen = toggleButton.getAttribute('data-open') === 'true';
        if (isOpen) {
            mainToolbar.classList.add('hidden');
            toggleIcon.src = '/web/images/reveal.png';
            toggleButton.setAttribute('data-open', 'false');
        } else {
            mainToolbar.classList.remove('hidden');
            toggleIcon.src = '/web/images/hide.png';
            toggleButton.setAttribute('data-open', 'true');
        }
        toggleConsoleSize();
    }

    function toggleConsoleSize() {
        //Function to adjust the size of the console based on the toolbar visibility
    }
});

function loadDropdown() {
    const dropdownContent = `
        <div class="dropdown">
            <button type="button" class="toolbar-button" onclick="toggleDropdown()" data-open="false">
                <img src="/web/images/manual_icon.png" alt="Icon_actions" style="height: 50px;">
            </button>
            <div class="dropdown-content">
                <button type="button" onclick="clear_files()">Clear Files</button>
                <button type="button" onclick="clear_files_light()">Clear Files Light</button>
                <button type="button" onclick="reboot_system()">Reboot</button>
                <button type="button" onclick="disconnect_wifi()">Disconnect Wi-Fi</button>
                <button type="button" onclick="shutdown_system()">Shutdown</button>
                <button type="button" onclick="restart_bjorn_service()">Restart Bjorn Service</button>
                <button type="button" onclick="backup_data()">Backup</button>
                <button type="button" onclick="restore_data()">Restore</button>
                <button type="button" onclick="stop_orchestrator()">Stop Orchestrator</button>
                <button type="button" onclick="start_orchestrator()">Start Orchestrator</button>
                <button type="button" onclick="initialize_csv()">Create Livestatus, Actions & Netkb CSVs</button>
            </div>
        </div>
    `;
    document.getElementById('dropdown-container').innerHTML = dropdownContent;
}

function loadBjornDropdown() {
    const bjornDropdownContent = `
        <div class="dropdown bjorn-dropdown">
            <button type="button" class="toolbar-button" onclick="toggleBjornDropdown()" data-open="false">
                <img src="/web/images/bjorn_icon.png" alt="Icon_bjorn" style="height: 50px;">
            </button>
            <div class="dropdown-content">
                <img id="screenImage_Home"  onclick="window.location.href='/bjorn.html'" src="screen.png" alt="Bjorn" style="width: 100%;">
            </div>
        </div>
    `;
    document.getElementById('bjorn-dropdown-container').innerHTML = bjornDropdownContent;
    startLiveview(); // Start live view when Bjorn dropdown is loaded
}

// Call the function to load the dropdowns when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    loadDropdown();
    loadBjornDropdown();
});


function clear_files() {
    fetch('/clear_files', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to clear files: ' + error.message));
}

function clear_files_light() {
    fetch('/clear_files_light', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to clear files: ' + error.message));
}

function reboot_system() {
    fetch('/reboot', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to reboot: ' + error.message));
}

function shutdown_system() {
    fetch('/shutdown', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to shutdown: ' + error.message));
}

function restart_bjorn_service() {
    fetch('/restart_bjorn_service', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to restart service: ' + error.message));
}

function backup_data() {
    fetch('/backup', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const link = document.createElement('a');
                link.href = data.url;
                link.download = data.filename;
                link.click();
                alert('Backup completed successfully');
            } else {
                alert('Backup failed: ' + data.message);
            }
        })
        .catch(error => alert('Backup failed: ' + error.message));
}

function restore_data() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.zip';
    input.onchange = () => {
        const file = input.files[0];
        const formData = new FormData();
        formData.append('file', file);

        fetch('/restore', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Restore failed: ' + error.message));
    };
    input.click();
}

function stop_orchestrator() {
    fetch('/stop_orchestrator', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to stop orchestrator: ' + error.message));
}

function start_orchestrator() {
    fetch('/start_orchestrator', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to start orchestrator: ' + error.message));
}

function disconnect_wifi() {
    fetch('/disconnect_wifi', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to disconnect: ' + error.message));
}

function initialize_csv() {
    fetch('/initialize_csv', { method: 'POST' })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => alert('Failed to initialize CSV: ' + error.message));
}

// Dropdown toggle logic
function toggleDropdown() {
    const dropdown = document.querySelector('.dropdown');
    const button = document.querySelector('.action-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
    } else {
        dropdown.classList.add('show');
        button.setAttribute('data-open', 'true');
    }
}

function closeDropdownIfOpen(event) {
    const dropdown = document.querySelector('.dropdown');
    const button = document.querySelector('.action-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (!event.target.closest('.dropdown') && isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
    }
}

// actions.js

let imageIntervalId;
let intervalId;
const delay = 2000 // Adjust this value to match your delay

let lastUpdate = 0;

function updateImage() {
    const now = Date.now();
    if (now - lastUpdate >= delay) {
        lastUpdate = now;
        const image = document.getElementById("screenImage_Home");
        const newImage = new Image();
        newImage.onload = function() {
            image.src = newImage.src; // Update only if the new image loads successfully
        };
        newImage.onerror = function() {
            console.warn("New image could not be loaded, keeping the previous image.");
        };
        newImage.src = "screen.png?t=" + new Date().getTime(); // Prevent caching
    }
}

function startLiveview() {
    updateImage(); // Immediately update the image
    intervalId = setInterval(updateImage, delay); // Then update at the specified interval
}

function stopLiveview() {
    clearInterval(intervalId);
}

// Dropdown toggle logic for Bjorn
function toggleBjornDropdown() {
    const dropdown = document.querySelector('.bjorn-dropdown');
    const button = document.querySelector('.bjorn-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
        stopLiveview(); // Stop image refresh when closing
    } else {
        dropdown.classList.add('show');
        button.setAttribute('data-open', 'true');
        startLiveview(); // Start image refresh when opening
    }
}

function closeBjornDropdownIfOpen(event) {
    const dropdown = document.querySelector('.bjorn-dropdown');
    const button = document.querySelector('.bjorn-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (!event.target.closest('.bjorn-dropdown') && isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
        stopLiveview(); // Stop image refresh when closing
    }
}

document.addEventListener('click', closeBjornDropdownIfOpen);
document.addEventListener('touchstart', closeBjornDropdownIfOpen);

// Existing logic for Actions dropdown
function toggleDropdown() {
    const dropdown = document.querySelector('.dropdown');
    const button = document.querySelector('.action-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
    } else {
        dropdown.classList.add('show');
        button.setAttribute('data-open', 'true');
    }
}

function closeDropdownIfOpen(event) {
    const dropdown = document.querySelector('.dropdown');
    const button = document.querySelector('.action-button');
    const isOpen = button.getAttribute('data-open') === 'true';

    if (!event.target.closest('.dropdown') && isOpen) {
        dropdown.classList.remove('show');
        button.setAttribute('data-open', 'false');
    }
}



function generateConfigForm(config) {
    const formElement = document.querySelector(".config-form");
    formElement.innerHTML = ''; // Clear the form
    
    const leftColumn = document.createElement('div');
    leftColumn.classList.add('left-column');
    
    const rightColumn = document.createElement('div');
    rightColumn.classList.add('right-column');
    
    for (const [key, value] of Object.entries(config)) {
        if (key.startsWith("__title_")) {
            rightColumn.innerHTML += `<div class="section-title"><b>${value}</b></div>`;
        } else if (typeof value === "boolean") {
            const checked = value ? "checked" : "";
            leftColumn.innerHTML += `
    
                <div class="label-switch">
                    <label class="switch">
                        <input type="checkbox" id="${key}" name="${key}" ${checked}>
                        <span class="slider round"></span>
                    </label>
                    <label for="${key}">${key}</label>
                </div>
            `;
        } else if (Array.isArray(value)) {
            const listValue = value.join(',');
            rightColumn.innerHTML += `
                <div class="section-item">
                    <label for="${key}">${key}:</label>
                    <input type="text" id="${key}" name="${key}" value="${listValue}">
                </div>
            `;
        } else if (!isNaN(value) && !key.toLowerCase().includes("ip") && !key.toLowerCase().includes("mac")) {
            rightColumn.innerHTML += `
                <div class="section-item">
                    <label for="${key}">${key}:</label>
                    <input type="number" id="${key}" name="${key}" value="${value}">
                </div>
            `;
        } else {
            rightColumn.innerHTML += `
                <div class="section-item">
                    <label for="${key}">${key}:</label>
                    <input type="text" id="${key}" name="${key}" value="${value}">
                </div>
            `;
        }
    }
    
    formElement.appendChild(leftColumn);
    formElement.appendChild(rightColumn);
    
    // Add a spacer div at the end for better scrolling experience
    formElement.innerHTML += '<div style="height: 50px;"></div>';
    }
    
    
    function saveConfig() {
        console.log("Saving configuration...");
        const formElement = document.querySelector(".config-form");
    
        if (!formElement) {
            console.error("Form element not found.");
            return;
        }
    
        const formData = new FormData(formElement);
        const formDataObj = {};
        // Each of these fields contains an array of data.  Lets track these so we can ensure the format remains an array for the underlying structure.
        const arrayFields = [
            "portlist",
            "mac_scan_blacklist",
            "ip_scan_blacklist",
            "steal_file_names",
            "steal_file_extensions",
        ];

        formData.forEach((value, key) => {
            // Check if the input from the user contains a `,` character or is a known array field
            if (value.includes(',') || arrayFields.includes(key)) {
                formDataObj[key] = value.split(',').map(item => {
                    const trimmedItem = item.trim();
                    return isNaN(trimmedItem) || trimmedItem == "" ? trimmedItem : parseFloat(trimmedItem);
                });
            } else {
                formDataObj[key] = value === 'on' ? true : (isNaN(value) ? value : parseFloat(value));
            }
        });
    
        formElement.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
            if (!formData.has(checkbox.name)) {
                formDataObj[checkbox.name] = false;
            }
        });
    
        console.log("Form data:", formDataObj);
    
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/save_config", true);
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.onreadystatechange = function () {
            if (xhr.readyState == 4) {
                console.log("Response status: " + xhr.status);
                if (xhr.status == 200) {
                    loadConfig();
                } else {
                    console.error("Failed to save configuration");
                    alert("Failed to save configuration");
                }
            }
        };
        xhr.send(JSON.stringify(formDataObj));
    }
    
    function restoreDefault() {
        fetch('/restore_default_config').then(response => response.json()).then(data => {
            generateConfigForm(data);
        });
    }
    
    function loadConfig() {
        fetch('/load_config').then(response => response.json()).then(data => {
            generateConfigForm(data);
        });
    }
    
    function toggleWifiPanel() {
        let wifiPanel = document.getElementById('wifi-panel');
        if (wifiPanel.style.display === 'block') {
            clearInterval(wifiIntervalId);
            wifiPanel.style.display = 'none';
        } else {
            scanWifi(true); // Pass true to start the update interval
        }
    }
    
    function closeWifiPanel() {
        clearInterval(wifiIntervalId);
        let wifiPanel = document.getElementById('wifi-panel');
        wifiPanel.style.display = 'none';
    }
    
    
    let wifiIntervalId;
    
    function scanWifi(update = false) {
        fetch('/scan_wifi')
            .then(response => response.json())
            .then(data => {
                console.log("Current SSID:", data.current_ssid); // Debugging
                let wifiPanel = document.getElementById('wifi-panel');
                let wifiList = document.getElementById('wifi-list');
                wifiList.innerHTML = '';
                data.networks.forEach(network => {
                    let li = document.createElement('li');
                    li.innerText = network;
                    li.setAttribute('data-ssid', network);
                    li.onclick = () => connectWifi(network);
                    if (network === data.current_ssid) {
                        li.classList.add('current-wifi'); // Apply the class if it's the current SSID
                        li.innerText += " ✅"; // Add the checkmark icon
                    }
                    wifiList.appendChild(li);
                });
                if (data.networks.length > 0) {
                    wifiPanel.style.display = 'block';
                    if (update) {
                        clearInterval(wifiIntervalId);
                        wifiIntervalId = setInterval(() => scanWifi(true), 5000);
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }
    
    
    
    function connectWifi(ssid) {
        let password = prompt("Enter the password for " + ssid);
        if (password) {
            fetch('/connect_wifi', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ssid: ssid, password: password }),
            })
            .then(response => response.json())
            .then(data => alert(data.message))
            .catch(error => alert('Error: ' + error));
        }
    }
    
    
        
    
    function adjustFormPadding() {
        const toolbarHeight = document.querySelector('.toolbar').offsetHeight;
        const formElement = document.querySelector('.config-form');
        formElement.style.paddingBottom = toolbarHeight + 'px';
    }
    
    window.addEventListener('load', () => {
        adjustFormPadding();
    });
    window.addEventListener('resize', () => {
        adjustFormPadding();
    }); // Adjust size on window resize
    
    document.addEventListener("DOMContentLoaded", function() {
        loadConfig();
    
    });

    let fontSize = 12;

    // Adjust font size based on device type
    if (/Mobi|Android/i.test(navigator.userAgent)) {
        fontSize = 7; // size for mobile devices
    }
    
    function adjustConfigFontSize(change) {
        fontSize += change;
        
        // Retrieve all elements with the class 'section-item'
        var sectionItems = document.getElementsByClassName('section-item');
        
        // Loop through each element and apply the style
        for (var i = 0; i < sectionItems.length; i++) {
            // Apply the style to the section element
            sectionItems[i].style.fontSize = fontSize + 'px';
            
            // Retrieve all inputs inside this section element
            var inputs = sectionItems[i].getElementsByTagName('input');
            
            // Loop through each input and apply the style
            for (var j = 0; j < inputs.length; j++) {
                inputs[j].style.fontSize = fontSize + 'px';
            }
            
            // Retrieve all elements with the class 'switch' inside this section element
            var switches = sectionItems[i].getElementsByClassName('switch');
            
            // Loop through each switch and apply the style
            for (var k = 0; k < switches.length; k++) {
                switches[k].style.fontSize = fontSize + 'px';
            }
    
            // Retrieve all elements with the class 'slider round' inside this section element
            var sliders = sectionItems[i].getElementsByClassName('slider round');
            
            // Loop through each slider and apply the style
            for (var l = 0; l < sliders.length; l++) {
                sliders[l].style.width = fontSize * 2 + 'px';  // Adjust width based on fontSize
                sliders[l].style.height = fontSize + 'px';  // Adjust height based on fontSize
                sliders[l].style.borderRadius = fontSize / 2 + 'px';  // Adjust border-radius based on fontSize
            }
        }
    
        // Retrieve all elements with the class 'section-title'
        var sectionTitles = document.getElementsByClassName('section-title');
        
        // Loop through each element and apply the style
        for (var i = 0; i < sectionTitles.length; i++) {
            sectionTitles[i].style.fontSize = fontSize + 'px';
        }
    
        // Retrieve all elements with the class 'label-switch'
        var labelSwitches = document.getElementsByClassName('label-switch');
        
        // Loop through each element and apply the style
        for (var i = 0; i < labelSwitches.length; i++) {
            labelSwitches[i].style.fontSize = fontSize + 'px';
        }
        
        // Apply the style to the element with the class 'config-form'
        document.querySelector('.config-form').style.fontSize = fontSize + 'px';
    }
    

    

function toggleConfigToolbar() {
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
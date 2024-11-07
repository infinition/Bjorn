let fontSize = 14;
// Adjust font size based on device type
if (/Mobi|Android/i.test(navigator.userAgent)) {
    fontSize = 7; // size for mobile
}

document.addEventListener("DOMContentLoaded", function() {
    fetch('/list_files')
        .then(response => response.json())
        .then(data => {
            document.getElementById('file-list').innerHTML = generateFileListHTML(data, "/", 0);
        })
        .catch(error => {
            console.error('Error:', error);
        });
});

function generateFileListHTML(files, path, indent) {
    let html = '<ul>';
    files.forEach(file => {
        if (file.is_directory) {
            const icon = path === "/" ? "web/images/mainfolder.png" : "web/images/subfolder.png";
            html += `
                <li style="margin-left: ${indent * 5}px;">
                    <img src="${icon}" alt="Folder Icon" style="height: 20px;">
                    <strong>${file.name}</strong>
                    <ul>
                        ${generateFileListHTML(file.children || [], `${path}/${file.name}`, indent + 1)}
                    </ul>
                </li>`;
        } else {
            const icon = "web/images/file.png";
            html += `
                <li style="margin-left: ${indent * 5}px;">
                    <img src="${icon}" alt="File Icon" style="height: 20px;">
                    <a href="/download_file?path=${encodeURIComponent(file.path)}">${file.name}</a>
                </li>`;
        }
    });
    html += '</ul>';
    return html;
}

function adjustLootFontSize(change) {
    fontSize += change;
    document.getElementById('file-list').style.fontSize = fontSize + 'px';
}

function toggleLootToolbar() {
    const mainToolbar = document.querySelector('.toolbar');
    const toggleButton = document.getElementById('toggle-toolbar');
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
    setInterval(() => {
        fetch('/list_files')
            .then(response => response.json())
            .then(data => {
                document.getElementById('file-list').innerHTML = generateFileListHTML(data, "/", 0);
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }, 10000); // Refresh every 10 seconds
});

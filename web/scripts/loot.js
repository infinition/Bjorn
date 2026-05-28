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
    let html = '<ul class="tree-list">';
    files.forEach(file => {
        if (file.is_directory) {
            const icon = path === "/" ? "/web/images/mainfolder.png" : "/web/images/subfolder.png";
            html += `
                <li class="tree-branch" style="padding-left: ${indent > 0 ? 12 : 0}px;">
                    <div class="tree-item folder-item">
                        <img src="${icon}" alt="Folder" class="tree-icon">
                        <span>${file.name}</span>
                    </div>
                    ${generateFileListHTML(file.children || [], `${path}/${file.name}`, indent + 1)}
                </li>`;
        } else {
            const icon = "/web/images/file.png";
            html += `
                <li class="tree-branch" style="padding-left: ${indent > 0 ? 12 : 0}px;">
                    <div class="tree-item file-item">
                        <a href="/download_file?path=${encodeURIComponent(file.path)}">
                            <img src="${icon}" alt="File" class="tree-icon">
                            <span>${file.name}</span>
                        </a>
                    </div>
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

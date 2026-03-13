let authRequired = false;
let authenticated = false;
let latestConnectivityState = {};

function setWifiFormEnabled(enabled) {
    const form = document.getElementById('wifi-form');
    form.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = !enabled;
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.message || data.error || `Request failed with status ${response.status}`);
    }
    return data;
}

function renderConnectivityState(state) {
    latestConnectivityState = state;
    const summary = document.getElementById('setup-summary');
    const stateGrid = document.getElementById('setup-state-grid');
    const portalHelper = document.getElementById('portal-helper');

    const wifiConnection = state.wifi_connection || 'none';
    const wifiConnectivity = state.wifi_connectivity || 'unknown';
    const btPanUrl = state.bluetooth_pan_url || 'unavailable';
    const setupApUrl = state.setup_ap_url || 'unavailable';
    const preferredUrl = state.preferred_ui_url || 'unavailable';
    const accessMode = state.setup_ap_active
        ? 'setup ap (primary)'
        : (state.bluetooth_pan_active ? 'bluetooth pan (secondary)' : 'normal lan');

    if (state.setup_ap_active) {
        summary.textContent = `Setup AP is the primary phone setup path. Stay on ${state.setup_ap_ssid || 'bjorn-setup'} and open ${setupApUrl} to get Bjorn onto Wi-Fi.`;
        portalHelper.hidden = true;
    } else if (state.portal_detected && state.bluetooth_pan_active) {
        summary.textContent = `Captive portal detected. Bluetooth PAN is a secondary Android-only path. Turn off Wi-Fi and mobile data on the phone, open ${btPanUrl}, then visit http://neverssl.com to complete sign-in.`;
        portalHelper.hidden = false;
    } else if (state.bluetooth_pan_active) {
        summary.textContent = `Bluetooth PAN is a secondary Android-only link. If ${btPanUrl} does not load, turn off Wi-Fi and mobile data on the phone. Use the setup AP when Bjorn is offline for the most reliable phone setup flow.`;
        portalHelper.hidden = true;
    } else {
        summary.textContent = `Wi-Fi: ${wifiConnection} | Connectivity: ${wifiConnectivity}. If Bjorn goes offline, use the setup AP at ${setupApUrl}.`;
        portalHelper.hidden = true;
    }

    const items = [
        { label: 'Access Mode', value: accessMode },
        { label: 'Current URL', value: preferredUrl },
        { label: 'Wi-Fi State', value: state.wifi_state || 'unknown' },
        { label: 'Wi-Fi Connection', value: wifiConnection },
        { label: 'Captive Portal', value: state.portal_detected ? 'detected' : 'no' },
        { label: 'Setup AP (primary)', value: state.setup_ap_active ? `${state.setup_ap_ssid} (${setupApUrl})` : setupApUrl },
        { label: 'Bluetooth PAN (secondary)', value: state.bluetooth_pan_active ? btPanUrl : (state.bluetooth_pan_error || 'inactive') },
        { label: 'PAN Clients', value: String(state.bluetooth_pan_client_count || 0) },
        { label: 'Wi-Fi Join Lock', value: state.wifi_transition_locked ? 'connecting' : 'idle' },
    ];

    stateGrid.innerHTML = '';
    items.forEach((item) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'setup-stat';

        const label = document.createElement('span');
        label.className = 'setup-stat-label';
        label.textContent = item.label;

        const value = document.createElement('span');
        value.className = 'setup-stat-value';
        value.textContent = item.value;

        wrapper.appendChild(label);
        wrapper.appendChild(value);
        stateGrid.appendChild(wrapper);
    });
}

function renderWifiNetworks(data) {
    const list = document.getElementById('wifi-networks');
    list.innerHTML = '';

    if (!data.networks || data.networks.length === 0) {
        const item = document.createElement('li');
        item.textContent = data.message || 'No scan results available right now. Manual SSID entry still works.';
        list.appendChild(item);
        return;
    }

    data.networks.forEach((network) => {
        const ssid = typeof network === 'string' ? network : network.ssid;
        const security = typeof network === 'string' ? '' : network.security;
        const signal = typeof network === 'string' ? '' : network.signal;
        const active = typeof network === 'string' ? false : network.active;

        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'setup-network-button';

        const name = document.createElement('span');
        name.textContent = ssid;

        const details = document.createElement('small');
        const detailParts = [];
        if (signal) {
            detailParts.push(`${signal}%`);
        }
        if (security) {
            detailParts.push(security);
        }
        if (active) {
            detailParts.push('connected');
        }
        details.textContent = detailParts.join(' ');

        button.appendChild(name);
        button.appendChild(details);
        button.onclick = () => {
            document.getElementById('ssid').value = ssid;
            document.getElementById('password').focus();
        };

        item.appendChild(button);
        list.appendChild(item);
    });
}

async function loadConnectivityState() {
    try {
        const state = await fetchJson('/connectivity_state');
        renderConnectivityState(state);
    } catch (error) {
        setText('setup-summary', `Failed to load connectivity state: ${error.message}`);
    }
}

async function loadAuthStatus() {
    try {
        const status = await fetchJson('/auth/status');
        authRequired = Boolean(status.auth_required);
        authenticated = Boolean(status.authenticated);

        const authCard = document.getElementById('auth-card');
        const authStatus = document.getElementById('auth-status');
        const authMessage = document.getElementById('auth-message');

        if (!authRequired) {
            authCard.hidden = true;
            authMessage.textContent = '';
            setWifiFormEnabled(true);
            return;
        }

        authCard.hidden = false;
        authStatus.textContent = authenticated
            ? 'Setup access is unlocked in this browser.'
            : (status.hint || 'Enter the setup code shown on Bjorn\'s screen.');
        authMessage.textContent = authenticated ? 'You can now change Wi-Fi settings and use the admin actions in the main UI.' : '';
        setWifiFormEnabled(authenticated);
    } catch (error) {
        setText('auth-status', `Failed to load setup auth status: ${error.message}`);
        setWifiFormEnabled(false);
    }
}

async function loginSetup(event) {
    event.preventDefault();
    const message = document.getElementById('auth-message');
    const token = document.getElementById('auth-token').value.trim();

    if (!token) {
        message.textContent = 'Enter the 6-digit setup code from Bjorn\'s screen.';
        return;
    }

    message.textContent = 'Checking setup code...';
    try {
        const data = await fetchJson('/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ token }),
        });
        message.textContent = data.message || 'Setup access granted.';
        document.getElementById('auth-token').value = '';
        await loadAuthStatus();
    } catch (error) {
        message.textContent = error.message;
    }
}

async function logoutSetup() {
    const message = document.getElementById('auth-message');
    message.textContent = 'Forgetting setup access for this browser...';
    try {
        const data = await fetchJson('/auth/logout', { method: 'POST' });
        message.textContent = data.message || 'Logged out.';
        await loadAuthStatus();
    } catch (error) {
        message.textContent = error.message;
    }
}

async function scanWifi() {
    const message = document.getElementById('wifi-message');
    message.textContent = 'Scanning for Wi-Fi networks...';

    try {
        const data = await fetchJson('/scan_wifi');
        message.textContent = data.current_ssid
            ? `Current Wi-Fi: ${data.current_ssid}`
            : (data.message || 'Select a scanned SSID or enter one manually.');
        renderWifiNetworks(data);
    } catch (error) {
        message.textContent = `Wi-Fi scan failed: ${error.message}`;
    }
}

async function connectWifi(event) {
    event.preventDefault();
    const ssid = document.getElementById('ssid').value.trim();
    const password = document.getElementById('password').value;
    const message = document.getElementById('wifi-message');

    if (!ssid) {
        message.textContent = 'SSID is required.';
        return;
    }

    if (authRequired && !authenticated) {
        message.textContent = 'Unlock setup with the code from Bjorn\'s screen before changing Wi-Fi.';
        return;
    }

    let reconnectHint = 'If it fails, reconnect and try again.';
    if (latestConnectivityState.setup_ap_active) {
        reconnectHint = `If it fails, rejoin ${latestConnectivityState.setup_ap_ssid || 'bjorn-setup'} and try again.`;
    } else if (latestConnectivityState.bluetooth_pan_active) {
        reconnectHint = `If the page stops responding, keep Bluetooth connected, turn off Wi-Fi and mobile data on the phone, and reopen ${latestConnectivityState.bluetooth_pan_url || 'http://172.22.0.1:8000'}/setup.html.`;
    }

    message.textContent = `Submitting Wi-Fi credentials for ${ssid}. Bjorn may drop the temporary link while it tries to join. ${reconnectHint}`;
    try {
        const data = await fetchJson('/connect_wifi', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ ssid, password }),
        });
        message.textContent = data.message || 'Bjorn is attempting to connect.';
    } catch (error) {
        message.textContent = `Wi-Fi connect request failed: ${error.message}`;
        if (error.message.includes('Setup authentication is required')) {
            await loadAuthStatus();
        }
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    setWifiFormEnabled(false);
    document.getElementById('auth-form').addEventListener('submit', loginSetup);
    document.getElementById('auth-logout').addEventListener('click', logoutSetup);
    document.getElementById('wifi-form').addEventListener('submit', connectWifi);
    document.getElementById('scan-button').addEventListener('click', scanWifi);
    await loadConnectivityState();
    await loadAuthStatus();
    await scanWifi();
    setInterval(loadConnectivityState, 5000);
    setInterval(loadAuthStatus, 15000);
});

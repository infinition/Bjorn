# 🖲️ Bjorn Development

<p align="center">
  <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="98">
</p>

## 📚 Table of Contents

- [Design](#-design)
- [Educational Aspects](#-educational-aspects)
- [Disclaimer](#-disclaimer)
- [Extensibility](#-extensibility)
- [Development Status](#-development-status)
  - [Project Structure](#-project-structure)
  - [Core Files](#-core-files)
  - [Actions](#-actions)
  - [Data Structure](#-data-structure)
- [Detailed Project Description](#-detailed-project-description)
  - [Behaviour of Bjorn](#-behavior-of-bjorn)
- [Running Bjorn](#-running-bjorn)
  - [Manual Start](#-manual-start)
  - [Service Control](#-service-control)
  - [Fresh Start](#-fresh-start)
- [Important Configuration Files](#-important-configuration-files)
  - [Shared Configuration](#-shared-configuration-shared_configjson)
  - [Actions Configuration](#-actions-configuration-actionsjson)
- [E-Paper Display Support](#-e-paper-display-support)
  - [Ghosting Removed](#-ghosting-removed)
- [Development Guidelines](#-development-guidelines)
  - [Adding New Actions](#-adding-new-actions)
  - [Testing](#-testing)
- [Web Interface](#-web-interface)
- [Project Roadmap](#-project-roadmap)
  - [Current Focus](#-future-plans)
  - [Future Plans](#-future-plans)
- [License](#-license)

## 🎨 Design

- **Portability**: Self-contained and portable device, ideal for penetration testing.
- **Modularity**: Extensible architecture allowing  addition of new actions.
- **Visual Interface**: The e-Paper HAT provides a visual interface for monitoring the ongoing actions, displaying results or stats, and interacting with Bjorn .

## 📔 Educational Aspects

- **Learning Tool**: Designed as an educational tool to understand cybersecurity concepts and penetration testing techniques.
- **Practical Experience**: Provides a practical means for students and professionals to familiarize themselves with network security practices and vulnerability assessment tools.

## ✒️ Disclaimer

- **Ethical Use**: This project is strictly for educational purposes.
- **Responsibility**: The author and contributors disclaim any responsibility for misuse of Bjorn.
- **Legal Compliance**: Unauthorized use of this tool for malicious activities is prohibited and may be prosecuted by law.

## 🧩 Extensibility

- **Evolution**: The main purpose of Bjorn is to gain new actions and extend his arsenal over time.
- **Modularity**: Actions are designed to be modular and can be easily extended or modified to add new functionality.
- **Possibilities**: From capturing pcap files to cracking hashes, man-in-the-middle attacks, and more—the possibilities are endless.
- **Contribution**: It's up to the user to develop new actions and add them to the project.

## 🔦 Development Status

- **Project Status**: Ongoing development.
- **Current Version**: Scripted  auto-installer, or manual installation. Not yet packaged with Raspberry Pi OS.
- **Reason**: The project is still in an early stage, requiring further development and debugging.

### 🗂️ Project Structure

```
Bjorn/
├── Bjorn.py
├── comment.py
├── display.py
├── epd_helper.py
├── init_shared.py
├── kill_port_8000.sh
├── logger.py
├── orchestrator.py
├── requirements.txt
├── shared.py
├── utils.py
├── webapp.py
├── __init__.py
├── actions/
│   ├── ftp_connector.py
│   ├── ssh_connector.py
│   ├── smb_connector.py
│   ├── rdp_connector.py
│   ├── telnet_connector.py
│   ├── sql_connector.py
│   ├── steal_files_ftp.py
│   ├── steal_files_ssh.py
│   ├── steal_files_smb.py
│   ├── steal_files_rdp.py
│   ├── steal_files_telnet.py
│   ├── steal_data_sql.py
│   ├── nmap_vuln_scanner.py
│   ├── scanning.py
│   └── __init__.py
├── backup/
│   ├── backups/
│   └── uploads/
├── config/
├── data/
│   ├── input/
│   │   └── dictionary/
│   ├── logs/
│   └── output/
│       ├── crackedpwd/
│       ├── data_stolen/
│       ├── scan_results/
│       ├── vulnerabilities/
│       └── zombies/
└── resources/
    └── waveshare_epd/
```

### ⚓ Core Files

#### Bjorn.py

The main entry point for the application. It initializes and runs the main components, including the network scanner, orchestrator, display, and web server.

#### comment.py

Handles generating all the Bjorn comments displayed on the e-Paper HAT based on different themes/actions and statuses.

#### display.py

Manages the e-Paper HAT display, updating the screen with Bjorn character, the dialog/comments, and the current information such as network status, vulnerabilities, and various statistics.

#### epd_helper.py

Handles the low-level interactions with the e-Paper display hardware.

#### logger.py

Defines a custom logger with specific formatting and handlers for console and file logging. It also includes a custom log level for success messages.

#### orchestrator.py

Bjorn’s AI, a heuristic engine that orchestrates the different actions such as network scanning, vulnerability scanning, attacks, and file stealing. It loads and executes actions based on the configuration and sets the status of the actions and Bjorn. 

#### shared.py

Defines the `SharedData` class that holds configuration settings, paths, and methods for updating and managing shared data across different modules.

#### init_shared.py

Initializes shared data that is used across different modules. It loads the configuration and sets up necessary paths and variables.

#### utils.py

Contains utility functions used throughout the project.

#### webapp.py

Sets up and runs a web server to provide a web interface for changing settings, monitoring and interacting with Bjorn.

### ▶️ Actions

#### actions/scanning.py

Conducts network scanning to identify live hosts and open ports. It updates the network knowledge base (`netkb`) and generates scan results.

#### actions/nmap_vuln_scanner.py

Performs vulnerability scanning using Nmap. It parses the results and updates the vulnerability summary for each host.

#### Protocol Connectors

- **ftp_connector.py**: Brute-force attacks on FTP services.
- **ssh_connector.py**: Brute-force attacks on SSH services.
- **smb_connector.py**: Brute-force attacks on SMB services.
- **rdp_connector.py**: Brute-force attacks on RDP services.
- **telnet_connector.py**: Brute-force attacks on Telnet services.
- **sql_connector.py**: Brute-force attacks on SQL services.

#### File Stealing Modules

- **steal_files_ftp.py**: Steals files from FTP servers.
- **steal_files_smb.py**: Steals files from SMB shares.
- **steal_files_ssh.py**: Steals files from SSH servers.
- **steal_files_telnet.py**: Steals files from Telnet servers.
- **steal_data_sql.py**: Extracts data from SQL databases.
 
### 📇 Data Structure

#### Network Knowledge Base (netkb.csv)

Located at `data/netkb.csv`. Stores information about:

- Known hosts and their status. (Alive or offline)
- Open ports and vulnerabilities.
- Action execution history. (Success or failed)

**Preview Example:**

![netkb1](https://github.com/infinition/Bjorn/assets/37984399/f641a565-2765-4280-a7d7-5b25c30dcea5)
![netkb2](https://github.com/infinition/Bjorn/assets/37984399/f08114a2-d7d1-4f50-b1c4-a9939ba66056)

#### Scan Results

Located in `data/output/scan_results/`.
This file is generated everytime the network is scanned. It is used to consolidate the data and update netkb.

**Example:**

![Scan result](https://github.com/infinition/Bjorn/assets/37984399/eb4a313a-f90c-4c43-b699-3678271886dc)

#### Live Status (livestatus.csv)

Contains real-time information displayed on the e-Paper HAT:

- Total number of known hosts.
- Currently alive hosts.
- Open ports count.
- Other runtime statistics.

## 📖 Detailed Project Description

### 👀 Behavior of Bjorn

Once launched, Bjorn performs the following steps:

1. **Initialization**: Loads configuration, initializes shared data, and sets up necessary components such as the e-Paper HAT display.
2. **Network Scanning**: Scans the network to identify live hosts and open ports. Updates the network knowledge base (`netkb`) with the results.
3. **Orchestration**: Orchestrates different actions based on the configuration and network knowledge base. This includes performing vulnerability scanning, attacks, and file stealing.
4. **Vulnerability Scanning**: Performs vulnerability scans on identified hosts and updates the vulnerability summary.
5. **Brute-Force Attacks and File Stealing**: Starts brute-force attacks and steals files based on the configuration criteria.
6. **Display Updates**: Continuously updates the e-Paper HAT display with current information such as network status, vulnerabilities, and various statistics. Bjorn also displays random comments based on different themes and statuses.
7. **Web Server**: Provides a web interface for monitoring and interacting with Bjorn.

## ▶️ Running Bjorn

### 📗 Manual Start

To manually start Bjorn (without the service, ensure the service is  stopped « sudo systemctl stop bjorn.service »):

```bash
cd /home/bjorn/Bjorn

# Run Bjorn
sudo python Bjorn.py
```

### 🕹️ Service Control

Control the Bjorn service:

```bash
# Start Bjorn
sudo systemctl start bjorn.service

# Stop Bjorn
sudo systemctl stop bjorn.service

# Check status
sudo systemctl status bjorn.service

# View logs
sudo journalctl -u bjorn.service
```

### 🪄 Fresh Start

To reset Bjorn to a clean state:

```bash
sudo rm -rf /home/bjorn/Bjorn/config/*.json \
    /home/bjorn/Bjorn/data/*.csv \
    /home/bjorn/Bjorn/data/*.log \
    /home/bjorn/Bjorn/data/output/data_stolen/* \
    /home/bjorn/Bjorn/data/output/crackedpwd/* \
    /home/bjorn/Bjorn/config/* \
    /home/bjorn/Bjorn/data/output/scan_results/* \
    /home/bjorn/Bjorn/__pycache__ \
    /home/bjorn/Bjorn/config/__pycache__ \
    /home/bjorn/Bjorn/data/__pycache__ \
    /home/bjorn/Bjorn/actions/__pycache__ \
    /home/bjorn/Bjorn/resources/__pycache__ \
    /home/bjorn/Bjorn/web/__pycache__ \
    /home/bjorn/Bjorn/*.log \
    /home/bjorn/Bjorn/resources/waveshare_epd/__pycache__ \
    /home/bjorn/Bjorn/data/logs/* \
    /home/bjorn/Bjorn/data/output/vulnerabilities/* \
    /home/bjorn/Bjorn/data/logs/*

```

Everything will be recreated automatically at the next launch of Bjorn.

## ❇️ Important Configuration Files

### 🔗 Shared Configuration (`shared_config.json`)

Defines various settings for Bjorn, including:

- Boolean settings (`manual_mode`, `websrv`, `debug_mode`, etc.).
- Time intervals and delays.
- Network settings.
- Port lists and blacklists.
These settings are accessible on the webpage.

### Optional Web Authentication

`web_auth.py` implements opt-in HTTP Basic authentication using a salted scrypt
password verifier. Credentials are managed by `configure_web_auth.py` and kept
out of `shared_config.json`, the web configuration endpoint, and Git.

When no credential file exists, current unauthenticated behavior is preserved.
When credentials exist and are enabled, every GET, HEAD, POST, static asset,
and API route requires authentication. An existing but unreadable credential
file fails closed.

An HTTP Basic challenge without an Authorization header is an expected part of
browser authentication and still receives `401`, but it is not recorded as an
invalid-credential warning. Requests that supply a malformed or incorrect
Authorization header are logged with the method, normalized path, and source
address. Query parameters are omitted from that audit message.

Rejected entity-bearing requests never wait for a declared request body before
returning the authentication challenge. Bytes that are already available are
drained non-blockingly, then the server returns `401` with `Connection: close`.
This prevents an incomplete unauthenticated POST from monopolizing Bjorn's
single-request web server.

`install_stability_web_auth.sh` provides one transactional deployment path for
the complete scanner, lifecycle, hardware-shutdown, web-server, and optional
authentication change set. These areas share the web-server lifecycle and are
therefore installed and rolled back atomically instead of being stacked as
independent patches. The installer validates the source and credential files,
snapshots every managed target file, stops and restarts the systemd service
once, verifies that the new service remains active and serves HTTP on port
8000, and restores the complete snapshot automatically on failure. The web
server enables address reuse so a quick service restart does not make it drift
to port 8001. Successful deployment snapshots can also be selected explicitly
with `install_stability_web_auth.sh --restore`. A restore creates its own
recovery snapshot before changing files, so it can be reversed as well.
It also installs `/usr/local/sbin/http_auth` as the short management command;
the main installer offers that command and credential configuration as two
separate opt-in choices during a dedicated full-install step.
`install_bjorn.sh --show-plan` renders that integrated nine-step sequence
without creating logs, requiring root, or changing the system.
Credential validation failures remain inside the credential prompt so a retry
actually reruns the failed operation. Other required-step failures abort the
installer immediately. The installer starts `bjorn.service` itself and its
final verification requires both an active unit and HTTP `200` or `401` on port
8000, preventing warning-only or false-success fresh installations.
For automation, `http_auth set USER --password-stdin` reads one password line
from standard input so the plaintext is not placed in a command argument or
shell history.

Targeted web-authentication checks remain available for development:

```bash
# Syntax, compile, and isolated HTTP/unit tests
./tests/run_web_auth_validation.sh --unit

# Live command and HTTP checks with automatic credential restoration
sudo ./tests/run_web_auth_validation.sh --runtime \
  --target /home/bjorn/Bjorn

# Both levels
sudo ./tests/run_web_auth_validation.sh --all \
  --target /home/bjorn/Bjorn
```

The runtime test temporarily installs a generated verifier, exercises `set`,
`status`, `disable`, and `enable`, validates correct, incorrect, missing, and
private-file requests, checks the incomplete-POST regression and challenge
stress behavior, then restores the original credential file even on failure or
interruption. Release validation uses the combined runner documented below.

### 🛠️ Actions Configuration (`actions.json`)

Lists the actions to be performed by Bjorn, including (dynamically generated with the content of the folder):

- Module and class definitions.
- Port assignments.
- Parent-child relationships.
- Action status definitions.

## 📟 E-Paper Display Support

Currently, hardcoded for the 2.13-inch V2 & V4 e-Paper HAT. 
My program automatically detect the screen model and adapt the python expressions into my code.

For other versions:
- As I don't have the v1 and v3 to validate my algorithm, I just hope it will work properly.

### 🍾 Ghosting Removed!
In my journey to make Bjorn work with the different screen versions, I struggled, hacking several parameters and found out that it was possible to remove the ghosting of screens! I let you see this, I think this method will be very useful for all other projects with the e-paper screen!

## ✍️ Development Guidelines

### ➕ Adding New Actions

1. Create a new action file in `actions/`.
2. Implement required methods:
   - `__init__(self, shared_data)`
   - `execute(self, ip, port, row, status_key)`
3. Add the action to `actions.json`.
4. Follow existing action patterns.

### 🧪 Testing

1. Create a test environment.
2. Use an isolated network.
3. Follow ethical guidelines.
4. Document test cases.

### Stability and web-authentication validation

The combined contribution has two validation levels:

```bash
# Fast, non-invasive syntax, compile, unit, and integration checks
./tests/run_stability_web_auth_validation.sh --unit

# Live Raspberry Pi checks, including scanner completion, authentication,
# credential restoration, and a real service stop/start
sudo ./tests/run_stability_web_auth_validation.sh --runtime \
  --target /home/bjorn/Bjorn

# Both levels in the required order
sudo ./tests/run_stability_web_auth_validation.sh --all \
  --target /home/bjorn/Bjorn

# Optional longer observation before a release or pull request
sudo ./tests/run_stability_web_auth_validation.sh --all \
  --target /home/bjorn/Bjorn \
  --duration 90
```

The combined runner prints a compact, color-coded release summary by default
and shows complete underlying diagnostics automatically when a check fails.
Use `--verbose` to show every test name and internal validation marker, or set
`NO_COLOR=1` when plain output is required for a log collector.

The unit level also runs `tests/run_fresh_installer_integration.sh`. It sources
the real fresh installer with all destination paths redirected into a temporary
root, then exercises declining the optional tool, installing it without
credentials, configuring a real salted test verifier through the installed
command, checking mode `0600`, and using status/disable/enable. Linux requires
the management command to be a real symbolic link. The temporary root is
removed automatically and no live Bjorn file or system command path changes.

The runtime level verifies that every installed runtime file matches the tested
checkout. The service PID and authenticated web response must remain stable,
thread use must stay below a configurable limit, a scan must complete without
executor errors, shutdown must be clean and bounded, and the service must
return on port 8000. It then exercises the web-authentication command and HTTP
contract and restores the original credential state. The default runtime
observation is 30 seconds; use `--duration 90` for the longer
release-validation profile.
When a freshly started scan needs longer than the observation window, the
runner continues monitoring only until that scan completes, bounded by
`--scan-timeout` (90 seconds by default).

If systemd stops Bjorn while Nmap is producing its XML result, the resulting
interruption is logged as an expected shutdown event. The same exception
outside an active shutdown remains a scanner error.

The scanner also disables Rich's automatic progress refresh thread. Progress
updates remain visible, but run synchronously in the orchestrator-owned scan
thread so a daemon refresh cannot write to the terminal during interpreter
shutdown.

After all Bjorn-owned workers have stopped, the lifecycle handler gives any
remaining Python library thread a bounded grace period. Residual threads are
reported with their name, class, target, and daemon state. A thread that misses
the grace deadline makes shutdown fail explicitly instead of allowing a false
`Clean exit` followed by an interpreter-shutdown traceback.

Display shutdown also puts the e-paper panel to sleep, closes every gpiozero
device created by the Waveshare backend, and closes the shared pin factory.
This stops gpiozero's hold worker and lgpio's callback thread before Python
finalization.

The Python lgpio binding starts one module-global notification daemon. Closing
the gpiochip alone does not stop its blocking pipe read, so final hardware
shutdown explicitly stops that worker, closes its notification handle to wake
the read, and joins it with a bounded timeout.

Host discovery is also shutdown-aware. `python-nmap` normally waits
indefinitely in `Popen.communicate()`, which can make `systemctl stop` wait for
an entire `/24` discovery pass. Bjorn now launches the equivalent Nmap XML
command with short polling intervals. A normal scan is never shortened; only
an active application shutdown terminates the child process. Completed output
continues through python-nmap's existing XML parser.

The scanner/lifecycle and authentication changes intentionally share one
`webapp.py`. A single installer and rollback snapshot prevent order-dependent
layering and ensure that the exact code covered by the combined validation
suite is the code running on the device.

For release validation on a freshly installed card, capture the pre-reboot
state and verify it after a real reboot with:

```bash
sudo ./tests/run_reboot_persistence_validation.sh --prepare
sudo reboot
# Reconnect after boot, then:
sudo ./tests/run_reboot_persistence_validation.sh --verify
```

The hand-off file contains only the old boot ID, expected HTTP result, a hash of
the credential file, and the management-command target. Verification requires a
new boot ID, the same access-control state, a completed scan, bounded thread
use, and a clean current-boot journal.

## 💻 Web Interface

- **Access**: `http://[device-ip]:8000`
- **Features**:
  - Real-time monitoring with a console.
  - Configuration management.
  - Viewing results. (Credentials and files)
  - System control.

## 🧭 Project Roadmap

### 🪛 Current Focus

- Stability improvements.
- Bug fixes.
- Service reliability.
- Documentation updates.

### 🧷 Future Plans

- Additional attack modules.
- Enhanced reporting.
- Improved user interface.
- Extended protocol support.

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

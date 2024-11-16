# <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="33"> Bjorn

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff)
![Status](https://img.shields.io/badge/Status-Development-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Reddit](https://img.shields.io/badge/Reddit-Bjorn__CyberViking-orange?style=for-the-badge&logo=reddit)](https://www.reddit.com/r/Bjorn_CyberViking)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289DA?style=for-the-badge&logo=discord)](https://discord.com/invite/B3ZH9taVfT)

<p align="center">
  <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="150">
  <img src="https://github.com/user-attachments/assets/1b490f07-f28e-4418-8d41-14f1492890c6" alt="bjorn_epd-removebg-preview" width="150">
</p>

Bjorn is a « Tamagotchi like » sophisticated, autonomous network scanning, vulnerability assessment, and offensive security tool designed to run on a Raspberry Pi equipped with a 2.13-inch e-Paper HAT. This document provides a detailed explanation of the project.


## 📚 Table of Contents

- [Introduction](#-introduction)
- [Features](#-features)
- [Getting Started](#-getting-started)
  - [Prerequisites](#-prerequisites)
  - [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Example](#-usage-example)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

## 📄 Introduction

Bjorn is a powerful tool designed to perform comprehensive network scanning, vulnerability assessment, and data ex-filtration. Its modular design and extensive configuration options allow for flexible and targeted operations. By combining different actions and orchestrating them intelligently, Bjorn can provide valuable insights into network security and help identify and mitigate potential risks.

The e-Paper HAT display and web interface make it easy to monitor and interact with Bjorn, providing real-time updates and status information. With its extensible architecture and customizable actions, Bjorn can be adapted to suit a wide range of security testing and monitoring needs.

## 🌟 Features

- **Network Scanning**: Identifies live hosts and open ports on the network.
- **Vulnerability Assessment**: Performs vulnerability scans using Nmap and other tools.
- **System Attacks**: Conducts brute-force attacks on various services (FTP, SSH, SMB, RDP, Telnet, SQL).
- **File Stealing**: Extracts data from vulnerable services.
- **User Interface**: Real-time display on the e-Paper HAT and web interface for monitoring and interaction.

![Bjorn Display](https://github.com/infinition/Bjorn/assets/37984399/bcad830d-77d6-4f3e-833d-473eadd33921)

## 🚀 Getting Started

## 📌 Prerequisites

### 📋 Prerequisites for RPI zero W (32bits)

![image](https://github.com/user-attachments/assets/3980ec5f-a8fc-4848-ab25-4356e0529639)

- Raspberry Pi OS installed. 
    - Stable:
      - System: 32-bit
      - Kernel version: 6.6
      - Debian version: 12 (bookworm) '2024-10-22-raspios-bookworm-armhf-lite'
- Username and hostname set to `bjorn`.
- 2.13-inch e-Paper HAT connected to GPIO pins.

### 📋 Prerequisites for RPI zero W2 (64bits)

![image](https://github.com/user-attachments/assets/e8d276be-4cb2-474d-a74d-b5b6704d22f5)

I did not develop Bjorn for the raspberry pi zero w2 64bits, but several feedbacks have attested that the installation worked perfectly.

- Raspberry Pi OS installed. 
    - Stable:
      - System: 64-bit
      - Kernel version: 6.6
      - Debian version: 12 (bookworm) '2024-10-22-raspios-bookworm-arm64-lite'
- Username and hostname set to `bjorn`.
- 2.13-inch e-Paper HAT connected to GPIO pins.


At the moment the paper screen v2  v4 have been tested and implemented.
I juste hope the V1 & V3 will work the same.

### 🔨 Installation

The fastest way to install Bjorn is using the automatic installation script :

```bash
# Download and run the installer
wget https://raw.githubusercontent.com/infinition/Bjorn/refs/heads/main/install_bjorn.sh
sudo chmod +x install_bjorn.sh && sudo ./install_bjorn.sh
# Choose the choice 1 for automatic installation. It may take a while as a lot of packages and modules will be installed. You must reboot at the end.
```

For **detailed information** about **installation** process go to [Install Guide](INSTALL.md)

## ⚡ Quick Start

**Need help ? You struggle to find Bjorn's IP after the installation ?**
Use my Bjorn Detector & SSH Launcher :

[https://github.com/infinition/bjorn-detector](https://github.com/infinition/bjorn-detector)

![ezgif-1-a310f5fe8f](https://github.com/user-attachments/assets/182f82f0-5c3a-48a9-a75e-37b9cfa2263a)

**Hmm, You still need help ?**
For **detailed information** about **troubleshooting** go to [Troubleshooting](TROUBLESHOOTING.md)

**Quick Installation**: you can use the fastest way to install **Bjorn** [Getting Started](#-getting-started)

## 💡 Usage Example

Here's a demonstration of how Bjorn autonomously hunts through your network like a Viking raider (fake demo for illustration):

```bash
# Reconnaissance Phase
[NetworkScanner] Discovering alive hosts...
[+] Host found: 192.168.1.100
    ├── Ports: 22,80,445,3306
    └── MAC: 00:11:22:33:44:55

# Attack Sequence 
[NmapVulnScanner] Found vulnerabilities on 192.168.1.100
    ├── MySQL 5.5 < 5.7 - User Enumeration
    └── SMB - EternalBlue Candidate

[SSHBruteforce] Cracking credentials...
[+] Success! user:password123
[StealFilesSSH] Extracting sensitive data...

# Automated Data Exfiltration
[SQLBruteforce] Database accessed!
[StealDataSQL] Dumping tables...
[SMBBruteforce] Share accessible
[+] Found config files, credentials, backups...
```

This is just a demo output - actual results will vary based on your network and target configuration.

All discovered data is automatically organized in the data/output/ directory, viewable through both the e-Paper display (as indicators) and web interface.
Bjorn works tirelessly, expanding its network knowledge base and growing stronger with each discovery.

No constant monitoring needed - just deploy and let Bjorn do what it does best: hunt for vulnerabilities.

🔧 Expand Bjorn's Arsenal!
Bjorn is designed to be a community-driven weapon forge. Create and share your own attack modules!

⚠️ **For educational and authorized testing purposes only** ⚠️

## 🤝 Contributing

The project welcomes contributions in:

- New attack modules.
- Bug fixes.
- Documentation.
- Feature improvements.

For **detailed information** about **contributing** process go to [Contributing Docs](CONTRIBUTING.md), [Code Of Conduct](CODE_OF_CONDUCT.md) and [Development Guide](DEVELOPMENT.md).

## 📫 Contact

- **Report Issues**: Via GitHub.
- **Guidelines**:
  - Follow ethical guidelines.
  - Document reproduction steps.
  - Provide logs and context.

- **Author**: __infinition__
- **GitHub**: [infinition/Bjorn](https://github.com/infinition/Bjorn)

## 🌠 Stargazers

[![Star History Chart](https://api.star-history.com/svg?repos=infinition/bjorn&type=Date)](https://star-history.com/#infinition/bjorn&Date)

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

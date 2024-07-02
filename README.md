
# Bjorn
![image](https://github.com/infinition/Bjorn/assets/37984399/537b2070-d673-4adb-8680-4492ef83679c)


## Introduction


Bjorn is a sophisticated network scanning, vulnerability assessment, and offensive security tool designed to run on a Raspberry Pi equipped with a 2.13-inch e-Paper HAT. This document provides a detailed explanation of the project:

## Features
- Network scanning
- Vulnerability assessment
- System attacks
- Credential brute forcing
- File stealing

## Design
- Portable, self-contained device
- Easily deployable for penetration testing and security assessments

## User Interface
- The e-Paper HAT provides a visual interface for monitoring the scanning process, displaying results, and interacting with Bjorn

## Educational Aspects
- Bjorn is designed as an educational tool to learn and understand cybersecurity and penetration testing techniques
- The primary goal is to provide a practical means for students and professionals to familiarize themselves with network security practices and vulnerability assessment tools

## Disclaimer
- This project is strictly for educational purposes
- The authors and contributors disclaim any responsibility for misuse of Bjorn
- Unauthorized use of this tool for malicious activities is prohibited and may be prosecuted by law

## Extensibility
- The main purpose of Bjorn is to gain new actions over time, so the actions are not limited to the ones listed above
- The actions are designed to be modular and can be easily extended or modified to add new functionality
- From capturing pcap files to cracking hashes, man-in-the-middle attacks, and more, the possibilities are endless
- It's up to the user to develop new actions and add them to the project

## Development Status
- **Project Status:** Ongoing development
- **Current Version:** Not yet packaged with the Raspberry Pi OS or associated services
- **Reason:** The project is still in an early stage, requiring further development and debugging
- **Current Launch Method:** Bjorn is currently launched manually


![Bjorn](https://github.com/infinition/Bjorn/assets/37984399/bcad830d-77d6-4f3e-833d-473eadd33921)


# Detailed Project Description for Bjorn

## Tree Structure

The project is organized as follows:

```
Bjorn_0107v6/
    Bjorn.py
    comment.py
    display.py
    init_shared.py
    logger.py
    orchestrator.py
    requirements.txt
    shared.py
    utils.py
    webapp.py
    __init__.py
    actions/
        ftp_connector.py
        nmap_vuln_scanner.py
        scanning.py
        smb_connector.py
        ssh_connector.py
        steal_files_ftp.py
        steal_files_smb.py
        steal_files_ssh.py
        steal_files_telnet.py
        telnet_connector.py
        __init__.py
    config/
    data/
        input/
            dictionary/
                passwords.txt
                users.txt
            scripts/
        logs/
        output/
            crackedpwd/
            data_stolen/
            scan_results/
            vulnerabilities/
            zombies/
    resources/
        __init__.py
        fonts/
        images/
        waveshare_epd/
            epd2in13_V2.py
            epdconfig.py
            __init__.py
    web/
        config.html
        index.html
```

## Core Files

### Bjorn.py
The main entry point for the application. It initializes and runs the main components, including the network scanner, orchestrator, display, and web server. 

### comment.py
Handles generating random comments displayed on the e-Paper HAT based on different themes and statuses.

### display.py
Manages the e-Paper HAT display, updating the screen with current information such as network status, vulnerabilities, and various statistics.

### logger.py
Defines a custom logger with specific formatting and handlers for console and file logging. It also includes a custom log level for success messages.

### orchestrator.py
Heuristic engine that orchestrates the different actions such as network scanning, vulnerability scanning, attacks and file stealing. It loads and executes actions based on the configuration and set the status of the actions and also the bjorn status.

### shared.py
Defines the SharedData class that holds configuration settings, paths, and methods for updating and managing shared data across different modules.

### init_shared.py
Initializes shared data that is used across different modules. It loads the configuration and sets up necessary paths and variables.

### utils.py
Contains utility functions used throughout the project.

### webapp.py
Sets up and runs a web server to provide a web interface for monitoring and interacting with Bjorn.


## Actions

### actions/ftp_connector.py
Performs brute-force attacks on FTP servers to crack credentials. It saves the cracked passwords to a file.

### actions/nmap_vuln_scanner.py
Performs vulnerability scanning using Nmap. It parses the results and updates the vulnerability summary for each host.

### actions/scanning.py
Conducts network scanning to identify live hosts and open ports. It updates the network knowledge base (netkb) and generates scan results.

### actions/smb_connector.py
Handles connections and interactions with SMB servers.

### actions/ssh_connector.py
Performs brute-force attacks on SSH servers to crack credentials. It saves the cracked passwords to a file.

### actions/telnet_connector.py
Performs brute-force attacks on Telnet servers to crack credentials. It saves the cracked passwords to a file.

### actions/steal_files_ftp.py
Steals files from FTP servers based on the configuration criteria.

### actions/steal_files_smb.py
Steals files from SMB servers based on the configuration criteria.

### actions/steal_files_ssh.py
Steals files from SSH servers based on the configuration criteria.

### actions/steal_files_telnet.py
Steals files from Telnet servers based on the configuration criteria.

### The main purpose of Bjorn is to gain new actions over time, so the actions are not limited to the ones listed above. The actions are designed to be modular and can be easily extended or modified to add new functionality. From capturing pcap files to cracking hashes, man in the middle attacks, and more, the possibilities are endless. It's up to the user to develop new actions and add them to the project.


## Configurations

### config/
This directory contains configuration files such as `shared_config.json` and `actions.json` that define settings and actions to be performed by Bjorn.


## Data

### data/
This directory contains subdirectories for input dictionaries, logs, and output data including cracked passwords, stolen data, scan results, vulnerabilities, and zombie clients.
### scan_result preview example:
![Scan result](https://github.com/infinition/Bjorn/assets/37984399/eb4a313a-f90c-4c43-b699-3678271886dc)



### data/netkb.csv
At the root of the data directory, there is netkb.csv, which is the network knowledge base that stores information about all known hosts and their open ports, permformed actions, and their status. This file is used to keep track of the network state and the actions performed on each host even on previous network.

### Netkb preview example:
![netkb1](https://github.com/infinition/Bjorn/assets/37984399/f641a565-2765-4280-a7d7-5b25c30dcea5)
![netkb2](https://github.com/infinition/Bjorn/assets/37984399/f08114a2-d7d1-4f50-b1c4-a9939ba66056)

### data/livestatus.csv
Contains the livestatus informations used to display the informations on the e-Paper HAT, such as all known hosts, open ports, all hosts currently alive...

#### data/input/
Contains dictionaries of usernames and passwords used for brute-force attacks and scripts used in the project.

#### data/logs/
Stores log files generated by the application.

#### data/output/
Stores output data including cracked passwords, stolen data, scan results, vulnerabilities, and zombie clients files.

### resources/
Contains resources such as fonts and images used by the application.

### tests/
Contains test scripts, at the moment it's an exemple of how could be implemented the a new action file. (attack)

### web/
Contains HTML files for the web interface.

## Behavior of Bjorn

Once launched, Bjorn performs the following steps:

1. **Initialization**: Loads configuration, initializes shared data, and sets up necessary components such as the e-Paper HAT display.
2. **Network Scanning**: Scans the network to identify live hosts and open ports. Updates the network knowledge base (netkb) with the results.

3. **Orchestration**: Orchestrates different actions based on the configuration and network knowledge base. This includes performing vulnerability scanning, attacks, and file stealing.
3. **Vulnerability Scanning**: Performs vulnerability scans on identified hosts and updates the vulnerability summary.
4. **Bruteforce, File Stealing and other Attacks**: Starts brute-force attacks, steals files based on the configuration criteria.
5. **Display Updates**: Continuously updates the e-Paper HAT display with current information such as network status, vulnerabilities, and various statistics. Bjorn also displays random comments based on different themes and statuses.
6. **Web Server**: Provides a web interface for monitoring and interacting with Bjorn.

## Important Files

### requirements.txt
Lists the Python packages required to run the project.

### Shared Configuration JSON (`shared_config.json`)
Defines various settings for Bjorn, including boolean settings, time intervals, text settings, and network settings.

### Actions Configuration JSON (`actions.json`)
Lists the actions to be performed by Bjorn, including the modules and classes to be used.

## Conclusion

Bjorn is a powerful tool designed to perform comprehensive network scanning, vulnerability assessment, and data exfiltration. Its modular design and extensive configuration options allow for flexible and targeted operations. By combining different actions and orchestrating them intelligently, Bjorn can provide valuable insights into network security and help identify and mitigate potential risks.
The e-Paper HAT display and web interface make it easy to monitor and interact with Bjorn, providing real-time updates and status information. With its extensible architecture and customizable actions, Bjorn can be adapted to suit a wide range of security testing and monitoring needs.







# Installing Bjorn on Raspberry Pi OS with a 2.13inch e-Paper HAT ###
Assuming that you have already installed Raspberry Pi OS on your Raspberry Pi with `bjorn` as the hostname & user and that you have connected the 2.13inch e-Paper HAT to the GPIO pins of your Raspberry Pi:

### Activate SPI & I2C ###
```bash
sudo raspi-config
```
- Enable SPI & I2C

### Install the required packages, libraries & update the system ###
```bash
sudo apt-get update && sudo apt-get upgrade
sudo apt install -y python3-pip wget git libopenjp2-7 nmap libopenblas-dev bluez-tools bluez dhcpcd5 bridge-utils
```

### Update nmap db ###
```bash
sudo nmap --script-updatedb
```

### Unlock the limits of the system ###
```bash
sudo vi /etc/security/limits.conf
```
Add the following lines:
```
* soft nofile 4096
* hard nofile 4096
```

### Reboot ###
```bash
sudo reboot
```

### Download the Bjorn repository & install the required packages ###
```bash
cd ~
sudo git clone https://github.com/infinition/Bjorn/
cd Bjorn
sudo pip install -r requirements.txt --break-system-packages
#I am using --break-system-packages because i'm not using any venv yet.
```



For the moment, the project is hardcoded to use the 2.13inch V2 e-Paper HAT. If you have another version, it might not work with V2. You need to modify the code in `shared.py` & `display.py` to import the correct version (v3, v4...). Get the file from [Waveshare e-Paper](https://github.com/waveshareteam/e-Paper) and replace the existing one in the `resources/waveshare_epd` folder.

### Launch Bjorn ###
```bash
sudo python3 Bjorn.py
```

### To get a fresh new start with Bjorn, go to the Bjorn root folder  and run this : ###
```bash
sudo rm -rf config/*.json && sudo rm -rf data/*.csv && sudo rm -rf data/*.log && sudo rm -rf data/output/data_stolen/* && sudo rm -rf data/output/crackedpwd/* && sudo rm -rf config/* && sudo rm -rf data/output/scan_results/* && sudo rm -rf __pycache__ && sudo rm -rf config/__pycache__ && sudo rm -rf data/__pycache__  && sudo rm -rf actions/__pycache__  && sudo rm -rf resources/__pycache__ && sudo rm -rf web/__pycache__  && sudo rm -rf *.log && sudo rm -rf resources/waveshare_epd/__pycache__ && sudo rm -rf data/logs/*  && sudo rm -rf data/output/vulnerabilities/* && sudo rm -rf data/logs/*
```
### Everything will be recreated automatically at the next launch : ###


####  IMPORTANT #### 
For now, as I am still working on the project, I have not yet created a service for Bjorn, so we need to keep the terminal open to keep Bjorn running. I need to debug and see logs to improve the code. Currently, I'm struggling with the following issues:

- When Bjorn is running for a long time:
    - OSError: [Errno 24] Too many open files (despite increasing the system limits)
- Creating a PAN0 Bluetooth network to share the Raspberry Pi connection with another device:
    - The discoverable option doesn't persist after a reboot; I need to make it permanent.
    - Bluetooth appears, but when trying to connect (iPhone, Android, MacBook), it fails, saying the device needs to be removed and reconnected (without success).

### If you still want to create a service to launch Bjorn at startup, along with a service for Bluetooth sharing and another for USB, here’s how to do it: ###

------------------------------------------------------------------------------------------------

### BJORN SERVICE ###

##### Create a systemd service for Bjorn #####
```bash
sudo vi /etc/systemd/system/bjorn.service
```

##### Paste the following content:
```ini
[Unit]
Description=Bjorn Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/bjorn/Bjorn/Bjorn.py
WorkingDirectory=/home/bjorn/Bjorn
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```

##### Make the file executable:
```bash
sudo chmod +x /home/bjorn/Bjorn/Bjorn.py
```

##### Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bjorn.service
sudo systemctl start bjorn.service
sudo systemctl stop bjorn.service
sudo systemctl status bjorn.service
```

##### If the service does not start correctly, you can check the logs for more details with the following command:
```bash
sudo journalctl -u bjorn.service
```

------------------------------------------------------------------------------------------------

### Bluetooth PAN0 to share the Raspberry Pi connection with another device by assigning a static IP address ###
```bash
sudo apt-get install bluez-tools
```

Create the file `/etc/systemd/network/pan0.netdev`:
```bash
sudo vi /etc/systemd/network/pan0.netdev
```

Add the following content:
```ini
[NetDev]
Name=pan0
Kind=bridge
```

Create the file `/etc/systemd/network/pan0.network`:
```bash
sudo vi /etc/systemd/network/pan0.network
```

Add the following content:
```ini
[Match]
Name=pan0

[Network]
Address=172.20.1.1/24
DHCPServer=yes
```

Create the file `/etc/systemd/system/bt-pan.service`:
```bash
sudo vi /etc/systemd/system/bt-pan.service
```

Add the following content:
```ini
[Unit]
Description=Bluetooth PAN Service
After=network.target

[Service]
ExecStartPre=-/usr/bin/ip link delete pan0 type bridge
ExecStartPre=/usr/bin/ip link add name pan0 type bridge
ExecStart=/usr/bin/bt-network -s nap pan0
ExecStartPost=/usr/bin/ip link set pan0 up
ExecStartPost=-/usr/sbin/ip addr add 172.20.1.1/24 dev pan0
ExecStartPost=/usr/local/bin/set_bluetooth_discoverable.sh
ExecStartPost=/usr/bin/bt-adapter --set Discoverable 1
Type=simple
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Modify the Bluetooth configuration:
```bash
sudo vi /etc/bluetooth/main.conf
```

Add the following line:
```ini
[General]
DisablePlugins = sap
```

Create the file `/usr/local/bin/set_bluetooth_discoverable.sh`:
```bash
sudo vi /usr/local/bin/set_bluetooth_discoverable.sh
```

Add the following content:
```bash
#!/bin/bash
/usr/bin/bt-adapter --set Discoverable 1
```

Make the script executable:
```bash
sudo chmod +x /usr/local/bin/set_bluetooth_discoverable.sh
```

Create the file `/etc/systemd/system/bt-discoverable.service`:
```bash
sudo vi /etc/systemd/system/bt-discoverable.service
```

Add the following content:
```ini
[Unit]
Description=Make Bluetooth Discoverable
After=bluetooth.target

[Service]
ExecStart=/usr/local/bin/set_bluetooth_discoverable.sh
Type=oneshot

[Install]
WantedBy=multi-user.target
```

Reload the systemd configuration:
```bash
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo systemctl status bluetooth
```

Enable and start the services:
```bash
sudo systemctl enable systemd-networkd
sudo systemctl enable bt-pan
sudo systemctl enable bt-discoverable

sudo systemctl start systemd-networkd
sudo systemctl start bt-pan
sudo systemctl start bt-discoverable
```

Check the status of the services:
```bash
sudo systemctl status bt-pan
sudo systemctl status bt-discoverable
```

Check the pan0 interface:
```bash
ip addr show pan0
```

Check the status of the service:
```bash
sudo journalctl -xeu bt-pan.service
```

Check the neighbors (devices connected via Bluetooth):
```bash
sudo ip neigh show dev pan0
```

------------------------------------------------------------------------------------------------

### USB Gadget (RNDIS) : Raspberry Pi Zero W (Raspberry Pi OS) to Windows PC ###

Modify the file `/boot/firmware/cmdline.txt`:
```bash
sudo vi /boot/firmware/cmdline.txt
```

Add the following line right after `rootwait`:
```bash
modules-load=dwc2,g_ether
```

Modify the file `/boot/firmware/config.txt`:
```bash
sudo vi /boot/firmware/config.txt
```

Add the following line at the end of the file:
```bash
dtoverlay=dwc2
```

Create a script to configure the USB gadget:
```bash
sudo vi /usr/local/bin/usb-gadget.sh
```

Add the following content:
```bash
#!/bin/bash
set -e

modprobe libcomposite
cd /sys/kernel/config/usb_gadget/
mkdir -p g1
cd g1

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "Pi Zero USB" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM network" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

mkdir -p functions/ecm.usb0

# Check for existing symlink and remove if necessary
if [ -L configs/c.1/ecm.usb0 ]; then
    rm configs/c.1/ecm.usb0
fi
ln -s functions/ecm.usb0 configs/c.1/

# Ensure the device is not busy before listing available USB device controllers
max_retries=

10
retry_count=0

while ! ls /sys/class/udc > UDC 2>/dev/null; do
    if [ $retry_count -ge $max_retries ]; then
        echo "Error: Device or resource busy after $max_retries attempts."
        exit 1
    fi
    retry_count=$((retry_count + 1))
    sleep 1
done

# Check if the usb0 interface is already configured
if ! ip addr show usb0 | grep -q "172.20.2.1"; then
    ifconfig usb0 172.20.2.1 netmask 255.255.255.0
else
    echo "Interface usb0 already configured."
fi
```

Make the script executable:
```bash
sudo chmod +x /usr/local/bin/usb-gadget.sh
```

Create a systemd service to run the script at startup:
```bash
sudo vi /etc/systemd/system/usb-gadget.service
```

Add the following content:
```ini
[Unit]
Description=USB Gadget Service
After=network.target

[Service]
ExecStartPre=/sbin/modprobe libcomposite
ExecStart=/usr/local/bin/usb-gadget.sh
Type=simple
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Configure usb0:
```bash
sudo vi /etc/network/interfaces
```

Add the following content:
```ini
allow-hotplug usb0
iface usb0 inet static
    address 172.20.2.1
    netmask 255.255.255.0
```

Reload the services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable systemd-networkd
sudo systemctl enable usb-gadget
sudo systemctl start systemd-networkd
sudo systemctl start usb-gadget
```

### Windows PC Configuration ###
Set the static IP address:
- IP Address: 172.20.2.2
- Subnet Mask: 255.255.255.0
- Default Gateway: 172.20.2.1
- DNS Servers: 8.8.8.8, 8.8.4.4

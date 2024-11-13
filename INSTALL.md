## 🔧 Installation and Configuration

<p align="center">
  <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="98">
</p>

## 📚 Table of Contents

- [Prerequisites](#-prerequisites)
- [Quick Install](#-quick-install)
- [Manual Install](#-manual-install)
- [License](#-license)

Use Raspberry Pi Imager to install your OS
https://www.raspberrypi.com/software/

### 📌 Prerequisites

![image](https://github.com/user-attachments/assets/e775f454-1771-4d6c-bff5-b262b3d98452)

- Raspberry Pi OS installed. 
    - Stable:
      - System: 32-bit
      - Kernel version: 6.6
      - Debian version: 12 (bookworm) '2024-10-22-raspios-bookworm-armhf-lite'
- Username and hostname set to `bjorn`.
- 2.13-inch e-Paper HAT connected to GPIO pins.

At the moment the paper screen v2 & v4 have been tested and implemented.
I juste hope the V1 & V3 will work the same.
 
### ⚡ Quick Install

The fastest way to install Bjorn is using the automatic installation script :

```bash
# Download and run the installer
wget https://raw.githubusercontent.com/infinition/Bjorn/refs/heads/main/install_bjorn.sh
sudo chmod +x install_bjorn.sh
sudo ./install_bjorn.sh
# Choose the choice 1 for automatic installation. It may take a while as a lot of packages and modules will be installed. You must reboot at the end.
```

### 🧰 Manual Install

#### Step 1: Activate SPI & I2C

```bash
sudo raspi-config
```

- Navigate to **"Interface Options"**.
- Enable **SPI**.
- Enable **I2C**.

#### Step 2: System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install required packages

 sudo apt install -y \
  libjpeg-dev \
  zlib1g-dev \
  libpng-dev \
  python3-dev \
  libffi-dev \
  libssl-dev \
  libgpiod-dev \
  libi2c-dev \
  libatlas-base-dev \
  build-essential \
  python3-pip \
  wget \
  lsof \
  git \
  libopenjp2-7 \
  nmap \
  libopenblas-dev \
  bluez-tools \
  bluez \
  dhcpcd5 \
  bridge-utils \
  python3-pil


# Update Nmap scripts database

sudo nmap --script-updatedb

```

#### Step 3: Bjorn Installation

```bash
# Clone the Bjorn repository
cd /home/bjorn
git clone https://github.com/infinition/Bjorn.git
cd Bjorn

# Install Python dependencies within the virtual environment
sudo pip install -r requirements.txt --break-system-packages
# As i did not succeed "for now" to get a stable installation with a virtual environment, i installed the dependencies system wide (with --break-system-packages), it did not cause any issue so far. You can try to install them in a virtual environment if you want.
```

##### 3.1: Configure E-Paper Display Type
Choose your e-Paper HAT version by modifying the configuration file:

1. Open the configuration file:
```bash
sudo vi /home/bjorn/Bjorn/config/shared_config.json
```
Press i to enter insert mode
Locate the line containing "epd_type":
Change the value according to your screen model:

- For 2.13 V1: "epd_type": "epd2in13",
- For 2.13 V2: "epd_type": "epd2in13_V2",
- For 2.13 V3: "epd_type": "epd2in13_V3",
- For 2.13 V4: "epd_type": "epd2in13_V4",

Press Esc to exit insert mode
Type :wq and press Enter to save and quit

#### Step 4: Configure File Descriptor Limits

To prevent `OSError: [Errno 24] Too many open files`, it's essential to increase the file descriptor limits.

##### 4.1: Modify File Descriptor Limits for All Users

Edit `/etc/security/limits.conf`:

```bash
sudo vi /etc/security/limits.conf
```

Add the following lines:

```
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
```

##### 4.2: Configure Systemd Limits

Edit `/etc/systemd/system.conf`:

```bash
sudo vi /etc/systemd/system.conf
```

Uncomment and modify:

```
DefaultLimitNOFILE=65535
```

Edit `/etc/systemd/user.conf`:

```bash
sudo vi /etc/systemd/user.conf
```

Uncomment and modify:

```
DefaultLimitNOFILE=65535
```

##### 4.3: Create or Modify `/etc/security/limits.d/90-nofile.conf`

```bash
sudo vi /etc/security/limits.d/90-nofile.conf
```

Add:

```
root soft nofile 65535
root hard nofile 65535
```

##### 4.4: Adjust the System-wide File Descriptor Limit

Edit `/etc/sysctl.conf`:

```bash
sudo vi /etc/sysctl.conf
```

Add:

```
fs.file-max = 2097152
```

Apply the changes:

```bash
sudo sysctl -p
```

#### Step 5: Reload Systemd and Apply Changes

Reload systemd to apply the new file descriptor limits:

```bash
sudo systemctl daemon-reload
```

#### Step 6: Modify PAM Configuration Files

PAM (Pluggable Authentication Modules) manages how limits are enforced for user sessions. To ensure that the new file descriptor limits are respected, update the following configuration files.

##### Step 6.1: Edit `/etc/pam.d/common-session` and `/etc/pam.d/common-session-noninteractive`

```bash
sudo vi /etc/pam.d/common-session
sudo vi /etc/pam.d/common-session-noninteractive
```

Add this line at the end of both files:

```
session required pam_limits.so
```

This ensures that the limits set in `/etc/security/limits.conf` are enforced for all user sessions.

#### Step 7: Configure Services

##### 7.1: Bjorn Service

Create the service file:

```bash
sudo vi /etc/systemd/system/bjorn.service
```

Add the following content:

```ini
[Unit]
Description=Bjorn Service
DefaultDependencies=no
Before=basic.target
After=local-fs.target

[Service]
ExecStartPre=/home/bjorn/Bjorn/kill_port_8000.sh
ExecStart=/usr/bin/python3 /home/bjorn/Bjorn/Bjorn.py
WorkingDirectory=/home/bjorn/Bjorn
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

# Check open files and restart if it reached the limit (ulimit -n buffer of 1000)
ExecStartPost=/bin/bash -c 'FILE_LIMIT=$(ulimit -n); THRESHOLD=$(( FILE_LIMIT - 1000 )); while :; do TOTAL_OPEN_FILES=$(lsof | wc -l); if [ "$TOTAL_OPEN_FILES" -ge "$THRESHOLD" ]; then echo "File descriptor threshold reached: $TOTAL_OPEN_FILES (threshold: $THRESHOLD). Restarting service."; systemctl restart bjorn.service; exit 0; fi; sleep 10; done &'

[Install]
WantedBy=multi-user.target
```



##### 7.2: Port 8000 Killer Script

Create the script to free up port 8000:

```bash
vi /home/bjorn/Bjorn/kill_port_8000.sh
```

Add:

```bash
#!/bin/bash
PORT=8000
PIDS=$(lsof -t -i:$PORT)

if [ -n "$PIDS" ]; then
    echo "Killing PIDs using port $PORT: $PIDS"
    kill -9 $PIDS
fi
```

Make the script executable:

```bash
chmod +x /home/bjorn/Bjorn/kill_port_8000.sh
```


##### 7.3: USB Gadget Configuration

Modify `/boot/firmware/cmdline.txt`:

```bash
sudo vi /boot/firmware/cmdline.txt
```

Add the following right after `rootwait`:

```
modules-load=dwc2,g_ether
```

Modify `/boot/firmware/config.txt`:

```bash
sudo vi /boot/firmware/config.txt
```

Add at the end of the file:

```
dtoverlay=dwc2
```

Create the USB gadget script:

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
max_retries=10
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

Create the systemd service:

```bash
sudo vi /etc/systemd/system/usb-gadget.service
```

Add:

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

Configure `usb0`:

```bash
sudo vi /etc/network/interfaces
```

Add:

```bash
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

You must reboot to be able to use it as a USB gadget (with ip)
###### Windows PC Configuration

Set the static IP address on your Windows PC:

- **IP Address**: `172.20.2.2`
- **Subnet Mask**: `255.255.255.0`
- **Default Gateway**: `172.20.2.1`
- **DNS Servers**: `8.8.8.8`, `8.8.4.4`

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

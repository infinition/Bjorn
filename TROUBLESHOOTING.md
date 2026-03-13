# 🐛 Known Issues and Troubleshooting

<p align="center">
  <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="98">
</p>

## 📚 Table of Contents

- [Current Development Issues](#-current-development-issues)
- [Troubleshooting Steps](#-troubleshooting-steps)
- [License](#-license)

## 🪲 Current Development Issues

### Long Runtime Issue

- **Problem**: `OSError: [Errno 24] Too many open files`
- **Status**: Partially resolved with system limits configuration.
- **Workaround**: Implemented file descriptor limits increase.
- **Monitoring**: Check open files with `lsof -p $(pgrep -f Bjorn.py) | wc -l`
- At the moment the logs show periodically this information as (FD : XXX)

## 🛠️ Troubleshooting Steps

### Service Issues

```bash
#See bjorn journalctl service
journalctl -fu bjorn.service

# Check service status
sudo systemctl status bjorn.service
sudo systemctl status bjorn-bluetooth.service
sudo systemctl status bjorn-connectivity.service

# View detailed logs
sudo journalctl -u bjorn.service -f
sudo journalctl -u bjorn-bluetooth.service -f
sudo journalctl -u bjorn-connectivity.service -f

or

sudo tail -f /home/bjorn/Bjorn/data/logs/*


# Check port 8000 usage
sudo lsof -i :8000
```

### Display Issues

```bash
# Verify SPI devices
ls /dev/spi*

# Check user permissions
sudo usermod -a -G spi,gpio bjorn
```

### Network Issues

```bash
# Check network interfaces
ip addr show

# Check NetworkManager state
nmcli general status
nmcli device status

# Check setup AP and Bluetooth PAN state
nmcli connection show --active
cat /home/bjorn/Bjorn/config/connectivity_state.json

# Test USB gadget interface
ip link show usb0
```

If `http://172.22.0.1:8000` will not load over Bluetooth PAN, turn off Wi-Fi and mobile data on the phone first. If that is still unreliable, use the `bjorn-setup` access point instead.

### Permission Issues

```bash
# Fix ownership
sudo chown -R bjorn:bjorn /home/bjorn/Bjorn

# Fix permissions
sudo chmod -R 755 /home/bjorn/Bjorn
```

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

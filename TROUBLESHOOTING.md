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

# View detailed logs
sudo journalctl -u bjorn.service -f

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

# Test USB gadget interface
ip link show usb0
```

### Orchestrator does not see Wi-Fi (non-English locale)

nmcli output is locale-dependent. Prefer keeping `en_GB.UTF-8` / `C.UTF-8`, or use a build that forces `LC_ALL=C` for nmcli checks. Ethernet-only setups are supported when a routable IPv4 exists on any interface.

### Unreadable Waveshare V4 / rotated panel

In `config/shared_config.json` you can override orientation:

```json
"screen_reversed": false,
"web_screen_reversed": false
```

### Web UI / manual attacks return 404

Ensure the service is serving the latest `web/` assets. Manual attack logs use `/get_logs` (alias `/recent_logs`).

### Port list cannot accept commas in Settings

`portlist` and other list fields must be text inputs (comma-separated). Save from the Settings toolbar after editing.

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

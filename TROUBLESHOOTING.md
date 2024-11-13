## Known Issues and Troubleshooting

### Current Development Issues

#### 1. Long Runtime Issue

- **Problem**: `OSError: [Errno 24] Too many open files`
- **Status**: Partially resolved with system limits configuration.
- **Workaround**: Implemented file descriptor limits increase.
- **Monitoring**: Check open files with `lsof -p $(pgrep -f Bjorn.py) | wc -l`
- At the moment the logs show periodically this information as (FD : XXX)

### Troubleshooting Steps

#### 1. Service Issues

```bash
# Check service status
sudo systemctl status bjorn.service

# View detailed logs
sudo journalctl -u bjorn.service -f

# Check port 8000 usage
sudo lsof -i :8000
```

#### 2. Display Issues

```bash
# Verify SPI devices
ls /dev/spi*

# Check user permissions
sudo usermod -a -G spi,gpio bjorn
```

#### 3. Network Issues

```bash
# Check network interfaces
ip addr show

# Test USB gadget interface
ip link show usb0
```

#### 4. Permission Issues

```bash
# Fix ownership
sudo chown -R bjorn:bjorn /home/bjorn/Bjorn

# Fix permissions
sudo chmod -R 755 /home/bjorn/Bjorn
```

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

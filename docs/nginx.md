# Bjorn — Nginx reverse proxy + TLS (guide)

This document shows a minimal, secure way to expose Bjorn's web UI to the internet using
an Nginx reverse proxy with Let's Encrypt TLS. The Bjorn built-in web server should be
bound to `127.0.0.1:8000` (local only) — this repository already sets that by default.

Replace `example.com` with your real domain name.

## Nginx server block
Create `/etc/nginx/sites-available/bjorn` with the following content:

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

Enable the site and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/bjorn /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Obtain TLS certificates (Certbot)
Install certbot and obtain a certificate using the Nginx plugin:

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

Follow prompts; certbot will modify the Nginx configuration and install certificates.

## Firewall
Allow only HTTP/HTTPS and SSH through the firewall, and ensure Bjorn's port is not publicly reachable:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
# If Bjorn is bound to 127.0.0.1 this is optional, otherwise explicitly deny:
sudo ufw deny 8000
```

## Bjorn configuration
- Ensure `shared_config.json` includes a strong `web_password` and `web_auth` set to `true`.
- The repository config already sets the web server to bind to `127.0.0.1` — recommended.

## Additional hardening
- Run Bjorn under a dedicated, unprivileged user (e.g., `bjorn`).
- Limit Nginx access by IP (if appropriate) with `allow`/`deny` directives.
- Monitor logs and set up automatic certificate renewal (certbot already creates a cron job/systemd timer).

```

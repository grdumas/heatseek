# HeatSeek Deployment Guide

This guide covers deploying the HeatSeek real-time coverage dashboard on a single server behind a corporate VPN.

## Architecture Overview

```
┌─────────────────┐
│   Engineers     │  (~12 concurrent users)
│   (Browsers)    │
└────────┬────────┘
         │ HTTPS
         ↓
┌─────────────────┐
│  Nginx/Apache   │  (Optional reverse proxy)
│  Reverse Proxy  │
└────────┬────────┘
         │ HTTP
         ↓
┌─────────────────┐
│  FastAPI Server │  (uvicorn, port 8080)
│  (server.py)    │  Cache: 30s TTL
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   OpenSearch    │  (Existing data source)
│   Cluster       │
└─────────────────┘
```

## Prerequisites

- Linux server (RHEL/Fedora/Ubuntu)
- Python 3.9+
- Network access to OpenSearch cluster
- (Optional) Nginx or Apache for HTTPS termination

## Installation

### 1. Create Application User

```bash
sudo useradd -r -s /bin/bash -d /opt/heatseek heatseek
sudo mkdir -p /opt/heatseek
sudo chown heatseek:heatseek /opt/heatseek
```

### 2. Clone Repository

```bash
sudo -u heatseek git clone https://github.com/your-org/heatseek.git /opt/heatseek
cd /opt/heatseek
```

### 3. Set Up Python Virtual Environment

```bash
sudo -u heatseek python3 -m venv venv
sudo -u heatseek venv/bin/pip install --upgrade pip
sudo -u heatseek venv/bin/pip install -r requirements.txt
```

### 4. Configure Environment Variables

Edit the systemd service file or create a `.env` file:

```bash
sudo -u heatseek nano /opt/heatseek/.env
```

Add:
```bash
OPENSEARCH_HOST=your-opensearch-host.com
OPENSEARCH_PORT=443
OPENSEARCH_USERNAME=readonly_user
OPENSEARCH_PASSWORD=your-password
OPENSEARCH_INDEX=zathras-results
```

**Security Note**: Ensure `.env` has restrictive permissions:
```bash
sudo chmod 600 /opt/heatseek/.env
sudo chown heatseek:heatseek /opt/heatseek/.env
```

### 5. Install Systemd Service

```bash
# Edit service file with your environment variables
sudo nano /opt/heatseek/heatseek.service

# Copy to systemd directory
sudo cp /opt/heatseek/heatseek.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable heatseek

# Start service
sudo systemctl start heatseek

# Check status
sudo systemctl status heatseek
```

### 6. Verify Service is Running

```bash
# Check service status
sudo systemctl status heatseek

# Check logs
sudo journalctl -u heatseek -f

# Test local connection
curl http://localhost:8080/health
```

Expected response:
```json
{"status":"healthy","timestamp":"2026-06-03T10:30:00.000000"}
```

## Option A: Direct Access (Development/Testing)

For quick testing without a reverse proxy:

```bash
# Allow port 8080 through firewall
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# Access dashboard
firefox http://server-ip:8080
```

## Option B: Nginx Reverse Proxy (Recommended)

### Install Nginx

```bash
# RHEL/Fedora
sudo dnf install nginx

# Ubuntu
sudo apt install nginx
```

### Configure Nginx

Create `/etc/nginx/conf.d/heatseek.conf`:

```nginx
server {
    listen 80;
    server_name heatseek.internal.company.com;

    # Redirect to HTTPS (optional but recommended)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name heatseek.internal.company.com;

    # SSL certificates (use your company's internal CA)
    ssl_certificate /etc/pki/tls/certs/heatseek.crt;
    ssl_certificate_key /etc/pki/tls/private/heatseek.key;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Logging
    access_log /var/log/nginx/heatseek-access.log;
    error_log /var/log/nginx/heatseek-error.log;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (future-proofing)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Enable and Start Nginx

```bash
# Test configuration
sudo nginx -t

# Enable on boot
sudo systemctl enable nginx

# Start/restart nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx
```

### Configure Firewall

```bash
# Allow HTTP and HTTPS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## Option C: Apache Reverse Proxy

### Install Apache

```bash
# RHEL/Fedora
sudo dnf install httpd mod_ssl

# Ubuntu
sudo apt install apache2
```

### Configure Apache

Create `/etc/httpd/conf.d/heatseek.conf`:

```apache
<VirtualHost *:443>
    ServerName heatseek.internal.company.com

    SSLEngine on
    SSLCertificateFile /etc/pki/tls/certs/heatseek.crt
    SSLCertificateKeyFile /etc/pki/tls/private/heatseek.key

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/

    ErrorLog /var/log/httpd/heatseek-error.log
    CustomLog /var/log/httpd/heatseek-access.log combined
</VirtualHost>

<VirtualHost *:80>
    ServerName heatseek.internal.company.com
    Redirect permanent / https://heatseek.internal.company.com/
</VirtualHost>
```

Enable required modules:

```bash
sudo a2enmod proxy proxy_http ssl
sudo systemctl restart httpd
```

## Monitoring and Maintenance

### View Logs

```bash
# Service logs
sudo journalctl -u heatseek -f

# Nginx logs (if using)
sudo tail -f /var/log/nginx/heatseek-access.log
sudo tail -f /var/log/nginx/heatseek-error.log
```

### Health Check

```bash
# Check API health
curl http://localhost:8080/health

# Check summary endpoint
curl http://localhost:8080/api/summary | jq
```

### Restart Service

```bash
sudo systemctl restart heatseek
```

### Update Application

```bash
cd /opt/heatseek
sudo -u heatseek git pull
sudo -u heatseek venv/bin/pip install -r requirements.txt
sudo systemctl restart heatseek
```

## Performance Tuning

### Adjust Worker Count

For ~12 concurrent users, 2 workers is sufficient. Edit `heatseek.service`:

```ini
ExecStart=/opt/heatseek/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8080 --workers 2
```

For higher load:
```bash
# Formula: (2 × CPU cores) + 1
ExecStart=/opt/heatseek/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8080 --workers 5
```

### Cache TTL Adjustment

Default cache TTL is 30 seconds. To adjust, edit `server.py`:

```python
def get_cache_key() -> str:
    """Round current time to 60-second buckets for cache invalidation"""
    now = datetime.now()
    bucket = now.replace(second=now.second // 60 * 60, microsecond=0)  # Changed to 60s
    return bucket.isoformat()
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status heatseek

# View detailed logs
sudo journalctl -u heatseek -n 50 --no-pager

# Common issues:
# 1. Missing dependencies
sudo -u heatseek /opt/heatseek/venv/bin/pip install -r /opt/heatseek/requirements.txt

# 2. Permission issues
sudo chown -R heatseek:heatseek /opt/heatseek

# 3. Port already in use
sudo lsof -i :8080
```

### OpenSearch Connection Errors

```bash
# Test connectivity
curl -u username:password https://opensearch-host:443/_cluster/health

# Verify credentials in service file
sudo systemctl cat heatseek
```

### Empty Dashboard / No Data

```bash
# Check API response
curl http://localhost:8080/api/coverage | jq

# Verify OpenSearch index
curl -u user:pass https://host:443/zathras-results/_count

# Check logs for query errors
sudo journalctl -u heatseek | grep ERROR
```

### High Memory Usage

```bash
# Check memory usage
ps aux | grep uvicorn

# Reduce worker count in heatseek.service
ExecStart=... --workers 1

# Restart service
sudo systemctl restart heatseek
```

## Security Considerations

1. **Use read-only OpenSearch credentials** - The dashboard only needs read access
2. **Restrict network access** - Use firewall rules to limit access to VPN IPs only
3. **Enable HTTPS** - Use company SSL certificates for encrypted communication
4. **Secure .env file** - Set permissions to 600 and owned by service user
5. **Regular updates** - Keep dependencies updated for security patches

## Backup and Disaster Recovery

The application is stateless - all data comes from OpenSearch. To backup configuration:

```bash
# Backup configuration
sudo tar -czf heatseek-config-backup.tar.gz \
    /opt/heatseek/.env \
    /etc/systemd/system/heatseek.service \
    /etc/nginx/conf.d/heatseek.conf

# Restore
sudo tar -xzf heatseek-config-backup.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl restart heatseek nginx
```

## Scaling Beyond 12 Users

If usage grows beyond 12 concurrent users:

1. **Increase worker count** - Use formula: (2 × CPU cores) + 1
2. **Add second server** - Use load balancer to distribute traffic
3. **Implement Redis caching** - Replace in-memory LRU cache with Redis for shared cache across servers
4. **Use CDN** - Serve static frontend assets via CDN

For most internal tools with ~12 users, the single-server setup is sufficient.

## Support

For issues:
1. Check logs: `sudo journalctl -u heatseek -f`
2. Verify OpenSearch connectivity
3. Test API endpoints directly: `curl http://localhost:8080/api/summary`
4. Contact Performance QA team

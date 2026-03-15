# Alive App Deployment Guide

## Prerequisites

- Ubuntu 24.04 VM with 8 cores
- MySQL 8.0+
- Python 3.12+

## 1. Deploy Application

```bash
# Clone/upload code to server
sudo mkdir -p /opt/alive-api
sudo chown ubuntu:ubuntu /opt/alive-api
# Copy files to /opt/alive-api

# Create virtual environment
cd /opt/alive-api
python3 -m venv alive_venv
source alive_venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env  # Edit with your values
```

## 2. Run Database Migration

```bash
mysql -u root -p < app/db/database.sql
mysql -u root -p alive_app < app/db/migrations/001_trigger_notifications.sql
```

## 3. Install Systemd Services

```bash
# Copy service files
sudo cp deploy/systemd/alive-api.service /etc/systemd/system/
sudo cp deploy/systemd/alive-trigger.service /etc/systemd/system/
sudo cp deploy/systemd/alive-trigger.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start API
sudo systemctl enable alive-api
sudo systemctl start alive-api

# Enable and start trigger timer
sudo systemctl enable alive-trigger.timer
sudo systemctl start alive-trigger.timer
```

## 4. Verify Services

```bash
# Check API status
sudo systemctl status alive-api
curl http://localhost:8000/health

# Check timer status
sudo systemctl status alive-trigger.timer
sudo systemctl list-timers | grep alive

# View logs
journalctl -u alive-api.service -f
journalctl -u alive-trigger.service -f
```

## 5. Manual Worker Test

```bash
cd /opt/alive-api
source alive_venv/bin/activate
python -m app.worker.trigger_worker
```

## CPU Quota Explanation

The `CPUQuota` setting in systemd:
- **100% = 1 CPU core**
- On an 8-core VM:
  - `CPUQuota=400%` = 4 cores = 50% of total VM capacity
  - `CPUQuota=100%` = 1 core = 12.5% of total VM capacity
  - `CPUQuota=50%` = 0.5 cores = 6.25% of total VM capacity

Current config uses `CPUQuota=400%` (50% of 8-core VM).

## Useful Commands

```bash
# Restart services
sudo systemctl restart alive-api
sudo systemctl restart alive-trigger.timer

# Stop timer (disable automatic checks)
sudo systemctl stop alive-trigger.timer

# Run worker manually once
sudo systemctl start alive-trigger.service

# View recent trigger worker runs
journalctl -u alive-trigger.service --since "1 hour ago"

# Check MySQL connection
mysql -u alive_api -p alive_app -e "SELECT COUNT(*) FROM users;"
```

## Troubleshooting

### Worker not sending emails
1. Check `.env` has correct SMTP settings
2. Set `EMAIL_USE_CONSOLE=true` to test without sending
3. Check logs: `journalctl -u alive-trigger.service -n 50`

### Timer not running
1. Check timer is enabled: `systemctl is-enabled alive-trigger.timer`
2. Check timer status: `systemctl status alive-trigger.timer`
3. List timers: `systemctl list-timers --all`

### API not starting
1. Check logs: `journalctl -u alive-api.service -n 50`
2. Test manually: `cd /opt/alive-api && source alive_venv/bin/activate && uvicorn app.main:app`

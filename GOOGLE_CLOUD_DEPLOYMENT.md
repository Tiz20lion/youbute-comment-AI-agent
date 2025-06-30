# 🚀 Google Cloud Platform Deployment Guide

## Overview

This guide provides detailed instructions for deploying the YouTube Comment AI Agent on Google Cloud Platform (GCP) using the enhanced VPS deployment script.

## 🔧 Prerequisites

### 1. Google Cloud Account
- Active Google Cloud account with billing enabled
- Project created in Google Cloud Console
- Compute Engine API enabled

### 2. Local Requirements
- `gcloud` CLI installed and configured
- SSH access to your instance
- Domain name (optional, for SSL)

## 📋 Quick Deployment

### Option 1: One-Command Deployment (Basic)
```bash
curl -fsSL https://raw.githubusercontent.com/Tiz20lion/youtube-comment-AI-agent/main/deploy-vps-gcp.sh | bash
```

### Option 2: One-Command Deployment (With SSL)
```bash
curl -fsSL https://raw.githubusercontent.com/Tiz20lion/youtube-comment-AI-agent/main/deploy-vps-gcp.sh | bash -s -- --ssl --domain yourdomain.com --email your@email.com
```

## 🏗️ Step-by-Step Deployment

### Step 1: Create a Compute Engine Instance

#### Using Google Cloud Console:
1. Go to **Compute Engine** > **VM instances**
2. Click **Create Instance**
3. Configure your instance:
   - **Name**: `tiz-lion-ai-agent`
   - **Region**: Choose your preferred region
   - **Machine type**: `e2-medium` (2 vCPU, 4 GB memory) or higher
   - **Boot disk**: Ubuntu 22.04 LTS
   - **Disk size**: 20 GB minimum (recommended: 50 GB)
   - **Firewall**: Allow HTTP and HTTPS traffic

#### Using gcloud CLI:
```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Create the instance
gcloud compute instances create tiz-lion-ai-agent \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --subnet=default \
    --network-tier=PREMIUM \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --tags=http-server,https-server \
    --create-disk=auto-delete=yes,boot=yes,device-name=tiz-lion-ai-agent,image=projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts,mode=rw,size=50,type=projects/$PROJECT_ID/zones/us-central1-a/diskTypes/pd-standard \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --reservation-affinity=any
```

### Step 2: Configure Firewall Rules

```bash
# Allow HTTP traffic
gcloud compute firewall-rules create allow-http-tiz-lion \
    --allow tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTP for Tiz Lion AI Agent"

# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https-tiz-lion \
    --allow tcp:443 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTPS for Tiz Lion AI Agent"

# Allow custom port (if needed)
gcloud compute firewall-rules create allow-custom-port-tiz-lion \
    --allow tcp:7844 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow custom port for Tiz Lion AI Agent"
```

### Step 3: Connect to Your Instance

```bash
gcloud compute ssh tiz-lion-ai-agent --zone=us-central1-a
```

### Step 4: Run the Deployment Script

#### Basic Deployment:
```bash
# Download and run the deployment script
curl -fsSL https://raw.githubusercontent.com/Tiz20lion/youtube-comment-AI-agent/main/deploy-vps-gcp.sh -o deploy-vps-gcp.sh
chmod +x deploy-vps-gcp.sh
sudo ./deploy-vps-gcp.sh
```

#### Advanced Deployment with SSL:
```bash
# Deploy with SSL certificate
sudo ./deploy-vps-gcp.sh --ssl --domain yourdomain.com --email your@email.com
```

#### All Available Options:
```bash
sudo ./deploy-vps-gcp.sh \
    --ssl \
    --domain yourdomain.com \
    --email your@email.com \
    --port 7844 \
    --no-monitoring \
    --no-backup
```

## 🌐 Domain Configuration (Optional)

### Step 1: Reserve a Static IP
```bash
gcloud compute addresses create tiz-lion-ai-agent-ip \
    --region=us-central1

# Get the IP address
gcloud compute addresses describe tiz-lion-ai-agent-ip \
    --region=us-central1 \
    --format="get(address)"
```

### Step 2: Assign Static IP to Instance
```bash
gcloud compute instances delete-access-config tiz-lion-ai-agent \
    --access-config-name="External NAT" \
    --zone=us-central1-a

gcloud compute instances add-access-config tiz-lion-ai-agent \
    --access-config-name="External NAT" \
    --address=tiz-lion-ai-agent-ip \
    --zone=us-central1-a
```

### Step 3: Configure DNS
Point your domain's A record to the static IP address you reserved.

## 🔒 Security Configuration

### Default Security Features
The deployment script automatically configures:
- UFW firewall with minimal open ports
- Fail2ban for intrusion detection
- Nginx with security headers
- SSL/TLS with Let's Encrypt (if domain provided)
- Rate limiting on API endpoints

### Additional Security Recommendations

#### 1. Change SSH Port (Optional)
```bash
sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Update firewall
sudo ufw allow 2222/tcp
sudo ufw deny 22/tcp
```

#### 2. Set up SSH Key Authentication
```bash
# On your local machine
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Copy public key to server
gcloud compute scp ~/.ssh/id_rsa.pub tiz-lion-ai-agent:~/.ssh/authorized_keys --zone=us-central1-a
```

#### 3. Disable Password Authentication
```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## 📊 Monitoring and Maintenance

### Built-in Monitoring
- **Health Checks**: Every 5 minutes via cron
- **Log Rotation**: Daily with 30-day retention
- **Automatic Backups**: Daily at 2:00 AM
- **SSL Renewal**: Automatic via certbot

### Google Cloud Monitoring (Optional)

#### Install Monitoring Agent:
```bash
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

#### Configure Uptime Checks:
1. Go to **Monitoring** > **Uptime checks** in Google Cloud Console
2. Create uptime check for your domain/IP
3. Set alert policies for notifications

### Management Commands

```bash
# Service management
tiz-lion-control start       # Start the service
tiz-lion-control stop        # Stop the service
tiz-lion-control restart     # Restart the service
tiz-lion-control status      # Show detailed status
tiz-lion-control logs        # View live logs
tiz-lion-control health      # Run health check
tiz-lion-control update      # Update from GitHub
tiz-lion-control backup      # Create manual backup

# Configuration
tiz-lion-startup             # Interactive configuration
ai-agent                     # Quick access to startup
nano /opt/youtube-comment-ai-agent/.env  # Edit config manually
```

## 🔧 Configuration

### Environment Variables
Edit `/opt/youtube-comment-ai-agent/.env`:

```env
# Server Configuration
PORT="7844"
HOST="0.0.0.0"

# YouTube API (Required)
YOUTUBE_API_KEY="your_youtube_api_key"
GOOGLE_API_KEY="your_google_api_key"

# OpenRouter AI API (Required)
OPENROUTER_API_KEY="your_openrouter_api_key"

# OAuth2 for Comment Posting (Optional)
GOOGLE_CLIENT_ID="your_oauth2_client_id"
GOOGLE_CLIENT_SECRET="your_oauth2_client_secret"
OAUTH2_REDIRECT_URI="http://yourdomain.com/auth/callback"

# Telegram Integration (Optional)
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Google Cloud Platform (Auto-configured)
GCP_PROJECT_ID="your-project-id"
GCP_ZONE="us-central1-a"
GCP_INSTANCE_NAME="tiz-lion-ai-agent"

# Comment Settings
ENABLE_COMMENT_POSTING="false"
COMMENT_MAX_LENGTH="500"
COMMENT_MIN_LENGTH="10"
COMMENT_POST_DELAY="30"

# Agent Settings
CHANNEL_PARSER_MAX_VIDEOS="10"
MAX_COMMENTS_PER_VIDEO="20"
PROCESSING_DELAY="2"
```

## 🚀 Optimization for Google Cloud

### Performance Tuning

#### 1. Use SSD Persistent Disks
```bash
# Create SSD disk
gcloud compute disks create tiz-lion-ssd-disk \
    --size=50GB \
    --type=pd-ssd \
    --zone=us-central1-a

# Attach to instance
gcloud compute instances attach-disk tiz-lion-ai-agent \
    --disk=tiz-lion-ssd-disk \
    --zone=us-central1-a
```

#### 2. Enable Google Cloud CDN (for static assets)
```bash
# Create load balancer with CDN
gcloud compute backend-services create tiz-lion-backend \
    --protocol=HTTP \
    --port-name=http \
    --health-checks=tiz-lion-health-check \
    --global \
    --enable-cdn
```

#### 3. Set up Auto-scaling (Advanced)
```bash
# Create instance template
gcloud compute instance-templates create tiz-lion-template \
    --machine-type=e2-medium \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --tags=http-server,https-server

# Create managed instance group
gcloud compute instance-groups managed create tiz-lion-group \
    --template=tiz-lion-template \
    --size=1 \
    --zone=us-central1-a
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check service status
systemctl status tiz-lion-ai-agent

# Check logs
journalctl -u tiz-lion-ai-agent -f

# Check port conflicts
netstat -tuln | grep 7844
```

#### 2. SSL Certificate Issues
```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew --dry-run

# Check nginx configuration
sudo nginx -t
```

#### 3. Firewall Issues
```bash
# Check UFW status
sudo ufw status

# Check Google Cloud firewall rules
gcloud compute firewall-rules list
```

#### 4. Memory Issues
```bash
# Check memory usage
free -h

# Upgrade instance type
gcloud compute instances set-machine-type tiz-lion-ai-agent \
    --machine-type=e2-standard-2 \
    --zone=us-central1-a
```

### Log Locations
- Application logs: `/var/log/tiz-lion-ai-agent/`
- Nginx logs: `/var/log/nginx/`
- System logs: `journalctl -u tiz-lion-ai-agent`

## 💰 Cost Optimization

### Recommended Instance Types
- **Development**: `e2-micro` (0.25 vCPU, 1 GB) - ~$7/month
- **Small Production**: `e2-small` (0.5 vCPU, 2 GB) - ~$14/month
- **Standard Production**: `e2-medium` (1 vCPU, 4 GB) - ~$28/month
- **High Traffic**: `e2-standard-2` (2 vCPU, 8 GB) - ~$56/month

### Cost-Saving Tips
1. Use preemptible instances for development
2. Set up committed use discounts for production
3. Use sustained use discounts automatically applied
4. Monitor usage with Cloud Billing budgets
5. Use Cloud Scheduler to start/stop instances automatically

## 📞 Support

### Getting Help
- **GitHub Issues**: [Create an issue](https://github.com/Tiz20lion/youtube-comment-AI-agent/issues)
- **Documentation**: [API Documentation](./API_DOCUMENTATION.md)
- **Logs**: Check `/var/log/tiz-lion-ai-agent/` for detailed logs

### Health Checks
```bash
# Manual health check
curl http://your-domain.com/health

# Service status
tiz-lion-control status

# View metrics
tiz-lion-control logs
```

---

**Note**: This deployment script is specifically optimized for Google Cloud Platform but can work on any Ubuntu-based VPS with minimal modifications. 
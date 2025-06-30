#!/bin/bash

# ====================================================================
# 🚀 Tiz Lion AI Agent - Google Cloud VPS Deployment Script 🚀
# ====================================================================
# Project: YouTube Comment AI Agent
# GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent
# Author: Tiz Lion
# Version: 2.1.0 - Google Cloud Edition
# ====================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
DEFAULT_PORT=7844
FALLBACK_PORT=7845
SERVICE_NAME="tiz-lion-ai-agent"
APP_DIR="/opt/youtube-comment-ai-agent"
STARTUP_SCRIPT="/usr/local/bin/tiz-lion-startup"
LOG_DIR="/var/log/tiz-lion-ai-agent"
BACKUP_DIR="/opt/tiz-lion-backups"
VENV_DIR="$APP_DIR/venv"

# Google Cloud specific settings
GC_INSTANCE_METADATA_URL="http://metadata.google.internal/computeMetadata/v1"
GC_PROJECT_ID=""
GC_ZONE=""
GC_INSTANCE_NAME=""

# SSL/TLS Configuration
ENABLE_SSL=${ENABLE_SSL:-false}
DOMAIN_NAME=${DOMAIN_NAME:-""}
EMAIL=${EMAIL:-""}

# Performance and monitoring
MONITORING_ENABLED=${MONITORING_ENABLED:-true}
AUTO_BACKUP_ENABLED=${AUTO_BACKUP_ENABLED:-true}
HEALTH_CHECK_ENABLED=${HEALTH_CHECK_ENABLED:-true}

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

print_header() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                              ║"
    echo "║                    🦁 TIZ LION AI AGENT VPS DEPLOY 🦁                       ║"
    echo "║                      Google Cloud Platform Edition                          ║"
    echo "║                                                                              ║"
    echo "║                      🤖 YouTube Comment Automation 🤖                       ║"
    echo "║                                                                              ║"
    echo "║               🔗 GitHub: github.com/Tiz20lion/youtube-comment-AI-agent      ║"
    echo "║                                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

detect_google_cloud() {
    log "Detecting Google Cloud Platform environment..."
    
    # Check if running on Google Cloud
    if curl -s -H "Metadata-Flavor: Google" "$GC_INSTANCE_METADATA_URL/instance/" &>/dev/null; then
        info "✅ Google Cloud Platform detected"
        
        # Get instance metadata
        GC_PROJECT_ID=$(curl -s -H "Metadata-Flavor: Google" "$GC_INSTANCE_METADATA_URL/project/project-id" 2>/dev/null || echo "unknown")
        GC_ZONE=$(curl -s -H "Metadata-Flavor: Google" "$GC_INSTANCE_METADATA_URL/instance/zone" 2>/dev/null | cut -d'/' -f4 || echo "unknown")
        GC_INSTANCE_NAME=$(curl -s -H "Metadata-Flavor: Google" "$GC_INSTANCE_METADATA_URL/instance/name" 2>/dev/null || echo "unknown")
        
        info "Project ID: $GC_PROJECT_ID"
        info "Zone: $GC_ZONE"
        info "Instance: $GC_INSTANCE_NAME"
        
        return 0
    else
        warn "Not running on Google Cloud Platform"
        return 1
    fi
}

check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":${port} "; then
        warn "Port ${port} is in use, trying fallback port ${FALLBACK_PORT}..."
        if netstat -tuln 2>/dev/null | grep -q ":${FALLBACK_PORT} "; then
            error "Both primary and fallback ports are in use. Please specify a different port."
            exit 1
        fi
        DEFAULT_PORT=$FALLBACK_PORT
    fi
    info "Using port: $DEFAULT_PORT"
}

install_system_deps() {
    log "Installing system dependencies..."
    
    # Update package list
    sudo apt update -y
    
    # Install essential packages
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        nginx \
        supervisor \
        ufw \
        fail2ban \
        htop \
        tree \
        unzip \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        jq \
        certbot \
        python3-certbot-nginx \
        redis-server \
        logrotate
    
    # Install Google Cloud SDK (if not already installed)
    if ! command -v gcloud &> /dev/null; then
        log "Installing Google Cloud SDK..."
        echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
        curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
        sudo apt update -y
        sudo apt install -y google-cloud-sdk
    fi
    
    # Install Node.js for potential frontend dependencies
    if ! command -v node &> /dev/null; then
        log "Installing Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
    
    success "System dependencies installed successfully"
}

create_directories() {
    log "Creating application directories..."
    
    # Create main directories
    sudo mkdir -p "$APP_DIR"
    sudo mkdir -p "$LOG_DIR"
    sudo mkdir -p "$BACKUP_DIR"
    sudo mkdir -p "/etc/tiz-lion-ai-agent"
    
    # Set proper permissions
    sudo chown -R $USER:$USER "$APP_DIR" 2>/dev/null || true
    sudo chown -R $USER:$USER "$LOG_DIR" 2>/dev/null || true
    sudo chown -R $USER:$USER "$BACKUP_DIR" 2>/dev/null || true
    
    success "Directories created successfully"
}

setup_app() {
    log "Setting up application..."
    
    cd "$APP_DIR"
    
    # Clone or update repository
    if [ -d "$APP_DIR/.git" ]; then
        log "Updating existing repository..."
        sudo git fetch origin
        sudo git reset --hard origin/main
        sudo git clean -fd
    else
        log "Cloning repository..."
        sudo git clone https://github.com/Tiz20lion/youtube-comment-AI-agent.git "$APP_DIR"
        cd "$APP_DIR"
    fi
    
    # Create and activate virtual environment
    log "Setting up Python virtual environment..."
    sudo python3 -m venv "$VENV_DIR"
    
    # Upgrade pip and install requirements
    sudo "$VENV_DIR/bin/pip" install --upgrade pip wheel setuptools
    sudo "$VENV_DIR/bin/pip" install -r requirements.txt
    
    # Install additional production dependencies
    sudo "$VENV_DIR/bin/pip" install \
        gunicorn \
        redis \
        psutil \
        python-multipart \
        prometheus-client
    
    # Set proper permissions
    sudo chown -R $USER:$USER "$APP_DIR"
    sudo chmod +x "$APP_DIR/startup.py"
    
    # Setup environment file if it doesn't exist
    if [ ! -f .env ]; then
        sudo cp example.env .env
        sudo sed -i "s/PORT=\"8080\"/PORT=\"$DEFAULT_PORT\"/" .env
        
        # Add Google Cloud specific settings
        if [ "$GC_PROJECT_ID" != "unknown" ] && [ "$GC_PROJECT_ID" != "" ]; then
            echo "" >> .env
            echo "# Google Cloud Platform Settings" >> .env
            echo "GCP_PROJECT_ID=\"$GC_PROJECT_ID\"" >> .env
            echo "GCP_ZONE=\"$GC_ZONE\"" >> .env
            echo "GCP_INSTANCE_NAME=\"$GC_INSTANCE_NAME\"" >> .env
        fi
        
        warn "Please configure your environment variables in $APP_DIR/.env"
    fi
    
    success "Application setup completed"
}

create_startup_commands() {
    log "Creating startup commands..."
    
    # Create main startup script
    sudo tee "$STARTUP_SCRIPT" > /dev/null <<EOF
#!/bin/bash
# Tiz Lion AI Agent Startup Script
cd "$APP_DIR"
"$VENV_DIR/bin/python" "$APP_DIR/startup.py" "\$@"
EOF

    sudo chmod +x "$STARTUP_SCRIPT"
    
    # Create shortcut command
    sudo tee "/usr/local/bin/ai-agent" > /dev/null <<EOF
#!/bin/bash
# Tiz Lion AI Agent Quick Access
cd "$APP_DIR"
"$VENV_DIR/bin/python" "$APP_DIR/startup.py" "\$@"
EOF

    sudo chmod +x "/usr/local/bin/ai-agent"
    
    success "Startup commands created"
}

create_systemd_service() {
    log "Creating systemd service..."
    
    sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Tiz Lion AI Agent - YouTube Comment Automation
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $DEFAULT_PORT
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tiz-lion-ai-agent

# Security settings
NoNewPrivileges=true
LimitNOFILE=65536
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR $LOG_DIR /tmp
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    
    success "Systemd service created and enabled"
}

setup_nginx_with_ssl() {
    log "Configuring nginx with SSL support..."
    
    # Remove default site
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Create nginx configuration
    sudo tee "/etc/nginx/sites-available/$SERVICE_NAME" > /dev/null <<EOF
# Tiz Lion AI Agent - Nginx Configuration
upstream ai_agent_backend {
    server 127.0.0.1:$DEFAULT_PORT;
    keepalive 32;
}

# Rate limiting
limit_req_zone \$binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone \$binary_remote_addr zone=conn_limit:10m;

# HTTP Server (redirects to HTTPS if SSL enabled)
server {
    listen 80;
    server_name $(if [ "$DOMAIN_NAME" != "" ]; then echo "$DOMAIN_NAME"; else echo "_"; fi);
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Health check endpoint
    location /health {
        proxy_pass http://ai_agent_backend/health;
        access_log off;
    }
    
$(if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ]; then
cat << 'INNER_EOF'
    # Redirect HTTP to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
INNER_EOF
else
cat << 'INNER_EOF'
    # Main application
    location / {
        proxy_pass http://ai_agent_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
    }
    
    # WebSocket support
    location /ws {
        proxy_pass http://ai_agent_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
INNER_EOF
fi)
}

$(if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ]; then
cat << 'OUTER_EOF'
# HTTPS Server
server {
    listen 443 ssl http2;
    server_name DOMAIN_NAME;
    
    # SSL Configuration (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_NAME/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # Main application
    location / {
        proxy_pass http://ai_agent_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
    }
    
    # WebSocket support
    location /ws {
        proxy_pass http://ai_agent_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://ai_agent_backend/health;
        access_log off;
    }
}
OUTER_EOF
fi)
EOF

    # Replace domain placeholders if SSL is enabled
    if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ]; then
        sudo sed -i "s/DOMAIN_NAME/$DOMAIN_NAME/g" "/etc/nginx/sites-available/$SERVICE_NAME"
    fi
    
    # Enable site
    sudo ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/"
    
    # Test nginx configuration
    if sudo nginx -t; then
        sudo systemctl restart nginx
        success "Nginx configured successfully"
    else
        error "Nginx configuration test failed"
        exit 1
    fi
}

setup_ssl_certificate() {
    if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ] && [ "$EMAIL" != "" ]; then
        log "Setting up SSL certificate with Let's Encrypt..."
        
        # Install certbot if not already installed
        sudo apt install -y certbot python3-certbot-nginx
        
        # Obtain SSL certificate
        sudo certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --email "$EMAIL" --redirect
        
        # Setup auto-renewal
        sudo systemctl enable certbot.timer
        sudo systemctl start certbot.timer
        
        success "SSL certificate configured successfully"
    else
        info "SSL not configured (requires ENABLE_SSL=true, DOMAIN_NAME, and EMAIL)"
    fi
}

configure_firewall() {
    log "Configuring firewall..."
    
    # Reset UFW to defaults
    sudo ufw --force reset
    
    # Set default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow essential services
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow "$DEFAULT_PORT/tcp"
    
    # Allow Google Cloud specific ports if needed
    if [ "$GC_PROJECT_ID" != "unknown" ] && [ "$GC_PROJECT_ID" != "" ]; then
        # Allow health checks from Google Cloud load balancers
        sudo ufw allow from 35.191.0.0/16 to any port 80
        sudo ufw allow from 130.211.0.0/22 to any port 80
    fi
    
    # Enable firewall
    sudo ufw --force enable
    
    success "Firewall configured successfully"
}

setup_fail2ban() {
    log "Configuring fail2ban for security..."
    
    # Create nginx jail configuration
    sudo tee "/etc/fail2ban/jail.d/nginx.conf" > /dev/null <<EOF
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-noscript]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 6

[nginx-badbots]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-noproxy]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
EOF
    
    sudo systemctl enable fail2ban
    sudo systemctl restart fail2ban
    
    success "Fail2ban configured successfully"
}

setup_monitoring() {
    if [ "$MONITORING_ENABLED" = "true" ]; then
        log "Setting up monitoring and health checks..."
        
        # Create health check script
        sudo tee "/usr/local/bin/tiz-lion-health-check" > /dev/null <<EOF
#!/bin/bash
# Tiz Lion AI Agent Health Check Script

HEALTH_URL="http://localhost:$DEFAULT_PORT/health"
LOG_FILE="$LOG_DIR/health-check.log"

# Check if service is running
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "\$(date): Service is not running" >> "\$LOG_FILE"
    exit 1
fi

# Check HTTP health endpoint
if curl -f -s "\$HEALTH_URL" > /dev/null; then
    echo "\$(date): Health check passed" >> "\$LOG_FILE"
    exit 0
else
    echo "\$(date): Health check failed" >> "\$LOG_FILE"
    exit 1
fi
EOF
        
        sudo chmod +x "/usr/local/bin/tiz-lion-health-check"
        
        # Create monitoring cron job
        echo "*/5 * * * * root /usr/local/bin/tiz-lion-health-check" | sudo tee -a /etc/crontab
        
        success "Monitoring configured successfully"
    fi
}

setup_backups() {
    if [ "$AUTO_BACKUP_ENABLED" = "true" ]; then
        log "Setting up automatic backups..."
        
        # Create backup script
        sudo tee "/usr/local/bin/tiz-lion-backup" > /dev/null <<EOF
#!/bin/bash
# Tiz Lion AI Agent Backup Script

BACKUP_DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/tiz-lion-backup-\$BACKUP_DATE.tar.gz"

# Create backup
tar -czf "\$BACKUP_FILE" -C "$APP_DIR" . --exclude=venv --exclude=.git

# Keep only last 7 backups
find "$BACKUP_DIR" -name "tiz-lion-backup-*.tar.gz" -type f -mtime +7 -delete

echo "\$(date): Backup created: \$BACKUP_FILE" >> "$LOG_DIR/backup.log"
EOF
        
        sudo chmod +x "/usr/local/bin/tiz-lion-backup"
        
        # Create daily backup cron job
        echo "0 2 * * * root /usr/local/bin/tiz-lion-backup" | sudo tee -a /etc/crontab
        
        success "Backup system configured successfully"
    fi
}

setup_log_rotation() {
    log "Setting up log rotation..."
    
    sudo tee "/etc/logrotate.d/tiz-lion-ai-agent" > /dev/null <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    postrotate
        systemctl reload nginx > /dev/null 2>&1 || true
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF
    
    success "Log rotation configured successfully"
}

create_management_script() {
    log "Creating management script..."
    
    sudo tee "/usr/local/bin/tiz-lion-control" > /dev/null <<EOF
#!/bin/bash
# Tiz Lion AI Agent Control Script

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SERVICE_NAME="$SERVICE_NAME"
APP_DIR="$APP_DIR"
LOG_DIR="$LOG_DIR"

show_status() {
    echo -e "\${CYAN}=== Tiz Lion AI Agent Status ===\${NC}"
    echo
    
    # Service status
    if systemctl is-active --quiet \$SERVICE_NAME; then
        echo -e "\${GREEN}✅ Service: Running\${NC}"
    else
        echo -e "\${RED}❌ Service: Stopped\${NC}"
    fi
    
    # Nginx status
    if systemctl is-active --quiet nginx; then
        echo -e "\${GREEN}✅ Nginx: Running\${NC}"
    else
        echo -e "\${RED}❌ Nginx: Stopped\${NC}"
    fi
    
    # Port check
    if netstat -tuln | grep -q ":$DEFAULT_PORT "; then
        echo -e "\${GREEN}✅ Port $DEFAULT_PORT: Open\${NC}"
    else
        echo -e "\${RED}❌ Port $DEFAULT_PORT: Closed\${NC}"
    fi
    
    # Disk usage
    echo -e "\${BLUE}💾 Disk Usage:\${NC}"
    df -h \$APP_DIR | tail -1
    
    # Memory usage
    echo -e "\${BLUE}🧠 Memory Usage:\${NC}"
    free -h | head -2
    
    echo
}

case "\$1" in
    start)
        echo -e "\${GREEN}Starting Tiz Lion AI Agent...\${NC}"
        sudo systemctl start \$SERVICE_NAME
        sudo systemctl start nginx
        ;;
    stop)
        echo -e "\${YELLOW}Stopping Tiz Lion AI Agent...\${NC}"
        sudo systemctl stop \$SERVICE_NAME
        ;;
    restart)
        echo -e "\${BLUE}Restarting Tiz Lion AI Agent...\${NC}"
        sudo systemctl restart \$SERVICE_NAME
        sudo systemctl reload nginx
        ;;
    status)
        show_status
        ;;
    logs)
        echo -e "\${CYAN}Showing live logs (Ctrl+C to exit)...\${NC}"
        sudo journalctl -u \$SERVICE_NAME -f
        ;;
    nginx-logs)
        echo -e "\${CYAN}Showing nginx logs...\${NC}"
        sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
        ;;
    config)
        echo -e "\${CYAN}Opening AI Agent Configuration...\${NC}"
        cd "\$APP_DIR"
        "\$APP_DIR/venv/bin/python" "\$APP_DIR/startup.py"
        ;;
    backup)
        echo -e "\${BLUE}Creating backup...\${NC}"
        /usr/local/bin/tiz-lion-backup
        ;;
    health)
        echo -e "\${CYAN}Running health check...\${NC}"
        /usr/local/bin/tiz-lion-health-check && echo -e "\${GREEN}✅ Health check passed\${NC}" || echo -e "\${RED}❌ Health check failed\${NC}"
        ;;
    update)
        echo -e "\${BLUE}Updating application...\${NC}"
        cd "\$APP_DIR"
        sudo git fetch origin
        sudo git reset --hard origin/main
        sudo "\$APP_DIR/venv/bin/pip" install -r requirements.txt
        sudo systemctl restart \$SERVICE_NAME
        echo -e "\${GREEN}✅ Update completed\${NC}"
        ;;
    *)
        echo -e "\${CYAN}Tiz Lion AI Agent Control Panel\${NC}"
        echo "Usage: \$0 {start|stop|restart|status|logs|nginx-logs|config|backup|health|update}"
        echo ""
        echo -e "\${YELLOW}Commands:\${NC}"
        echo "  start      - Start the AI agent service"
        echo "  stop       - Stop the AI agent service"  
        echo "  restart    - Restart the AI agent service"
        echo "  status     - Show detailed system status"
        echo "  logs       - Show live application logs"
        echo "  nginx-logs - Show live nginx logs"
        echo "  config     - Configure AI agent settings"
        echo "  backup     - Create manual backup"
        echo "  health     - Run health check"
        echo "  update     - Update from GitHub"
        echo ""
        echo -e "\${BLUE}Quick access: 'tiz-lion-startup' or 'ai-agent'\${NC}"
        ;;
esac
EOF

    sudo chmod +x "/usr/local/bin/tiz-lion-control"
    success "Management script created successfully"
}

start_services() {
    log "Starting services..."
    
    # Start Redis if not running
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
    
    # Start and enable services
    sudo systemctl start "$SERVICE_NAME"
    sudo systemctl start nginx
    
    # Wait for services to start
    sleep 5
    
    # Check service status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "🎉 Tiz Lion AI Agent started successfully!"
        
        # Check nginx status
        if systemctl is-active --quiet nginx; then
            success "🌐 Nginx proxy started successfully!"
        else
            warn "Nginx may have issues - check logs with: sudo journalctl -u nginx"
        fi
        
        print_usage_instructions
    else
        error "Service failed to start!"
        warn "Check logs with: sudo journalctl -u $SERVICE_NAME --no-pager -n 50"
    fi
}

print_usage_instructions() {
    local public_ip=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")
    local protocol="http"
    local port_suffix=""
    
    if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ]; then
        protocol="https"
        public_ip="$DOMAIN_NAME"
    else
        if [ "$DEFAULT_PORT" != "80" ]; then
            port_suffix=":$DEFAULT_PORT"
        fi
    fi
    
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                    🎉 ${GREEN}TIZ LION AI AGENT DEPLOYED!${NC} 🎉                        ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                      Google Cloud Platform Edition                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}🌐 Web Interface: ${BLUE}${protocol}://${public_ip}${port_suffix}${NC}"
    echo -e "${GREEN}🔧 Application Port: ${BLUE}$DEFAULT_PORT${NC}"
    echo -e "${GREEN}📁 App Directory: ${BLUE}$APP_DIR${NC}"
    echo -e "${GREEN}📊 Log Directory: ${BLUE}$LOG_DIR${NC}"
    echo -e "${GREEN}💾 Backup Directory: ${BLUE}$BACKUP_DIR${NC}"
    
    if [ "$GC_PROJECT_ID" != "unknown" ] && [ "$GC_PROJECT_ID" != "" ]; then
        echo ""
        echo -e "${YELLOW}☁️  GOOGLE CLOUD PLATFORM:${NC}"
        echo -e "${CYAN}  Project ID: ${BLUE}$GC_PROJECT_ID${NC}"
        echo -e "${CYAN}  Zone: ${BLUE}$GC_ZONE${NC}"
        echo -e "${CYAN}  Instance: ${BLUE}$GC_INSTANCE_NAME${NC}"
    fi
    
    if [ "$ENABLE_SSL" = "true" ] && [ "$DOMAIN_NAME" != "" ]; then
        echo ""
        echo -e "${GREEN}🔒 SSL Certificate: ${BLUE}Enabled for $DOMAIN_NAME${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}🚀 QUICK START COMMANDS:${NC}"
    echo -e "${CYAN}  tiz-lion-startup${NC}    - Configure & launch AI agent (Interactive)"
    echo -e "${CYAN}  ai-agent${NC}            - Same as above (shortcut)"
    echo -e "${CYAN}  tiz-lion-control${NC}    - Advanced service management"
    echo ""
    echo -e "${YELLOW}⚙️ CONFIGURATION:${NC}"
    echo -e "${CYAN}  tiz-lion-startup${NC}    - Full interactive setup with settings menu"
    echo -e "${CYAN}  nano $APP_DIR/.env${NC}      - Edit configuration manually"
    echo ""
    echo -e "${YELLOW}🔧 SERVICE MANAGEMENT:${NC}"
    echo -e "${CYAN}  tiz-lion-control start${NC}     - Start the service"
    echo -e "${CYAN}  tiz-lion-control stop${NC}      - Stop the service"
    echo -e "${CYAN}  tiz-lion-control restart${NC}   - Restart the service"
    echo -e "${CYAN}  tiz-lion-control status${NC}    - Detailed system status"
    echo -e "${CYAN}  tiz-lion-control logs${NC}      - View live logs"
    echo -e "${CYAN}  tiz-lion-control health${NC}    - Run health check"
    echo -e "${CYAN}  tiz-lion-control update${NC}    - Update from GitHub"
    echo -e "${CYAN}  tiz-lion-control backup${NC}    - Create manual backup"
    echo ""
    echo -e "${YELLOW}📊 MONITORING & MAINTENANCE:${NC}"
    echo -e "${CYAN}  Health checks: ${BLUE}Every 5 minutes${NC}"
    echo -e "${CYAN}  Auto backups: ${BLUE}Daily at 2:00 AM${NC}"
    echo -e "${CYAN}  Log rotation: ${BLUE}Daily, 30 days retention${NC}"
    echo -e "${CYAN}  SSL renewal: ${BLUE}Automatic (Let's Encrypt)${NC}"
    echo ""
    echo -e "${YELLOW}📖 GETTING STARTED:${NC}"
    echo -e "${BLUE}  1. Run: ${CYAN}tiz-lion-startup${NC}"
    echo -e "${BLUE}  2. Configure your API keys and settings${NC}"
    echo -e "${BLUE}  3. Launch the AI agent from the menu${NC}"
    echo ""
    echo -e "${RED}⚠️  IMPORTANT:${NC}"
    echo -e "${BLUE}  • Configure your API keys before first use${NC}"
    echo -e "${BLUE}  • Review firewall settings: ${CYAN}sudo ufw status${NC}"
    echo -e "${BLUE}  • Monitor logs: ${CYAN}tiz-lion-control logs${NC}"
    echo ""
    echo -e "${BLUE}🔗 Documentation: ${CYAN}https://github.com/Tiz20lion/youtube-comment-AI-agent${NC}"
    echo ""
}

main() {
    print_header
    
    # Check if running as root (recommended for VPS deployment)
    if [[ $EUID -eq 0 ]]; then
        info "Running as root - recommended for VPS deployment"
    else
        warn "Running as non-root user - some operations may require sudo"
    fi
    
    # Detect Google Cloud environment
    detect_google_cloud
    
    # Main deployment steps
    check_port "$DEFAULT_PORT"
    install_system_deps
    create_directories
    setup_app
    create_startup_commands
    create_systemd_service
    setup_nginx_with_ssl
    setup_ssl_certificate
    configure_firewall
    setup_fail2ban
    setup_monitoring
    setup_backups
    setup_log_rotation
    create_management_script
    start_services
}

# Handle command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --ssl)
            ENABLE_SSL=true
            shift
            ;;
        --port)
            DEFAULT_PORT="$2"
            shift 2
            ;;
        --no-monitoring)
            MONITORING_ENABLED=false
            shift
            ;;
        --no-backup)
            AUTO_BACKUP_ENABLED=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --domain DOMAIN     Domain name for SSL certificate"
            echo "  --email EMAIL       Email for SSL certificate"
            echo "  --ssl              Enable SSL/HTTPS"
            echo "  --port PORT        Custom port (default: $DEFAULT_PORT)"
            echo "  --no-monitoring    Disable monitoring features"
            echo "  --no-backup        Disable automatic backups"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Basic installation"
            echo "  $0 --ssl --domain example.com --email admin@example.com"
            echo "  $0 --port 8080 --no-monitoring"
            exit 0
            ;;
        *)
            warn "Unknown option: $1"
            shift
            ;;
    esac
done

# Run main deployment
main "$@" 

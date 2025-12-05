#!/bin/bash
# TactiMesh Installation Script for Linux/Ubuntu
# Requires root privileges for system configuration

set -e

echo "🛡️  TactiMesh Military Mesh Network Installation"
echo "=================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    build-essential \
    libffi-dev \
    libssl-dev \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    sqlite3 \
    batctl \
    batman-adv-dkms \
    bridge-utils \
    iw \
    hostapd \
    dnsmasq

# Install BATMAN-adv mesh networking
echo "🕸️  Configuring BATMAN-adv mesh networking..."
modprobe batman-adv
echo 'batman-adv' >> /etc/modules

# Create batman interface configuration
cat > /etc/systemd/network/bat0.netdev << EOF
[NetDev]
Name=bat0
Kind=batadv
EOF

cat > /etc/systemd/network/bat0.network << EOF
[Match]
Name=bat0

[Network]
IPForward=yes
Address=192.168.200.1/24
EOF

# Enable systemd-networkd
systemctl enable systemd-networkd
systemctl enable systemd-resolved

# Create TactiMesh user
echo "👤 Creating tactimesh user..."
useradd -r -m -s /bin/bash tactimesh
usermod -aG dialout tactimesh  # For serial port access

# Create application directory
echo "📁 Setting up application directory..."
mkdir -p /opt/tactimesh
chown -R tactimesh:tactimesh /opt/tactimesh

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
sudo -u tactimesh python3 -m venv /opt/tactimesh/venv
sudo -u tactimesh /opt/tactimesh/venv/bin/pip install --upgrade pip
sudo -u tactimesh /opt/tactimesh/venv/bin/pip install -r requirements.txt

# Copy application files
echo "📋 Installing TactiMesh application..."
cp tactimesh.py /opt/tactimesh/
cp requirements.txt /opt/tactimesh/
chown -R tactimesh:tactimesh /opt/tactimesh/

# Create systemd service
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/tactimesh.service << EOF
[Unit]
Description=TactiMesh Military Mesh Network
After=network.target systemd-networkd.service
Wants=network.target

[Service]
Type=simple
User=tactimesh
Group=tactimesh
WorkingDirectory=/opt/tactimesh
Environment=PATH=/opt/tactimesh/venv/bin
ExecStart=/opt/tactimesh/venv/bin/python tactimesh.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/tactimesh
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable tactimesh.service

# Create logrotate configuration
cat > /etc/logrotate.d/tactimesh << EOF
/home/tactimesh/.tactimesh/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 tactimesh tactimesh
}
EOF

# Configure firewall
echo "🔒 Configuring firewall..."
ufw allow 8000/tcp  # Web interface
ufw allow 47474/udp # Mesh communication
ufw --force enable

# Create mesh network startup script
cat > /opt/tactimesh/start-mesh.sh << 'EOF'
#!/bin/bash
# TactiMesh Network Interface Setup

# Function to setup WiFi mesh interface
setup_wifi_mesh() {
    local interface=$1
    echo "Setting up WiFi mesh on $interface..."

    # Set interface to mesh mode
    iw dev $interface del 2>/dev/null || true
    iw phy phy0 interface add $interface type mesh
    ip link set $interface up

    # Join mesh network
    iw dev $interface mesh join tactimesh-net freq 2412

    # Add to batman-adv
    echo $interface > /sys/class/net/bat0/mesh/interfaces/$interface/batman_adv/mesh_iface

    echo "WiFi mesh interface $interface configured"
}

# Function to setup Ethernet mesh interface  
setup_ethernet_mesh() {
    local interface=$1
    echo "Setting up Ethernet mesh on $interface..."

    # Configure interface
    ip link set $interface up

    # Add to batman-adv
    echo $interface > /sys/class/net/bat0/mesh/interfaces/$interface/batman_adv/mesh_iface

    echo "Ethernet mesh interface $interface configured"
}

# Main execution
echo "🕸️  Starting TactiMesh network interfaces..."

# Create batman interface
ip link add name bat0 type batadv
ip link set bat0 up

# Configure available interfaces for mesh
# WiFi interfaces
for iface in wlan0 wlan1; do
    if ip link show $iface >/dev/null 2>&1; then
        setup_wifi_mesh $iface
    fi
done

# Ethernet interfaces (excluding management)
for iface in eth1 eth2 eth3; do
    if ip link show $iface >/dev/null 2>&1; then
        setup_ethernet_mesh $iface
    fi
done

# Configure batman-adv parameters
echo 1000 > /sys/class/net/bat0/mesh/orig_interval
echo 1 > /sys/class/net/bat0/mesh/distributed_arp_table
echo 1 > /sys/class/net/bat0/mesh/multicast_mode

# Assign IP to batman interface
ip addr add 192.168.200.1/24 dev bat0

echo "✅ TactiMesh network setup complete"
EOF

chmod +x /opt/tactimesh/start-mesh.sh
chown tactimesh:tactimesh /opt/tactimesh/start-mesh.sh

echo ""
echo "✅ TactiMesh installation completed successfully!"
echo ""
echo "🚀 Next steps:"
echo "1. Configure your mesh network interfaces in /opt/tactimesh/start-mesh.sh"
echo "2. Start the mesh network: sudo /opt/tactimesh/start-mesh.sh"
echo "3. Start TactiMesh service: systemctl start tactimesh"
echo "4. Access web interface: http://your-ip:8000"
echo ""
echo "📋 Service management:"
echo "  Status: systemctl status tactimesh"
echo "  Logs:   journalctl -u tactimesh -f"
echo "  Stop:   systemctl stop tactimesh"
echo ""
echo "🛡️  TactiMesh is ready for tactical deployment!"

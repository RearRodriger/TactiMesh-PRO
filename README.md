# TactiMesh: Real-Time Military Mesh Networking & Situational Awareness Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 🛡️ Overview

TactiMesh is a production-ready tactical communication and situational awareness system designed for military and emergency response operations. It provides real-time mesh networking capabilities with end-to-end encryption, blue force tracking, and offline mapping support.

### Key Features

- **🕸️ Mesh Networking**: BATMAN-adv and LoRa mesh support for resilient communication
- **🔒 Military-Grade Security**: End-to-end encryption with NaCl/Curve25519
- **📍 Blue Force Tracking**: Real-time position sharing and geospatial intelligence
- **💬 Tactical Messaging**: Priority-based message system with military classifications
- **🗺️ Offline Mapping**: Pre-cached maps with MGRS coordinate support
- **📱 Web Interface**: Real-time tactical dashboard with WebSocket updates
- **🔧 Production Ready**: Systemd service, logging, monitoring, and deployment scripts

## 🚀 Quick Start

### System Requirements

- Ubuntu 20.04+ or similar Linux distribution
- Python 3.8+
- Root access for mesh network configuration
- WiFi adapter supporting mesh mode (for WiFi mesh)
- LoRa transceiver (optional, for LoRa mesh)

### Installation

1. **Clone repository:**
   ```bash
   git clone https://github.com/your-org/tactimesh.git
   cd tactimesh
   ```

2. **Run installation script:**
   ```bash
   sudo ./install.sh
   ```

3. **Configure mesh interfaces:**
   ```bash
   sudo /opt/tactimesh/start-mesh.sh
   ```

4. **Start TactiMesh service:**
   ```bash
   sudo systemctl start tactimesh
   sudo systemctl status tactimesh
   ```

5. **Access web interface:**
   ```
   http://your-device-ip:8000
   ```

### Docker Deployment

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## 📋 Configuration

### Node Configuration

Edit `/opt/tactimesh/config.json`:

```json
{
  "node": {
    "callsign": "ALPHA-1",
    "unit": "1ST PLT",
    "rank": "SGT",
    "role": "TEAM_LEADER",
    "clearance_level": 3
  },
  "network": {
    "batman_enabled": true,
    "lora_enabled": false,
    "mesh_port": 47474
  }
}
```

### Mesh Network Setup

**BATMAN-adv (WiFi/Ethernet):**
```bash
# Configure WiFi mesh interface
iw dev wlan0 del
iw phy phy0 interface add mesh0 type mesh
iw dev mesh0 mesh join tactimesh-net freq 2412
ip link set mesh0 up

# Add to BATMAN-adv
echo mesh0 > /sys/class/net/bat0/mesh/interfaces/mesh0/batman_adv/mesh_iface
ip addr add 192.168.200.1/24 dev bat0
```

**LoRa Mesh:**
```json
{
  "network": {
    "lora_enabled": true,
    "lora_port": "/dev/ttyUSB0",
    "lora_baudrate": 115200
  }
}
```

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Client    │◄──►│   FastAPI Web    │◄──►│  TactiMesh Node │
│   (Browser)     │    │    Server        │    │    (Core)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                       ┌──────────────────┐             │
                       │   SQLite DB      │◄────────────┤
                       │   (Persistence)  │             │
                       └──────────────────┘             │
                                                         │
┌─────────────────┐    ┌──────────────────┐             │
│  BATMAN-adv     │◄──►│   Transport      │◄────────────┤
│  Mesh Layer     │    │   Adapters       │             │
└─────────────────┘    └──────────────────┘             │
                                │                        │
┌─────────────────┐             │               ┌────────▼────────┐
│   LoRa Mesh     │◄────────────┘               │   Situational   │
│   (Serial)      │                             │   Awareness     │
└─────────────────┘                             │   Engine        │
                                                 └─────────────────┘
```

### Message Flow

1. **Tactical Message Creation**: User creates message via web interface
2. **Encryption & Signing**: Message encrypted with recipient's public key and signed
3. **Mesh Distribution**: Message broadcast via all available transport adapters
4. **Reception & Verification**: Receiving nodes verify signatures and decrypt
5. **Database Storage**: Messages stored locally for offline access
6. **Real-time Updates**: WebSocket pushes updates to connected clients

## 🔒 Security Features

### Cryptographic Implementation

- **Key Exchange**: Curve25519 elliptic curve Diffie-Hellman
- **Encryption**: XSalsa20 stream cipher with Poly1305 MAC
- **Signatures**: Ed25519 digital signatures
- **Perfect Forward Secrecy**: Session keys rotated regularly
- **Message Integrity**: All messages cryptographically signed

### Security Best Practices

- Keys stored with restricted file permissions (600)
- No plaintext sensitive data in logs
- Configurable message expiration
- Network traffic analysis resistant
- Side-channel attack mitigations

## 📡 Networking Protocols

### BATMAN-adv Integration

TactiMesh leverages BATMAN-adv (Better Approach To Mobile Ad-hoc Networking) for:
- Automatic mesh topology discovery
- Loop-free routing
- Link quality assessment
- Fast failover and healing

### LoRa Mesh Support

For long-range, low-power communications:
- Serial bridge to LoRa transceivers
- Configurable frequency and power
- Store-and-forward messaging
- Integration with existing LoRa mesh protocols

## 🗺️ Geospatial Features

### Coordinate Systems

- **WGS84**: Standard GPS coordinates
- **MGRS**: Military Grid Reference System
- **UTM**: Universal Transverse Mercator
- **Custom Projections**: Configurable coordinate systems

### Mapping Capabilities

- Offline map tile caching
- Real-time position tracking
- Geofence monitoring
- Tactical overlay support
- Route planning and analysis

## 🔧 Operations & Maintenance

### Service Management

```bash
# Service status
systemctl status tactimesh

# View logs
journalctl -u tactimesh -f

# Restart service
systemctl restart tactimesh

# Stop service
systemctl stop tactimesh
```

### Log Analysis

```bash
# Application logs
tail -f /home/tactimesh/.tactimesh/logs/tactimesh.log

# System logs
journalctl -u tactimesh --since "1 hour ago"

# Network diagnostics
batctl if    # BATMAN-adv interfaces
batctl o     # Originator table
batctl n     # Neighbor table
```

### Performance Monitoring

- Message throughput tracking
- Network topology visualization
- Node health monitoring
- Resource usage statistics

## 🔧 Development & Customization

### Adding Custom Message Types

```python
# Define new message topic
TOPIC_CUSTOM = "custom_intel"

# Handle in message processor
async def _process_received_message(self, message: TacticalMessage):
    if message.topic == TOPIC_CUSTOM:
        # Custom processing logic
        await self._handle_custom_intel(message)
```

### Transport Adapter Development

```python
class CustomTransportAdapter(MeshTransportAdapter):
    async def send_message(self, data: bytes, destination: Optional[str] = None):
        # Implement custom transport logic
        pass

    async def receive_message(self) -> Tuple[bytes, Optional[str]]:
        # Implement message reception
        pass
```

## 📚 API Reference

### REST Endpoints

- `GET /api/tactical-picture` - Current tactical situation
- `GET /api/nodes` - Active mesh nodes
- `GET /api/messages` - Recent messages
- `POST /api/messages` - Send tactical message

### WebSocket Events

- `send_message` - Transmit message
- `update_position` - Update node position
- `message` - Incoming message notification

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for authorized military and emergency response use only. Users are responsible for compliance with applicable laws and regulations regarding radio communications and encryption technologies.

## 📞 Support

For technical support and deployment assistance:
- Email: support@tactimesh.mil
- Documentation: https://docs.tactimesh.mil
- Issue Tracker: https://github.com/your-org/tactimesh/issues

---

**🛡️ TactiMesh - Secure Communications for Critical Operations**

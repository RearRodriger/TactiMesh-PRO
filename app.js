class TactiMesh {
    constructor() {
        this.nodes = {
            "ALPHA-1": {
                id: "ALPHA-1",
                callsign: "ALPHA-1",
                unit: "1ST PLT HQ",
                role: "TEAM_LEADER",
                rank: "SSG",
                lat: 37.7749,
                lon: -122.4194,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 89,
                signalStrength: 95
            },
            "BRAVO-2": {
                id: "BRAVO-2",
                callsign: "BRAVO-2",
                unit: "1ST PLT",
                role: "RIFLEMAN",
                rank: "CPL",
                lat: 37.7729,
                lon: -122.4174,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 67,
                signalStrength: 88
            },
            "CHARLIE-3": {
                id: "CHARLIE-3",
                callsign: "CHARLIE-3",
                unit: "1ST PLT",
                role: "MEDIC",
                rank: "SPC",
                lat: 37.7769,
                lon: -122.4214,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 78,
                signalStrength: 92
            },
            "DELTA-4": {
                id: "DELTA-4",
                callsign: "DELTA-4",
                unit: "SNIPER TEAM",
                role: "SNIPER",
                rank: "SGT",
                lat: 37.7789,
                lon: -122.4154,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 91,
                signalStrength: 85
            },
            "ECHO-5": {
                id: "ECHO-5",
                callsign: "ECHO-5",
                unit: "ENGINEER",
                role: "ENGINEER",
                rank: "SPC",
                lat: 37.7709,
                lon: -122.4234,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 73,
                signalStrength: 90
            },
            "FOXTROT-6": {
                id: "FOXTROT-6",
                callsign: "FOXTROT-6",
                unit: "COMMS",
                role: "RTO",
                rank: "PFC",
                lat: 37.7739,
                lon: -122.4184,
                status: "ACTIVE",
                lastSeen: new Date(),
                battery: 85,
                signalStrength: 98
            }
        };

        this.messages = [
            {
                id: 1,
                sender: "ALPHA-1",
                recipient: "ALL",
                type: "COMMAND",
                content: "Move to overwatch positions. Enemy activity reported in sector 7-G.",
                timestamp: new Date(Date.now() - 15 * 60000),
                priority: 1,
                acknowledged: true
            },
            {
                id: 2,
                sender: "DELTA-4",
                recipient: "ALPHA-1",
                type: "INTEL",
                content: "Eyes on 3x enemy personnel, grid 32T 0123 4567. No weapons visible.",
                timestamp: new Date(Date.now() - 10 * 60000),
                priority: 2,
                acknowledged: true
            },
            {
                id: 3,
                sender: "CHARLIE-3",
                recipient: "ALPHA-1",
                type: "MEDICAL",
                content: "BRAVO-2 minor injury, continuing mission. Medical supplies adequate.",
                timestamp: new Date(Date.now() - 5 * 60000),
                priority: 1,
                acknowledged: false
            }
        ];

        this.geofences = [
            {
                name: "FRIENDLY ZONE",
                type: "FRIENDLY",
                coordinates: [[37.770, -122.425], [37.780, -122.425], [37.780, -122.410], [37.770, -122.410]],
                color: "#00ff0040"
            },
            {
                name: "RESTRICTED AREA",
                type: "RESTRICTED",
                coordinates: [[37.775, -122.420], [37.785, -122.420], [37.785, -122.405], [37.775, -122.405]],
                color: "#ff000040"
            }
        ];

        this.mapScale = 2000;
        this.mapCenter = { lat: 37.7749, lon: -122.4194 };
        this.activeTab = 'network';
        this.messageIdCounter = 4;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startSimulation();
        this.renderMap();
        this.updateUI();
        this.updateMissionTime();
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Map controls
        document.getElementById('zoomIn').addEventListener('click', () => this.zoomIn());
        document.getElementById('zoomOut').addEventListener('click', () => this.zoomOut());
        document.getElementById('centerMap').addEventListener('click', () => this.centerMap());

        // Message sending
        document.getElementById('sendMessage').addEventListener('click', () => this.sendMessage());

        // Modal close
        document.getElementById('modalClose').addEventListener('click', () => this.closeModal());

        // Populate selects
        this.populateMessageSelects();
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabName) {
                btn.classList.add('active');
            }
        });

        // Update tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(tabName + 'Tab').classList.add('active');

        this.activeTab = tabName;
        this.updateUI();
    }

    populateMessageSelects() {
        const senderSelect = document.getElementById('messageSender');
        const recipientSelect = document.getElementById('messageRecipient');

        // Clear existing options except first
        senderSelect.innerHTML = '<option value="ALPHA-1">ALPHA-1 (Self)</option>';
        recipientSelect.innerHTML = '<option value="ALL">ALL STATIONS</option>';

        // Add all nodes as potential recipients
        Object.values(this.nodes).forEach(node => {
            if (node.id !== 'ALPHA-1') {
                recipientSelect.innerHTML += `<option value="${node.id}">${node.callsign}</option>`;
            }
        });
    }

    sendMessage() {
        const sender = document.getElementById('messageSender').value;
        const recipient = document.getElementById('messageRecipient').value;
        const type = document.getElementById('messageType').value;
        const priority = parseInt(document.getElementById('messagePriority').value);
        const content = document.getElementById('messageContent').value.trim();

        if (!content) {
            alert('Message content cannot be empty.');
            return;
        }

        const message = {
            id: this.messageIdCounter++,
            sender,
            recipient,
            type,
            content,
            timestamp: new Date(),
            priority,
            acknowledged: false
        };

        this.messages.unshift(message);
        document.getElementById('messageContent').value = '';
        this.updateUI();

        // Simulate response after delay
        setTimeout(() => {
            this.simulateMessageResponse(message);
        }, 2000 + Math.random() * 3000);
    }

    simulateMessageResponse(originalMessage) {
        if (originalMessage.recipient === 'ALL' || originalMessage.sender === originalMessage.recipient) {
            return;
        }

        const responses = {
            'COMMAND': ['Roger, moving to position.', 'Wilco, ETA 5 minutes.', 'Copy, standing by.'],
            'INTEL': ['Confirmed, tracking target.', 'Roger, relaying to HQ.', 'Copy, maintaining overwatch.'],
            'MEDICAL': ['Roger, medical support available.', 'Copy, standing by for medevac.'],
            'LOGISTICS': ['Supply drop confirmed.', 'Roger, resupply en route.'],
            'SITREP': ['Roger, status acknowledged.', 'Copy, continuing mission.']
        };

        const responseOptions = responses[originalMessage.type] || ['Roger, message received.'];
        const response = responseOptions[Math.floor(Math.random() * responseOptions.length)];

        const responseMessage = {
            id: this.messageIdCounter++,
            sender: originalMessage.recipient,
            recipient: originalMessage.sender,
            type: 'SITREP',
            content: response,
            timestamp: new Date(),
            priority: 3,
            acknowledged: false
        };

        this.messages.unshift(responseMessage);
        this.updateUI();
    }

    startSimulation() {
        // Update node positions periodically
        setInterval(() => {
            this.updateNodePositions();
            this.renderMap();
            this.updateUI();
        }, 15000);

        // Generate periodic status messages
        setInterval(() => {
            this.generateStatusMessage();
        }, 30000);

        // Update mission time
        setInterval(() => {
            this.updateMissionTime();
        }, 1000);
    }

    updateNodePositions() {
        Object.values(this.nodes).forEach(node => {
            // Small random movement within realistic bounds
            const moveDistance = 0.0005; // ~50 meters
            const angle = Math.random() * Math.PI * 2;
            
            node.lat += Math.cos(angle) * moveDistance * (Math.random() - 0.5);
            node.lon += Math.sin(angle) * moveDistance * (Math.random() - 0.5);
            
            // Keep nodes within reasonable bounds
            node.lat = Math.max(37.765, Math.min(37.785, node.lat));
            node.lon = Math.max(-122.430, Math.min(-122.405, node.lon));
            
            node.lastSeen = new Date();
            
            // Simulate battery drain
            if (Math.random() < 0.1) {
                node.battery = Math.max(20, node.battery - Math.floor(Math.random() * 3));
            }
            
            // Simulate signal strength changes
            node.signalStrength = Math.max(70, Math.min(100, 
                node.signalStrength + Math.floor((Math.random() - 0.5) * 10)
            ));
        });
    }

    generateStatusMessage() {
        const nodeIds = Object.keys(this.nodes);
        const senderId = nodeIds[Math.floor(Math.random() * nodeIds.length)];
        
        const statusMessages = [
            "Position secure, no contact.",
            "Area of operations clear.",
            "Continuing patrol route.",
            "All equipment operational.",
            "Maintaining overwatch position.",
            "No enemy activity observed.",
            "Radio check - signal clear.",
            "Supplies adequate for mission."
        ];

        const message = {
            id: this.messageIdCounter++,
            sender: senderId,
            recipient: "ALPHA-1",
            type: "SITREP",
            content: statusMessages[Math.floor(Math.random() * statusMessages.length)],
            timestamp: new Date(),
            priority: 3,
            acknowledged: false
        };

        this.messages.unshift(message);
        
        // Keep message history reasonable
        if (this.messages.length > 50) {
            this.messages = this.messages.slice(0, 50);
        }

        this.updateUI();
    }

    updateMissionTime() {
        const now = new Date();
        const missionStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 19, 0, 0);
        const elapsed = now - missionStart;
        
        const hours = Math.floor(elapsed / (1000 * 60 * 60));
        const minutes = Math.floor((elapsed % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((elapsed % (1000 * 60)) / 1000);
        
        document.getElementById('missionTime').textContent = 
            `T+${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    renderMap() {
        const svg = document.getElementById('mapSvg');
        const rect = svg.getBoundingClientRect();
        
        // Clear existing elements
        document.getElementById('geofenceLayer').innerHTML = '';
        document.getElementById('meshLayer').innerHTML = '';
        document.getElementById('nodeLayer').innerHTML = '';

        // Render geofences
        this.renderGeofences();
        
        // Render mesh connections
        this.renderMeshConnections();
        
        // Render nodes
        this.renderNodes();
    }

    renderGeofences() {
        const geofenceLayer = document.getElementById('geofenceLayer');
        
        this.geofences.forEach(geofence => {
            const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            const points = geofence.coordinates.map(coord => {
                const screenPos = this.latLonToScreen(coord[0], coord[1]);
                return `${screenPos.x},${screenPos.y}`;
            }).join(' ');
            
            polygon.setAttribute('points', points);
            polygon.setAttribute('class', `geofence-${geofence.type.toLowerCase()}`);
            
            geofenceLayer.appendChild(polygon);
        });
    }

    renderMeshConnections() {
        const meshLayer = document.getElementById('meshLayer');
        const nodes = Object.values(this.nodes);
        
        // Create connections between nearby nodes
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const node1 = nodes[i];
                const node2 = nodes[j];
                const distance = this.calculateDistance(node1.lat, node1.lon, node2.lat, node2.lon);
                
                // Connect nodes within ~2km range
                if (distance < 2) {
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    const pos1 = this.latLonToScreen(node1.lat, node1.lon);
                    const pos2 = this.latLonToScreen(node2.lat, node2.lon);
                    
                    line.setAttribute('x1', pos1.x);
                    line.setAttribute('y1', pos1.y);
                    line.setAttribute('x2', pos2.x);
                    line.setAttribute('y2', pos2.y);
                    line.setAttribute('class', distance < 1 ? 'mesh-connection strong' : 'mesh-connection');
                    
                    meshLayer.appendChild(line);
                }
            }
        }
    }

    renderNodes() {
        const nodeLayer = document.getElementById('nodeLayer');
        
        Object.values(this.nodes).forEach(node => {
            const screenPos = this.latLonToScreen(node.lat, node.lon);
            
            // Create node group
            const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            nodeGroup.setAttribute('class', 'node-marker');
            nodeGroup.setAttribute('data-node-id', node.id);
            nodeGroup.style.cursor = 'pointer';
            
            // Create node circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', screenPos.x);
            circle.setAttribute('cy', screenPos.y);
            circle.setAttribute('r', 8);
            circle.setAttribute('class', 'node-friendly');
            
            // Create node label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', screenPos.x);
            text.setAttribute('y', screenPos.y - 15);
            text.setAttribute('class', 'node-label');
            text.textContent = node.callsign;
            
            // Add click event
            nodeGroup.addEventListener('click', () => this.showNodeDetails(node));
            
            nodeGroup.appendChild(circle);
            nodeGroup.appendChild(text);
            nodeLayer.appendChild(nodeGroup);
        });
    }

    latLonToScreen(lat, lon) {
        const svg = document.getElementById('mapSvg');
        const rect = svg.getBoundingClientRect();
        
        // Simple mercator-like projection
        const x = ((lon - this.mapCenter.lon) * this.mapScale) + rect.width / 2;
        const y = ((this.mapCenter.lat - lat) * this.mapScale) + rect.height / 2;
        
        return { x, y };
    }

    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth's radius in kilometers
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    zoomIn() {
        this.mapScale *= 1.5;
        this.renderMap();
    }

    zoomOut() {
        this.mapScale /= 1.5;
        this.renderMap();
    }

    centerMap() {
        // Center on ALPHA-1
        const alpha1 = this.nodes['ALPHA-1'];
        this.mapCenter = { lat: alpha1.lat, lon: alpha1.lon };
        this.renderMap();
    }

    showNodeDetails(node) {
        const modal = document.getElementById('nodeModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');
        
        modalTitle.textContent = `${node.callsign} - NODE DETAILS`;
        
        const connections = this.getNodeConnections(node);
        
        modalBody.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
                <div>
                    <strong>Callsign:</strong><br>${node.callsign}<br><br>
                    <strong>Unit:</strong><br>${node.unit}<br><br>
                    <strong>Role:</strong><br>${node.role}<br><br>
                    <strong>Rank:</strong><br>${node.rank}
                </div>
                <div>
                    <strong>Status:</strong><br><span style="color: var(--color-success);">${node.status}</span><br><br>
                    <strong>Battery:</strong><br>${node.battery}%<br><br>
                    <strong>Signal:</strong><br>${node.signalStrength}%<br><br>
                    <strong>Last Seen:</strong><br>${node.lastSeen.toLocaleTimeString()}
                </div>
            </div>
            <div style="border-top: 1px solid var(--color-border); padding-top: 16px;">
                <strong>Coordinates:</strong><br>
                Lat: ${node.lat.toFixed(6)}°<br>
                Lon: ${node.lon.toFixed(6)}°<br><br>
                <strong>Mesh Connections:</strong><br>
                ${connections.join(', ') || 'No active connections'}
            </div>
        `;
        
        modal.classList.add('show');
    }

    getNodeConnections(targetNode) {
        const connections = [];
        
        Object.values(this.nodes).forEach(node => {
            if (node.id !== targetNode.id) {
                const distance = this.calculateDistance(
                    targetNode.lat, targetNode.lon,
                    node.lat, node.lon
                );
                
                if (distance < 2) {
                    connections.push(node.callsign);
                }
            }
        });
        
        return connections;
    }

    closeModal() {
        document.getElementById('nodeModal').classList.remove('show');
    }

    updateUI() {
        this.updateNetworkTab();
        this.updateMessagingTab();
        this.updateTrackerTab();
        this.updateHeader();
    }

    updateHeader() {
        document.getElementById('nodeCount').textContent = Object.keys(this.nodes).length;
        
        // Update connection count
        let connectionCount = 0;
        const nodes = Object.values(this.nodes);
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const distance = this.calculateDistance(
                    nodes[i].lat, nodes[i].lon,
                    nodes[j].lat, nodes[j].lon
                );
                if (distance < 2) connectionCount++;
            }
        }
        
        document.getElementById('connectionCount').textContent = connectionCount;
        
        // Update average latency (simulated)
        const avgLatency = 30 + Math.floor(Math.random() * 30);
        document.getElementById('avgLatency').textContent = avgLatency + 'ms';
    }

    updateNetworkTab() {
        if (this.activeTab !== 'network') return;
        
        const nodeList = document.getElementById('nodeList');
        nodeList.innerHTML = '';
        
        Object.values(this.nodes).forEach(node => {
            const nodeItem = document.createElement('div');
            nodeItem.className = 'node-item';
            nodeItem.innerHTML = `
                <div class="node-header">
                    <span class="node-callsign">${node.callsign}</span>
                    <span class="node-status">${node.status}</span>
                </div>
                <div class="node-details">
                    <div>${node.unit} - ${node.role}</div>
                    <div>Battery: ${node.battery}% | Signal: ${node.signalStrength}%</div>
                    <div>Last seen: ${node.lastSeen.toLocaleTimeString()}</div>
                </div>
            `;
            
            nodeItem.addEventListener('click', () => this.showNodeDetails(node));
            nodeList.appendChild(nodeItem);
        });
    }

    updateMessagingTab() {
        if (this.activeTab !== 'messaging') return;
        
        const messageList = document.getElementById('messageList');
        messageList.innerHTML = '';
        
        this.messages.slice(0, 20).forEach(message => {
            const messageItem = document.createElement('div');
            messageItem.className = `message-item ${message.type.toLowerCase()}`;
            messageItem.innerHTML = `
                <div class="message-header">
                    <div>
                        <span class="message-from">${message.sender}</span>
                        <span class="message-type">${message.type}</span>
                    </div>
                    <div class="message-time">${message.timestamp.toLocaleTimeString()}</div>
                </div>
                <div class="message-content">${message.content}</div>
            `;
            
            messageList.appendChild(messageItem);
        });
    }

    updateTrackerTab() {
        if (this.activeTab !== 'tracker') return;
        
        const unitList = document.getElementById('unitList');
        unitList.innerHTML = '';
        
        Object.values(this.nodes).forEach(node => {
            const unitItem = document.createElement('div');
            unitItem.className = 'unit-item';
            
            // Convert to MGRS-style coordinates (simplified)
            const mgrs = this.convertToMGRS(node.lat, node.lon);
            
            unitItem.innerHTML = `
                <div class="unit-header">
                    <span class="unit-callsign">${node.callsign}</span>
                    <span class="unit-coordinates">${mgrs}</span>
                </div>
                <div class="unit-info">
                    <div>${node.unit} - ${node.role} (${node.rank})</div>
                    <div>Status: ${node.status} | Battery: ${node.battery}%</div>
                </div>
            `;
            
            unitList.appendChild(unitItem);
        });
    }

    convertToMGRS(lat, lon) {
        // Simplified MGRS conversion for demo purposes
        const zone = '32T';
        const easting = Math.floor((lon + 122.5) * 10000).toString().padStart(4, '0');
        const northing = Math.floor((lat - 37.7) * 10000).toString().padStart(4, '0');
        return `${zone} ${easting} ${northing}`;
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TactiMesh();
});
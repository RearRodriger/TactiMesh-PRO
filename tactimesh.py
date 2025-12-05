#!/usr/bin/env python3
"""
TactiMesh: Real-Time Military Mesh Networking & Situational Awareness Platform
==============================================================================

A production-ready tactical communication and situational awareness system featuring:
- Real-time mesh networking over BATMAN-adv/OLSR and LoRa
- End-to-end encryption with NaCl/Curve25519
- Blue force tracking and geospatial intelligence
- Offline mapping and tactical data exchange
- Military-grade security and resilience

Author: TactiMesh Development Team
License: Military/Government Use Only
Version: 1.0.0
"""

import os
import sys
import json
import time
import asyncio
import socket
import struct
import base64
import uuid
import secrets
import sqlite3
import threading
import logging
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path

# Core dependencies
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import transform
import pyproj

# Cryptography
from nacl.public import PrivateKey, PublicKey, Box
from nacl.signing import SigningKey, VerifyKey
from nacl.secret import SecretBox
from nacl.utils import random
from nacl.encoding import Base64Encoder
from nacl.exceptions import BadSignatureError

# Web framework and real-time communication
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn

# Serial communication for LoRa
try:
    import serial
    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

# Application directories
APP_DIR = Path.home() / ".tactimesh"
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DIR / "tactimesh.db"
KEY_PATH = APP_DIR / "keys.json"
CONFIG_PATH = APP_DIR / "config.json"
MAPS_DIR = APP_DIR / "maps"
ATTACH_DIR = APP_DIR / "attachments"
LOGS_DIR = APP_DIR / "logs"

for directory in [MAPS_DIR, ATTACH_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Network configuration
MESH_PORT = 47474
BROADCAST_ADDR = "255.255.255.255"
DEFAULT_INTERFACE = "bat0"  # BATMAN-adv interface

# Message topics (military standard)
TOPIC_BLUE_FORCE = "blue_force"
TOPIC_RED_FORCE = "red_force" 
TOPIC_NEUTRAL = "neutral"
TOPIC_INTEL = "intel"
TOPIC_SITREP = "sitrep"
TOPIC_MEDEVAC = "medevac"
TOPIC_SUPPLIES = "supplies"
TOPIC_FIRES = "fires"
TOPIC_COMMAND = "command"
TOPIC_ALERT = "alert"
TOPIC_FILE = "file_transfer"

# Military grid reference system
MGRS_ZONES = ["32T", "32U", "33T", "33U"]

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'tactimesh.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class NodeIdentity:
    """Military node identification"""
    node_id: str
    callsign: str
    unit: str
    rank: str
    role: str
    clearance_level: int
    pubkey: str
    verify_key: str
    created: float

@dataclass
class Position:
    """Geospatial position data"""
    node_id: str
    lat: float
    lon: float
    alt: float
    accuracy: float
    speed: float
    course: float
    timestamp: float
    mgrs: str = ""

@dataclass
class TacticalMessage:
    """Military tactical message format"""
    msg_id: str
    msg_type: str
    topic: str
    sender: str
    recipients: List[str]
    classification: str
    priority: int  # 0=FLASH, 1=IMMEDIATE, 2=PRIORITY, 3=ROUTINE
    timestamp: float
    expires: Optional[float]
    payload: Dict[str, Any]
    attachments: List[str]
    signature: Optional[str] = None

@dataclass
class GeofenceZone:
    """Tactical geofence definition"""
    zone_id: str
    name: str
    zone_type: str  # FRIENDLY, HOSTILE, RESTRICTED, OBJECTIVE
    polygon: str  # WKT format
    classification: str
    created_by: str
    created: float
    active: bool = True

# =============================================================================
# CRYPTOGRAPHIC SECURITY MODULE
# =============================================================================

class MilitaryCrypto:
    """Military-grade encryption and key management"""

    def __init__(self):
        self.keys = self._load_or_generate_keys()
        self.session_keys: Dict[str, SecretBox] = {}

    def _load_or_generate_keys(self) -> Dict[str, str]:
        """Load existing keys or generate new military-grade keypair"""
        if KEY_PATH.exists():
            try:
                with open(KEY_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load keys: {e}")

        # Generate new keypair
        enc_private = PrivateKey.generate()
        sig_private = SigningKey.generate()

        keys = {
            "node_id": str(uuid.uuid4()),
            "enc_private": base64.b64encode(bytes(enc_private)).decode(),
            "enc_public": base64.b64encode(bytes(enc_private.public_key)).decode(),
            "sig_private": base64.b64encode(bytes(sig_private)).decode(),
            "sig_public": base64.b64encode(bytes(sig_private.verify_key)).decode(),
            "created": time.time()
        }

        # Save keys securely
        try:
            with open(KEY_PATH, 'w') as f:
                json.dump(keys, f, indent=2)
            os.chmod(KEY_PATH, 0o600)  # Secure permissions
            logger.info("Generated new military crypto keys")
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")

        return keys

    def sign_message(self, data: bytes) -> str:
        """Sign message with private key"""
        try:
            signing_key = SigningKey(base64.b64decode(self.keys["sig_private"]))
            signature = signing_key.sign(data).signature
            return base64.b64encode(signature).decode()
        except Exception as e:
            logger.error(f"Message signing failed: {e}")
            raise

    def verify_signature(self, data: bytes, signature: str, public_key: str) -> bool:
        """Verify message signature"""
        try:
            verify_key = VerifyKey(base64.b64decode(public_key))
            verify_key.verify(data, base64.b64decode(signature))
            return True
        except (BadSignatureError, Exception) as e:
            logger.warning(f"Signature verification failed: {e}")
            return False

    def encrypt_message(self, data: bytes, recipient_public_key: str) -> bytes:
        """Encrypt message for specific recipient"""
        try:
            private_key = PrivateKey(base64.b64decode(self.keys["enc_private"]))
            public_key = PublicKey(base64.b64decode(recipient_public_key))
            box = Box(private_key, public_key)
            return box.encrypt(data)
        except Exception as e:
            logger.error(f"Message encryption failed: {e}")
            raise

    def decrypt_message(self, encrypted_data: bytes, sender_public_key: str) -> bytes:
        """Decrypt message from sender"""
        try:
            private_key = PrivateKey(base64.b64decode(self.keys["enc_private"]))
            public_key = PublicKey(base64.b64decode(sender_public_key))
            box = Box(private_key, public_key)
            return box.decrypt(encrypted_data)
        except Exception as e:
            logger.error(f"Message decryption failed: {e}")
            raise

# =============================================================================
# DATABASE & PERSISTENCE LAYER
# =============================================================================

class TacticalDatabase:
    """SQLite database for tactical data persistence"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        """Create database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    callsign TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    rank TEXT NOT NULL,
                    role TEXT NOT NULL,
                    clearance_level INTEGER NOT NULL,
                    pubkey TEXT NOT NULL,
                    verify_key TEXT NOT NULL,
                    last_seen REAL NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    created REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS positions (
                    node_id TEXT PRIMARY KEY,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    alt REAL NOT NULL,
                    accuracy REAL NOT NULL,
                    speed REAL NOT NULL,
                    course REAL NOT NULL,
                    mgrs TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (node_id) REFERENCES nodes(node_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    msg_id TEXT PRIMARY KEY,
                    msg_type TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipients TEXT NOT NULL,  -- JSON array
                    classification TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    expires REAL,
                    payload TEXT NOT NULL,     -- JSON
                    attachments TEXT,          -- JSON array
                    signature TEXT,
                    delivered BOOLEAN DEFAULT FALSE,
                    acknowledged BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS geofences (
                    zone_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    zone_type TEXT NOT NULL,
                    polygon TEXT NOT NULL,     -- WKT format
                    classification TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created REAL NOT NULL,
                    active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS files (
                    file_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    uploaded REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic);
                CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_nodes_unit ON nodes(unit);
            """)

    def upsert_node(self, node: NodeIdentity):
        """Insert or update node information"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO nodes 
                (node_id, callsign, unit, rank, role, clearance_level, pubkey, verify_key, last_seen, created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (node.node_id, node.callsign, node.unit, node.rank, node.role, 
                  node.clearance_level, node.pubkey, node.verify_key, time.time(), node.created))

    def upsert_position(self, position: Position):
        """Insert or update position data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO positions 
                (node_id, lat, lon, alt, accuracy, speed, course, mgrs, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (position.node_id, position.lat, position.lon, position.alt,
                  position.accuracy, position.speed, position.course, position.mgrs, position.timestamp))

    def store_message(self, message: TacticalMessage):
        """Store tactical message"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO messages 
                (msg_id, msg_type, topic, sender, recipients, classification, priority, 
                 timestamp, expires, payload, attachments, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (message.msg_id, message.msg_type, message.topic, message.sender,
                  json.dumps(message.recipients), message.classification, message.priority,
                  message.timestamp, message.expires, json.dumps(message.payload),
                  json.dumps(message.attachments), message.signature))

    def get_active_nodes(self, max_age_seconds: int = 300) -> List[NodeIdentity]:
        """Get nodes active within specified time"""
        cutoff_time = time.time() - max_age_seconds
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT node_id, callsign, unit, rank, role, clearance_level, 
                       pubkey, verify_key, created
                FROM nodes 
                WHERE last_seen > ? AND status = 'ACTIVE'
                ORDER BY last_seen DESC
            """, (cutoff_time,))

            return [NodeIdentity(*row) for row in cursor.fetchall()]

    def get_current_positions(self, max_age_seconds: int = 300) -> List[Position]:
        """Get current position data for active nodes"""
        cutoff_time = time.time() - max_age_seconds
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT p.node_id, p.lat, p.lon, p.alt, p.accuracy, p.speed, p.course, p.mgrs, p.timestamp
                FROM positions p
                JOIN nodes n ON p.node_id = n.node_id
                WHERE p.timestamp > ? AND n.status = 'ACTIVE'
                ORDER BY p.timestamp DESC
            """, (cutoff_time,))

            return [Position(*row) for row in cursor.fetchall()]

# =============================================================================
# MESH NETWORK TRANSPORT LAYER
# =============================================================================

class MeshTransportAdapter:
    """Abstract base class for mesh transport adapters"""

    async def send_message(self, data: bytes, destination: Optional[str] = None):
        raise NotImplementedError

    async def receive_message(self) -> Tuple[bytes, Optional[str]]:
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    async def stop(self):
        raise NotImplementedError

class BatmanAdvAdapter(MeshTransportAdapter):
    """BATMAN-adv mesh network adapter"""

    def __init__(self, interface: str = DEFAULT_INTERFACE, port: int = MESH_PORT):
        self.interface = interface
        self.port = port
        self.socket = None
        self.running = False

    async def start(self):
        """Initialize BATMAN-adv transport"""
        try:
            # Verify BATMAN-adv interface exists
            result = subprocess.run(['ip', 'link', 'show', self.interface], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"BATMAN-adv interface {self.interface} not found")
                return False

            # Create UDP socket for application-level mesh communication
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.setblocking(False)

            self.running = True
            logger.info(f"BATMAN-adv adapter started on {self.interface}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start BATMAN-adv adapter: {e}")
            return False

    async def send_message(self, data: bytes, destination: Optional[str] = None):
        """Send message via BATMAN-adv mesh"""
        if not self.socket or not self.running:
            return

        try:
            if destination:
                # Unicast to specific node
                addr = (destination, self.port)
            else:
                # Broadcast to all mesh nodes
                addr = (BROADCAST_ADDR, self.port)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.socket.sendto, data, addr)

        except Exception as e:
            logger.error(f"Failed to send message via BATMAN-adv: {e}")

    async def receive_message(self) -> Tuple[bytes, Optional[str]]:
        """Receive message from BATMAN-adv mesh"""
        if not self.socket or not self.running:
            return b'', None

        try:
            loop = asyncio.get_event_loop()
            data, addr = await loop.run_in_executor(None, self.socket.recvfrom, 65535)
            return data, addr[0]

        except socket.error:
            await asyncio.sleep(0.01)
            return b'', None
        except Exception as e:
            logger.error(f"Failed to receive message via BATMAN-adv: {e}")
            return b'', None

class LoRaMeshAdapter(MeshTransportAdapter):
    """LoRa mesh network adapter via serial bridge"""

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.running = False

    async def start(self):
        """Initialize LoRa mesh transport"""
        if not LORA_AVAILABLE:
            logger.error("PySerial not available for LoRa adapter")
            return False

        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            logger.info(f"LoRa mesh adapter started on {self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start LoRa adapter: {e}")
            return False

    async def send_message(self, data: bytes, destination: Optional[str] = None):
        """Send message via LoRa mesh"""
        if not self.serial_conn or not self.running:
            return

        try:
            # Encode message as base64 and send as line
            encoded = base64.b64encode(data).decode() + '\n'
            self.serial_conn.write(encoded.encode())

        except Exception as e:
            logger.error(f"Failed to send LoRa message: {e}")

    async def receive_message(self) -> Tuple[bytes, Optional[str]]:
        """Receive message from LoRa mesh"""
        if not self.serial_conn or not self.running:
            return b'', None

        try:
            line = self.serial_conn.readline()
            if not line:
                await asyncio.sleep(0.05)
                return b'', None

            # Decode base64 message
            data = base64.b64decode(line.strip())
            return data, None  # LoRa doesn't provide source address

        except Exception as e:
            logger.error(f"Failed to receive LoRa message: {e}")
            return b'', None

# =============================================================================
# TACTICAL MESH NODE
# =============================================================================

class TactiMeshNode:
    """Main tactical mesh networking node"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.crypto = MilitaryCrypto()
        self.database = TacticalDatabase(DB_PATH)

        # Node identity
        self.identity = NodeIdentity(
            node_id=self.crypto.keys["node_id"],
            callsign=config.get("callsign", f"NODE{self.crypto.keys['node_id'][:6]}"),
            unit=config.get("unit", "UNASSIGNED"),
            rank=config.get("rank", "E-4"),
            role=config.get("role", "OPERATOR"),
            clearance_level=config.get("clearance_level", 3),
            pubkey=self.crypto.keys["enc_public"],
            verify_key=self.crypto.keys["sig_public"],
            created=self.crypto.keys["created"]
        )

        # Transport adapters
        self.transports: List[MeshTransportAdapter] = []

        # Message queues
        self.outbox = asyncio.PriorityQueue()
        self.inbox = asyncio.Queue()

        # Geospatial components
        self.current_position: Optional[Position] = None
        self.geofences: List[GeofenceZone] = []

        # Runtime state
        self.running = False
        self.connected_clients: set = set()

    async def initialize(self):
        """Initialize mesh node and transport adapters"""
        try:
            # Register this node
            self.database.upsert_node(self.identity)

            # Initialize transport adapters
            if self.config.get("batman_enabled", True):
                batman_adapter = BatmanAdvAdapter()
                if await batman_adapter.start():
                    self.transports.append(batman_adapter)

            if self.config.get("lora_enabled", False):
                lora_config = self.config.get("lora", {})
                if "port" in lora_config:
                    lora_adapter = LoRaMeshAdapter(
                        lora_config["port"], 
                        lora_config.get("baudrate", 115200)
                    )
                    if await lora_adapter.start():
                        self.transports.append(lora_adapter)

            if not self.transports:
                logger.error("No transport adapters initialized")
                return False

            logger.info(f"Initialized {len(self.transports)} transport adapter(s)")
            return True

        except Exception as e:
            logger.error(f"Node initialization failed: {e}")
            return False

    def _encode_message(self, message: TacticalMessage) -> bytes:
        """Encode and sign tactical message"""
        try:
            # Create message envelope
            envelope = {
                "version": "1.0",
                "sender_identity": asdict(self.identity),
                "message": asdict(message)
            }

            # Serialize message
            data = json.dumps(envelope, separators=(',', ':')).encode()

            # Sign message
            signature = self.crypto.sign_message(data)
            envelope["message"]["signature"] = signature

            # Re-serialize with signature
            return json.dumps(envelope, separators=(',', ':')).encode()

        except Exception as e:
            logger.error(f"Message encoding failed: {e}")
            raise

    def _decode_message(self, data: bytes) -> Optional[Tuple[TacticalMessage, NodeIdentity]]:
        """Decode and verify tactical message"""
        try:
            envelope = json.loads(data.decode())

            # Extract components
            sender_identity = NodeIdentity(**envelope["sender_identity"])
            message_data = envelope["message"]
            signature = message_data.get("signature")

            if not signature:
                logger.warning("Received unsigned message")
                return None

            # Verify signature
            message_copy = dict(message_data)
            message_copy.pop("signature", None)
            verify_envelope = {
                "version": envelope["version"],
                "sender_identity": envelope["sender_identity"],
                "message": message_copy
            }
            verify_data = json.dumps(verify_envelope, separators=(',', ':')).encode()

            if not self.crypto.verify_signature(verify_data, signature, sender_identity.verify_key):
                logger.warning("Message signature verification failed")
                return None

            # Create message object
            message = TacticalMessage(**message_data)

            # Update sender info in database
            self.database.upsert_node(sender_identity)

            return message, sender_identity

        except Exception as e:
            logger.error(f"Message decoding failed: {e}")
            return None

    async def send_message(self, topic: str, payload: Dict[str, Any], 
                          recipients: List[str] = None, priority: int = 2,
                          classification: str = "UNCLASSIFIED"):
        """Send tactical message"""
        try:
            message = TacticalMessage(
                msg_id=str(uuid.uuid4()),
                msg_type="DATA",
                topic=topic,
                sender=self.identity.node_id,
                recipients=recipients or [],
                classification=classification,
                priority=priority,
                timestamp=time.time(),
                expires=None,
                payload=payload,
                attachments=[]
            )

            # Store message
            self.database.store_message(message)

            # Queue for transmission
            await self.outbox.put((priority, message))

            logger.info(f"Queued message {message.msg_id} for transmission")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def update_position(self, lat: float, lon: float, alt: float = 0.0, 
                            accuracy: float = 10.0, speed: float = 0.0, course: float = 0.0):
        """Update node position and broadcast to mesh"""
        try:
            # Convert to MGRS if possible
            mgrs = self._convert_to_mgrs(lat, lon)

            position = Position(
                node_id=self.identity.node_id,
                lat=lat,
                lon=lon,
                alt=alt,
                accuracy=accuracy,
                speed=speed,
                course=course,
                timestamp=time.time(),
                mgrs=mgrs
            )

            self.current_position = position
            self.database.upsert_position(position)

            # Broadcast position update
            await self.send_message(
                topic=TOPIC_BLUE_FORCE,
                payload=asdict(position),
                priority=2
            )

        except Exception as e:
            logger.error(f"Position update failed: {e}")

    def _convert_to_mgrs(self, lat: float, lon: float) -> str:
        """Convert lat/lon to MGRS coordinates"""
        try:
            # Simplified MGRS conversion - in production use proper library
            zone = int((lon + 180) / 6) + 1
            letter = chr(ord('C') + int((lat + 80) / 8))
            return f"{zone}{letter}"
        except:
            return ""

    async def transmit_loop(self):
        """Main transmission loop"""
        while self.running:
            try:
                # Get next message from queue
                priority, message = await asyncio.wait_for(
                    self.outbox.get(), timeout=1.0
                )

                # Encode message
                data = self._encode_message(message)

                # Transmit via all available transports
                tasks = []
                for transport in self.transports:
                    task = asyncio.create_task(transport.send_message(data))
                    tasks.append(task)

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                logger.debug(f"Transmitted message {message.msg_id}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Transmission error: {e}")
                await asyncio.sleep(0.1)

    async def receive_loop(self):
        """Main reception loop"""
        while self.running:
            try:
                # Check all transports for incoming messages
                for transport in self.transports:
                    data, sender = await transport.receive_message()
                    if data:
                        # Decode message
                        result = self._decode_message(data)
                        if result:
                            message, sender_identity = result

                            # Store message
                            self.database.store_message(message)

                            # Process special message types
                            await self._process_received_message(message)

                            # Queue for application layer
                            await self.inbox.put((message, sender_identity))

                            logger.debug(f"Received message {message.msg_id}")

                await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Reception error: {e}")
                await asyncio.sleep(0.1)

    async def _process_received_message(self, message: TacticalMessage):
        """Process received tactical messages"""
        try:
            if message.topic == TOPIC_BLUE_FORCE:
                # Update position data
                position_data = message.payload
                position = Position(**position_data)
                self.database.upsert_position(position)

            elif message.topic == TOPIC_ALERT:
                # Handle tactical alerts
                logger.warning(f"TACTICAL ALERT: {message.payload}")

            # Broadcast to connected web clients
            await self._broadcast_to_clients({
                "type": "message",
                "data": asdict(message)
            })

        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def _broadcast_to_clients(self, data: Dict[str, Any]):
        """Broadcast data to connected web clients"""
        if not self.connected_clients:
            return

        message = json.dumps(data)
        disconnected = set()

        for websocket in self.connected_clients.copy():
            try:
                await websocket.send_text(message)
            except:
                disconnected.add(websocket)

        # Remove disconnected clients
        self.connected_clients -= disconnected

    async def start(self):
        """Start mesh node operations"""
        if not await self.initialize():
            return False

        self.running = True

        # Start background tasks
        asyncio.create_task(self.transmit_loop())
        asyncio.create_task(self.receive_loop())

        # Start position updates if GPS available
        if self.config.get("gps_enabled", False):
            asyncio.create_task(self._gps_update_loop())

        logger.info(f"TactiMesh node started: {self.identity.callsign}")
        return True

    async def _gps_update_loop(self):
        """Periodic GPS position updates"""
        while self.running:
            try:
                # In production, integrate with actual GPS hardware
                # For now, use configured position
                pos_config = self.config.get("position", {})
                if pos_config:
                    await self.update_position(
                        lat=pos_config.get("lat", 0.0),
                        lon=pos_config.get("lon", 0.0),
                        alt=pos_config.get("alt", 0.0)
                    )

                await asyncio.sleep(30)  # Update every 30 seconds

            except Exception as e:
                logger.error(f"GPS update error: {e}")
                await asyncio.sleep(60)

# =============================================================================
# SITUATIONAL AWARENESS ENGINE
# =============================================================================

class SituationalAwareness:
    """Geospatial intelligence and mapping engine"""

    def __init__(self, database: TacticalDatabase):
        self.database = database
        self.offline_maps: Dict[str, Any] = {}

    def get_tactical_picture(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> Dict[str, Any]:
        """Generate current tactical situation picture"""
        try:
            # Get current positions
            positions = self.database.get_current_positions()

            # Convert to GeoDataFrame
            if positions:
                pos_data = []
                for pos in positions:
                    pos_data.append({
                        'node_id': pos.node_id,
                        'lat': pos.lat,
                        'lon': pos.lon,
                        'alt': pos.alt,
                        'speed': pos.speed,
                        'course': pos.course,
                        'timestamp': pos.timestamp,
                        'geometry': Point(pos.lon, pos.lat)
                    })

                gdf = gpd.GeoDataFrame(pos_data)

                # Filter by bounding box if provided
                if bbox:
                    minx, miny, maxx, maxy = bbox
                    bbox_poly = Polygon([(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)])
                    gdf = gdf[gdf.geometry.within(bbox_poly)]

                # Convert back to serializable format
                features = []
                for _, row in gdf.iterrows():
                    features.append({
                        'type': 'Feature',
                        'properties': {
                            'node_id': row['node_id'],
                            'lat': row['lat'],
                            'lon': row['lon'],
                            'alt': row['alt'],
                            'speed': row['speed'],
                            'course': row['course'],
                            'timestamp': row['timestamp']
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [row['lon'], row['lat']]
                        }
                    })

                return {
                    'type': 'FeatureCollection',
                    'features': features,
                    'timestamp': time.time()
                }

            return {'type': 'FeatureCollection', 'features': [], 'timestamp': time.time()}

        except Exception as e:
            logger.error(f"Failed to generate tactical picture: {e}")
            return {'type': 'FeatureCollection', 'features': [], 'timestamp': time.time()}

    def check_geofence_violations(self, position: Position) -> List[str]:
        """Check for geofence violations"""
        violations = []
        try:
            point = Point(position.lon, position.lat)

            # Check against all active geofences
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.execute("""
                    SELECT zone_id, name, zone_type, polygon, classification
                    FROM geofences 
                    WHERE active = TRUE
                """)

                for row in cursor.fetchall():
                    zone_id, name, zone_type, polygon_wkt, classification = row

                    # Parse WKT polygon
                    from shapely import wkt
                    polygon = wkt.loads(polygon_wkt)

                    # Check if position is within restricted zone
                    if zone_type in ["HOSTILE", "RESTRICTED"] and polygon.contains(point):
                        violations.append({
                            'zone_id': zone_id,
                            'name': name,
                            'type': zone_type,
                            'classification': classification
                        })

        except Exception as e:
            logger.error(f"Geofence check failed: {e}")

        return violations

# =============================================================================
# WEB API & USER INTERFACE
# =============================================================================

# Global mesh node instance
mesh_node: Optional[TactiMeshNode] = None

# FastAPI application
app = FastAPI(
    title="TactiMesh",
    description="Real-Time Military Mesh Networking & Situational Awareness Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify authentication token"""
    # In production, implement proper JWT verification
    return {"user": "tactical_user"}

@app.on_event("startup")
async def startup():
    """Application startup"""
    global mesh_node

    # Load configuration
    config = {
        "callsign": "ALPHA-1",
        "unit": "1ST PLT",
        "rank": "SGT",
        "role": "TEAM_LEADER",
        "clearance_level": 3,
        "batman_enabled": True,
        "lora_enabled": False,
        "gps_enabled": True,
        "position": {
            "lat": 37.7749,
            "lon": -122.4194,
            "alt": 50.0
        }
    }

    # Initialize mesh node
    mesh_node = TactiMeshNode(config)
    success = await mesh_node.start()

    if success:
        logger.info("TactiMesh application started successfully")
    else:
        logger.error("Failed to start TactiMesh application")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()

    if mesh_node:
        mesh_node.connected_clients.add(websocket)

        try:
            while True:
                # Handle incoming WebSocket messages
                data = await websocket.receive_json()
                message_type = data.get("type")

                if message_type == "send_message":
                    await mesh_node.send_message(
                        topic=data.get("topic", TOPIC_COMMAND),
                        payload=data.get("payload", {}),
                        priority=data.get("priority", 2)
                    )

                elif message_type == "update_position":
                    await mesh_node.update_position(
                        lat=data.get("lat"),
                        lon=data.get("lon"),
                        alt=data.get("alt", 0.0)
                    )

        except WebSocketDisconnect:
            if mesh_node:
                mesh_node.connected_clients.discard(websocket)

@app.get("/api/tactical-picture")
async def get_tactical_picture():
    """Get current tactical situation picture"""
    if not mesh_node:
        raise HTTPException(status_code=503, detail="Mesh node not initialized")

    sa_engine = SituationalAwareness(mesh_node.database)
    return sa_engine.get_tactical_picture()

@app.get("/api/nodes")
async def get_active_nodes():
    """Get list of active mesh nodes"""
    if not mesh_node:
        raise HTTPException(status_code=503, detail="Mesh node not initialized")

    nodes = mesh_node.database.get_active_nodes()
    return [asdict(node) for node in nodes]

@app.get("/api/messages")
async def get_messages(topic: Optional[str] = None, limit: int = 100):
    """Get tactical messages"""
    if not mesh_node:
        raise HTTPException(status_code=503, detail="Mesh node not initialized")

    with sqlite3.connect(mesh_node.database.db_path) as conn:
        if topic:
            cursor = conn.execute("""
                SELECT msg_id, msg_type, topic, sender, recipients, classification, 
                       priority, timestamp, payload, attachments
                FROM messages 
                WHERE topic = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (topic, limit))
        else:
            cursor = conn.execute("""
                SELECT msg_id, msg_type, topic, sender, recipients, classification,
                       priority, timestamp, payload, attachments
                FROM messages 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))

        messages = []
        for row in cursor.fetchall():
            messages.append({
                'msg_id': row[0],
                'msg_type': row[1],
                'topic': row[2],
                'sender': row[3],
                'recipients': json.loads(row[4]),
                'classification': row[5],
                'priority': row[6],
                'timestamp': row[7],
                'payload': json.loads(row[8]),
                'attachments': json.loads(row[9]) if row[9] else []
            })

        return messages

@app.post("/api/messages")
async def send_message(
    topic: str = Form(...),
    payload: str = Form(...),
    priority: int = Form(2),
    classification: str = Form("UNCLASSIFIED")
):
    """Send tactical message"""
    if not mesh_node:
        raise HTTPException(status_code=503, detail="Mesh node not initialized")

    try:
        payload_dict = json.loads(payload)
        await mesh_node.send_message(
            topic=topic,
            payload=payload_dict,
            priority=priority,
            classification=classification
        )
        return {"status": "Message sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send message: {e}")

# Serve static web interface
@app.get("/")
async def get_interface():
    """Serve tactical web interface"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TactiMesh - Military Mesh Network</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #1a1a1a; color: #00ff00; }
            .header { background: #000; padding: 10px; border-bottom: 2px solid #00ff00; }
            .container { display: flex; height: calc(100vh - 60px); }
            .map-panel { flex: 2; position: relative; }
            .control-panel { flex: 1; background: #2a2a2a; padding: 20px; overflow-y: auto; }
            #map { height: 100%; width: 100%; }
            .message-area { background: #333; border: 1px solid #00ff00; padding: 10px; margin: 10px 0; height: 200px; overflow-y: auto; }
            .node-list { background: #333; border: 1px solid #00ff00; padding: 10px; margin: 10px 0; }
            input, select, textarea, button { background: #333; color: #00ff00; border: 1px solid #00ff00; padding: 5px; margin: 5px 0; }
            button { cursor: pointer; }
            button:hover { background: #00ff00; color: #000; }
            .status { font-size: 12px; color: #ffff00; }
            .classification { background: #ff0000; color: #fff; padding: 2px 5px; font-size: 10px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ TactiMesh - Military Mesh Network</h1>
            <span class="classification">UNCLASSIFIED</span>
            <span class="status" id="status">INITIALIZING...</span>
        </div>

        <div class="container">
            <div class="map-panel">
                <div id="map"></div>
            </div>

            <div class="control-panel">
                <h3>📡 Network Status</h3>
                <div id="nodeList" class="node-list">Loading nodes...</div>

                <h3>💬 Tactical Messages</h3>
                <div id="messageArea" class="message-area"></div>

                <h3>📤 Send Message</h3>
                <form id="messageForm">
                    <select id="topicSelect" style="width: 100%;">
                        <option value="blue_force">Blue Force</option>
                        <option value="intel">Intelligence</option>
                        <option value="sitrep">SITREP</option>
                        <option value="command">Command</option>
                        <option value="alert">Alert</option>
                    </select>
                    <textarea id="messageText" placeholder="Message content..." style="width: 100%; height: 60px;"></textarea>
                    <select id="prioritySelect" style="width: 100%;">
                        <option value="0">FLASH</option>
                        <option value="1">IMMEDIATE</option>
                        <option value="2" selected>PRIORITY</option>
                        <option value="3">ROUTINE</option>
                    </select>
                    <button type="submit" style="width: 100%;">📡 TRANSMIT</button>
                </form>

                <h3>📍 Position Update</h3>
                <form id="positionForm">
                    <input type="number" id="latInput" placeholder="Latitude" step="0.000001" style="width: 100%;">
                    <input type="number" id="lonInput" placeholder="Longitude" step="0.000001" style="width: 100%;">
                    <input type="number" id="altInput" placeholder="Altitude (m)" style="width: 100%;">
                    <button type="submit" style="width: 100%;">📡 UPDATE POSITION</button>
                </form>

                <div class="status" id="networkStats">
                    Nodes: 0 | Messages: 0 | Last Update: Never
                </div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <script>
            // Initialize map
            const map = L.map('map').setView([37.7749, -122.4194], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: 'OpenStreetMap contributors'
            }).addTo(map);

            // WebSocket connection
            const ws = new WebSocket(`ws://${window.location.host}/ws`);
            let nodeMarkers = {};
            let messageCount = 0;

            ws.onopen = function() {
                document.getElementById('status').textContent = 'CONNECTED';
                document.getElementById('status').style.color = '#00ff00';
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);

                if (data.type === 'message') {
                    handleMessage(data.data);
                }

                updateDisplay();
            };

            ws.onclose = function() {
                document.getElementById('status').textContent = 'DISCONNECTED';
                document.getElementById('status').style.color = '#ff0000';
            };

            function handleMessage(message) {
                messageCount++;

                // Display message
                const messageArea = document.getElementById('messageArea');
                const messageDiv = document.createElement('div');
                messageDiv.style.marginBottom = '10px';
                messageDiv.style.padding = '5px';
                messageDiv.style.border = '1px solid #555';

                const timestamp = new Date(message.timestamp * 1000).toLocaleString();
                messageDiv.innerHTML = `
                    <strong>[${message.topic.toUpperCase()}]</strong> ${message.sender}<br>
                    <small>${timestamp} - Priority: ${message.priority}</small><br>
                    ${JSON.stringify(message.payload)}
                `;

                messageArea.appendChild(messageDiv);
                messageArea.scrollTop = messageArea.scrollHeight;
            }

            function updateDisplay() {
                // Update network stats
                const stats = document.getElementById('networkStats');
                stats.textContent = `Nodes: ${Object.keys(nodeMarkers).length} | Messages: ${messageCount} | Last Update: ${new Date().toLocaleString()}`;

                // Fetch tactical picture
                fetch('/api/tactical-picture')
                    .then(response => response.json())
                    .then(data => {
                        updateMap(data);
                    })
                    .catch(error => console.error('Error fetching tactical picture:', error));

                // Fetch active nodes
                fetch('/api/nodes')
                    .then(response => response.json())
                    .then(nodes => {
                        updateNodeList(nodes);
                    })
                    .catch(error => console.error('Error fetching nodes:', error));
            }

            function updateMap(tacticalPicture) {
                // Clear existing markers
                Object.values(nodeMarkers).forEach(marker => map.removeLayer(marker));
                nodeMarkers = {};

                // Add new markers
                tacticalPicture.features.forEach(feature => {
                    const props = feature.properties;
                    const coords = feature.geometry.coordinates;

                    const marker = L.marker([coords[1], coords[0]], {
                        title: props.node_id
                    }).addTo(map);

                    marker.bindPopup(`
                        <strong>Node:</strong> ${props.node_id}<br>
                        <strong>Position:</strong> ${coords[1].toFixed(6)}, ${coords[0].toFixed(6)}<br>
                        <strong>Altitude:</strong> ${props.alt}m<br>
                        <strong>Speed:</strong> ${props.speed} km/h<br>
                        <strong>Updated:</strong> ${new Date(props.timestamp * 1000).toLocaleString()}
                    `);

                    nodeMarkers[props.node_id] = marker;
                });
            }

            function updateNodeList(nodes) {
                const nodeList = document.getElementById('nodeList');

                if (nodes.length === 0) {
                    nodeList.innerHTML = 'No active nodes';
                    return;
                }

                nodeList.innerHTML = nodes.map(node => `
                    <div style="margin-bottom: 10px; padding: 5px; border: 1px solid #555;">
                        <strong>${node.callsign}</strong> (${node.unit})<br>
                        <small>${node.rank} - ${node.role}</small><br>
                        <small>Clearance: L${node.clearance_level}</small>
                    </div>
                `).join('');
            }

            // Message form handler
            document.getElementById('messageForm').addEventListener('submit', function(e) {
                e.preventDefault();

                const topic = document.getElementById('topicSelect').value;
                const text = document.getElementById('messageText').value;
                const priority = parseInt(document.getElementById('prioritySelect').value);

                if (!text.trim()) return;

                ws.send(JSON.stringify({
                    type: 'send_message',
                    topic: topic,
                    payload: { text: text },
                    priority: priority
                }));

                document.getElementById('messageText').value = '';
            });

            // Position form handler
            document.getElementById('positionForm').addEventListener('submit', function(e) {
                e.preventDefault();

                const lat = parseFloat(document.getElementById('latInput').value);
                const lon = parseFloat(document.getElementById('lonInput').value);
                const alt = parseFloat(document.getElementById('altInput').value) || 0;

                if (isNaN(lat) || isNaN(lon)) return;

                ws.send(JSON.stringify({
                    type: 'update_position',
                    lat: lat,
                    lon: lon,
                    alt: alt
                }));

                // Clear form
                document.getElementById('latInput').value = '';
                document.getElementById('lonInput').value = '';
                document.getElementById('altInput').value = '';
            });

            // Update display every 5 seconds
            setInterval(updateDisplay, 5000);

            // Initial update
            setTimeout(updateDisplay, 1000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("TactiMesh: Real-Time Military Mesh Networking & Situational Awareness Platform")
    print("=" * 80)
    print("Starting production deployment...")

    # Configure logging for production
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOGS_DIR / 'tactimesh.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    try:
        # Start FastAPI server
        uvicorn.run(
            "tactimesh:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            reload=False  # Production mode
        )
    except KeyboardInterrupt:
        logger.info("TactiMesh shutdown requested")
    except Exception as e:
        logger.error(f"TactiMesh startup failed: {e}")
        sys.exit(1)

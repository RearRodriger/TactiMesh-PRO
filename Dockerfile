FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    sqlite3 \
    batctl \
    iw \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd -r -m -s /bin/bash tactimesh

# Create application directory
WORKDIR /opt/tactimesh

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN python3 -m venv venv && \
    venv/bin/pip install --upgrade pip && \
    venv/bin/pip install -r requirements.txt

# Copy application files
COPY tactimesh.py .
COPY config.json .

# Set ownership
RUN chown -R tactimesh:tactimesh /opt/tactimesh

# Switch to application user
USER tactimesh

# Expose ports
EXPOSE 8000 47474/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/nodes || exit 1

# Start application
CMD ["venv/bin/python", "tactimesh.py"]

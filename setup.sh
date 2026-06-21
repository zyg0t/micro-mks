#!/bin/bash
# Define paths
DIR="/root/mks-robin"
SERVICE_FILE="/etc/systemd/system/mks-robin.service"

# Check if the service file exists
if [ -f "$SERVICE_FILE" ]; then
    echo "Service found. Uninstalling..."
    systemctl stop mks-robin
    systemctl disable mks-robin
    rm -f "$SERVICE_FILE"
    rm -rf "$DIR"
    systemctl daemon-reload
    echo "Uninstalled."
else
    echo "Installing..."
    # Ensure directory exists and clone
    mkdir -p "$DIR"
    git clone https://github.com/zyg0t/micro-mks.git "$DIR"
    pip3 install -r "$DIR/requirements.txt" --break-system-packages

    # Create service file
    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=MKS Robin Backend
After=network.target

[Service]
ExecStart=/usr/bin/python3 $DIR/app.py
WorkingDirectory=$DIR
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

    # Reload and start
    systemctl daemon-reload
    systemctl enable --now mks-robin
    echo "Installation complete. Service is running."
fi

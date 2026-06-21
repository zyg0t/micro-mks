#!/bin/bash
INSTALL_DIR="/opt/mks-robin"
SERVICE_NAME="mks-robin"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME.service"

if [ -f "$SERVICE_PATH" ]; then
    echo "Existing installation found. Uninstalling..."
    sudo systemctl stop $SERVICE_NAME 2>/dev/null
    sudo systemctl disable $SERVICE_NAME 2>/dev/null
    sudo rm "$SERVICE_PATH"
    sudo rm -rf "$INSTALL_DIR"
    sudo systemctl daemon-reload
    echo "Uninstalled successfully."
else
    echo "Installing..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo git clone https://github.com/zyg0t/micro-mks.git "$INSTALL_DIR"
    sudo pip3 install -r "$INSTALL_DIR/requirements.txt" --break-system-packages
    
    read -p "Add to startup? (y/n) " choice
    if [[ "$choice" == "y" ]]; then
        cat <<EOF | sudo tee "$SERVICE_PATH"
[Unit]
Description=MKS Robin Backend
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/app.py
WorkingDirectory=$INSTALL_DIR
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable --now $SERVICE_NAME
        echo "Service installed and started."
    fi
fi

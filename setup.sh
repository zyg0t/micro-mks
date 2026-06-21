#!/bin/bash
REPO_URL="https://github.com/zyg0t/micro-mks.git"
INSTALL_DIR="$HOME/mks-robin"
SERVICE_NAME="mks-robin"

if [ -d "$INSTALL_DIR" ]; then
    echo "Existing installation found. Uninstalling..."
    sudo systemctl stop $SERVICE_NAME && sudo systemctl disable $SERVICE_NAME
    sudo rm "/etc/systemd/system/$SERVICE_NAME.service"
    rm -rf "$INSTALL_DIR"
    echo "Uninstalled successfully."
else
    git clone $REPO_URL $INSTALL_DIR && cd $INSTALL_DIR
    pip install -r requirements.txt
    read -p "Add to startup? (y/n) " choice
    if [[ "$choice" == "y" ]]; then
        cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=MKS Robin Backend
After=network.target
[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/app.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl enable --now $SERVICE_NAME
    fi
fi

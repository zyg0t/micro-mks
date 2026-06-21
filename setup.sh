#!/bin/bash
DIR="/root/mks-robin"
SERVICE="/etc/systemd/system/mks-robin.service"

if [ -f "$SERVICE" ]; then
    echo "Uninstalling service..."
    sudo systemctl stop mks-robin && sudo systemctl disable mks-robin
    sudo rm "$SERVICE"
    sudo rm -rf "$DIR"
    sudo systemctl daemon-reload
    echo "Done. Uninstalled."
else
    echo "Installing..."
    sudo apt-get update && sudo apt-get install -y git python3-pip
    sudo git clone https://github.com/zyg0t/micro-mks.git "$DIR"
    sudo pip3 install -r "$DIR/requirements.txt" --break-system-packages
    
    sudo bash -c "cat > $SERVICE <<EOF
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
EOF"
    
    sudo systemctl daemon-reload
    sudo systemctl enable --now mks-robin
    echo "Installed and running!"
fi

#!/bin/bash

# Deepseek Chat Assistant Installer
echo "Installing Deepseek Chat Assistant..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Get username of the user who ran sudo
REAL_USER=$(logname || echo $SUDO_USER)
USER_HOME=$(eval echo ~$REAL_USER)

# Install dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3-pip python3-venv libnotify-bin

# Create installation directory
INSTALL_DIR="/opt/deepseek-chat"
mkdir -p $INSTALL_DIR

# Copy files to installation directory
echo "Copying files to $INSTALL_DIR..."
cp -r ./* $INSTALL_DIR/

# Set permissions
chown -R $REAL_USER:$REAL_USER $INSTALL_DIR

# Create virtual environment
echo "Setting up Python environment..."
sudo -u $REAL_USER python3 -m venv $INSTALL_DIR/venv
sudo -u $REAL_USER $INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt

# Update launch script to use venv
cat > $INSTALL_DIR/launch.sh << EOL
#!/bin/bash
# export DEEPSEEK_API_KEY=
# export GOOGLE_API_KEY=
# export GOOGLE_CSE_ID=

# Activate virtual environment
source $INSTALL_DIR/venv/bin/activate

# Start the application
cd $INSTALL_DIR
streamlit run app.py
EOL

chmod +x $INSTALL_DIR/launch.sh

# Install systemd service
echo "Installing systemd service..."
cat > /etc/systemd/system/deepseek-chat.service << EOL
[Unit]
Description=Deepseek Chat Assistant
After=network.target

[Service]
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/bin/bash $INSTALL_DIR/launch.sh
Restart=on-failure
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOL

# Install desktop entry
echo "Creating desktop shortcut..."
cat > $USER_HOME/.local/share/applications/deepseek-chat.desktop << EOL
[Desktop Entry]
Name=Deepseek Chat
Comment=AI Assistant powered by Deepseek
Exec=xdg-open http://localhost:8501
Terminal=false
Type=Application
Categories=Utility;
EOL

# Enable and start the service
systemctl daemon-reload
systemctl enable deepseek-chat.service
systemctl start deepseek-chat.service

echo "Installation complete!"
echo "Deepseek Chat Assistant is now running as a system service."
echo "You can access it by clicking the desktop icon or visiting http://localhost:8501"
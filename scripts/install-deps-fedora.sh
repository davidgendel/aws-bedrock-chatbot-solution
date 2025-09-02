#!/bin/bash
set -e

echo "Installing dependencies for GenAI Chatbot on Fedora..."

# Update package list
sudo dnf update -y

# Install Git
echo "Installing Git..."
sudo dnf install -y git

# Install Docker
echo "Installing Docker..."
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Install AWS CLI
echo "Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo dnf install -y unzip
unzip awscliv2.zip
sudo ./aws/install --update
rm -rf aws awscliv2.zip

# Install pyenv dependencies and pyenv
echo "Installing Python 3.12+ via pyenv..."
sudo dnf install -y make gcc zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel
curl https://pyenv.run | bash

# Add pyenv to PATH
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.12
pyenv install 3.12.0
pyenv global 3.12.0

# Install nvm and Node.js 22
echo "Installing Node.js 22+ via nvm..."
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 22
nvm use 22
nvm alias default 22

echo "Installation complete!"
echo "Please run 'source ~/.bashrc' or restart your terminal to ensure all PATH changes take effect."
echo "You may need to log out and back in for Docker group membership to take effect."

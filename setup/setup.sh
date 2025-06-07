#!/bin/bash

# Exit on error
set -e

# Update system
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install required packages
echo "Installing required packages..."
sudo apt install -y \
python3-pyaudio \
python3-dev \
portaudio19-dev
# TODO: add packages

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create config directory
echo "Setting up configuration..."
sudo mkdir -p /boot/firmware

# Create config.txt
sudo cp ./setup/boot/firmware/config.txt /boot/firmware/config.txt
sudo cp ./setup/boot/firmware/cmdline.txt /boot/firmware/cmdline.txt

# Make scripts executable
chmod +x *.py

echo "Hai!"

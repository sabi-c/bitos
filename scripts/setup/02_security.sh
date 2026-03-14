#!/bin/bash
set -euo pipefail

# Firewall: deny all inbound except Tailscale and LAN
sudo apt-get install -y ufw fail2ban
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow in on tailscale0
# Adjust subnet if home network differs — check with: ip route
sudo ufw allow from 192.168.0.0/16
sudo ufw --force enable

# fail2ban for SSH brute force protection
sudo bash -c 'cat > /etc/fail2ban/jail.local << EOF
[sshd]
enabled = true
maxretry = 3
bantime = 3600
findtime = 600
EOF'
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

# SSH hardening — keys only, no passwords
sudo bash -c 'cat > /etc/ssh/sshd_config.d/bitos.conf << EOF
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 20
EOF'
sudo systemctl restart sshd

echo "SECURITY HARDENING COMPLETE"
echo "Verify: sudo ufw status verbose"
echo "Verify: sudo fail2ban-client status sshd"

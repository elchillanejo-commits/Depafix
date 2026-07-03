#!/bin/bash
VPS_IP="${1}"
[ -z "$VPS_IP" ] && echo "Uso: $0 <IP_VPS>" && exit 1
ssh ubuntu@$VPS_IP "sudo apt update -qq && sudo apt install -y certbot python3-certbot-nginx && sudo certbot --nginx -d gestalt.cl -d www.gestalt.cl --non-interactive --agree-tos --email depafix@gmail.com && echo '0 3 * * * certbot renew --quiet' | crontab -"
echo "✅ SSL configurado"

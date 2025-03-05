#!/bin/bash

# Replace these variables with your values
domains=(smm.bishalbudhathoki.engineer www.smm.bishalbudhathoki.engineer)
email="bishalkc331@gmail.com" # Adding a valid address is strongly recommended
staging=1 # Set to 1 if you're testing your setup to avoid hitting request limits

# Create directories for certbot
mkdir -p certbot/conf certbot/www

# Stop nginx if it's running
docker-compose down

# Delete any existing certificates (be careful with this in production)
rm -rf certbot/conf/*

# Download recommended TLS parameters
curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > certbot/conf/options-ssl-nginx.conf
curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > certbot/conf/ssl-dhparams.pem

# Start nginx
docker-compose up --force-recreate -d nginx

# Select appropriate email arg
case "$email" in
  "") email_arg="--register-unsafely-without-email" ;;
  *) email_arg="--email $email" ;;
esac

# Enable staging mode if needed
if [ $staging != "0" ]; then staging_arg="--staging"; fi

# Get certificates
docker-compose run --rm certbot certonly --webroot -w /var/www/certbot \
  $staging_arg \
  $email_arg \
  -d ${domains[0]} -d ${domains[1]} \
  --rsa-key-size 4096 \
  --agree-tos \
  --force-renewal

# Reload nginx
docker-compose exec nginx nginx -s reload 
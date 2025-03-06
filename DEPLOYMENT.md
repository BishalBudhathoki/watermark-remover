# Deployment Guide

This guide covers the deployment of the Social Media Manager application using Docker, Nginx, SSL certificates, and Celery.

## Prerequisites

- Ubuntu server (Oracle Cloud Instance)
- Domain name pointing to your server (smm.bishalbudhathoki.engineer)
- Docker and Docker Compose installed

## 1. Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common \
    git \
    ufw

# Configure firewall
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw allow 9000  # Portainer HTTP
sudo ufw allow 9443  # Portainer HTTPS
sudo ufw enable
```

## 2. Project Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd watermark-remover

# Create necessary directories
mkdir -p certbot/conf/live/smm.bishalbudhathoki.engineer
mkdir -p certbot/www
mkdir -p uploads processed downloads

# Set proper permissions
chmod -R 755 uploads processed downloads
```

## 3. Configuration Files

### 3.1 Environment Variables (.env)
```bash
# Copy example env file
cp .env.example .env

# Edit .env file with your credentials
nano .env
```

### 3.2 Docker Compose Configuration
File: `docker-compose.yml`
- Web service (Flask application)
- Redis for caching
- Celery for background tasks
- Nginx as reverse proxy
- Certbot for SSL
- Portainer for container management

### 3.3 Nginx Configuration
File: `nginx.conf`
- SSL configuration
- Proxy settings
- Static file serving
- Security headers

## 4. SSL Certificate Setup

```bash
# Make the initialization script executable
chmod +x init-letsencrypt.sh

# Run the script in staging mode first
./init-letsencrypt.sh

# If successful, edit the script
nano init-letsencrypt.sh
# Change staging=1 to staging=0

# Run again for real certificates
./init-letsencrypt.sh
```

## 5. Docker Deployment

```bash
# Build and start containers
docker-compose up -d --build

# Verify containers are running
docker ps

# Check logs
docker-compose logs -f
```

## 6. Service URLs

- Main Application: https://smm.bishalbudhathoki.engineer
- Portainer: https://smm.bishalbudhathoki.engineer/portainer/

## 7. Celery Configuration

Celery is configured with:
- Redis as message broker
- 4 worker processes
- Automatic task retry on failure
- Periodic task scheduling with celery-beat

## 8. Monitoring and Maintenance

### 8.1 Check Service Status
```bash
# Check all containers
docker-compose ps

# Check specific service logs
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f nginx
```

### 8.2 SSL Certificate Renewal
Certificates auto-renew via the certbot container. To manually renew:
```bash
docker-compose run --rm certbot renew
```

### 8.3 Backup Important Data
```bash
# Backup environment variables
cp .env .env.backup

# Backup SSL certificates
tar -czf certbot-backup.tar.gz certbot/
```

## 9. Common Issues and Solutions

### 9.1 SSL Certificate Issues
- Check domain DNS settings
- Verify Nginx configuration
- Check certbot logs: `docker-compose logs certbot`

### 9.2 Application Not Accessible
- Check container status: `docker-compose ps`
- Verify Nginx logs: `docker-compose logs nginx`
- Check firewall settings: `sudo ufw status`

### 9.3 Celery Tasks Not Processing
- Check Redis connection: `docker-compose logs redis`
- Verify Celery workers: `docker-compose logs celery`
- Check task queue status in Flower dashboard

## 10. Security Considerations

1. Environment Variables:
   - Keep `.env` file secure
   - Regular rotation of API keys
   - Use strong passwords

2. SSL/TLS:
   - Regular certificate renewal
   - Modern TLS configuration
   - HSTS enabled

3. Docker:
   - Regular image updates
   - Non-root user in containers
   - Limited container permissions

4. Nginx:
   - Security headers configured
   - Rate limiting enabled
   - Request size limits

## 11. Scaling Considerations

1. Horizontal Scaling:
   - Add more Celery workers
   - Configure load balancing
   - Implement caching

2. Vertical Scaling:
   - Increase container resources
   - Optimize application code
   - Monitor resource usage

## 12. Backup and Recovery

1. Regular Backups:
   - Environment variables
   - SSL certificates
   - Application data
   - Database dumps

2. Recovery Procedures:
   - Restore from backups
   - Rebuild containers
   - Verify functionality

## 13. Monitoring

1. Application Monitoring:
   - Container metrics
   - Application logs
   - Error tracking

2. System Monitoring:
   - Resource usage
   - Network traffic
   - Disk space

## 14. Useful Commands

```bash
# Restart all services
docker-compose restart

# Rebuild specific service
docker-compose up -d --build web

# View real-time logs
docker-compose logs -f

# Check resource usage
docker stats

# Stop all services
docker-compose down

# Remove all containers and volumes
docker-compose down -v
``` 
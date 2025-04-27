# Social Media Manager

A comprehensive social media management tool that helps automate content creation, scheduling, and posting across multiple platforms including Instagram, TikTok, and YouTube.

## Features

- Multi-platform social media integration (Instagram, TikTok, YouTube)
- Content scheduling and automation
- Media processing and watermark removal
- Secure OAuth2 authentication
- Docker containerization
- SSL/TLS support with Let's Encrypt
- Redis-based task queue with Celery
- Nginx reverse proxy

## Prerequisites

- Docker and Docker Compose
- Domain name with DNS configured
- Social media platform developer accounts:
  - Facebook/Instagram Business Account
  - TikTok Developer Account
  - Google Developer Account

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/watermark-remover.git
cd watermark-remover
```

2. Create environment file:
```bash
cp .env.example .env.prod
# Edit .env.prod with your credentials
```

3. Initialize SSL certificates:
```bash
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

4. Start the application:
```bash
docker-compose up -d
```

## Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your development credentials
```

4. Run the development server:
```bash
flask run
```

## Production Deployment

1. Configure your domain's DNS settings:
```
A Record: your-domain.com -> Your Server IP
A Record: www.your-domain.com -> Your Server IP
```

2. Update social media OAuth redirect URIs:
- Instagram: https://your-domain.com/social-auth/callback/instagram
- TikTok: https://your-domain.com/social-auth/callback/tiktok
- YouTube: https://your-domain.com/social-auth/callback/youtube

3. Deploy with Docker Compose:
```bash
docker-compose -f docker-compose.yml up -d
```

## Environment Variables

See `.env.example` for all required environment variables.

## Security

- All sensitive credentials should be stored in `.env.prod`
- Never commit `.env` files to version control
- Keep SSL certificates and private keys secure
- Regularly update dependencies and Docker images

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [MoviePy](https://zulko.github.io/moviepy/) for video processing
- [OpenAI](https://openai.com/) for text generation
- Various social media platform APIs

# Watermark Remover - Production Deployment Guide

This repository contains a production-ready Docker Compose setup for the Watermark Remover application, featuring Flask, Nginx, Certbot, Redis, and Celery.

## Architecture

The application uses the following components:
- Flask application server
- Nginx as reverse proxy with SSL termination
- Redis as message broker and caching
- Celery for background task processing
- Certbot for SSL certificate management

## Prerequisites

- Docker and Docker Compose installed
- Domain name pointed to your server (A record for smm.bishalbudhathoki.engineer)
- Open ports 80 and 443 on your firewall

## Directory Structure

```
.
├── app/                    # Flask application code
├── nginx/                  # Nginx configuration
│   └── conf.d/            # Nginx site configurations
├── certbot/               # SSL certificates and configuration
│   ├── conf/              # Let's Encrypt configuration
│   └── www/              # ACME challenge files
├── redis/                # Redis data directory
│   └── data/            # Persistent Redis data
├── logs/                 # Application logs
│   ├── nginx/           # Nginx logs
│   ├── flask/           # Flask application logs
│   └── celery/          # Celery worker logs
├── docker-compose.yml    # Docker Compose configuration
├── .env                 # Environment variables
└── init-letsencrypt.sh  # SSL certificate initialization script
```

## Initial Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd watermark-remover
   ```

2. Create required directories:
   ```bash
   mkdir -p nginx/conf.d certbot/conf certbot/www redis/data logs/{nginx,flask,celery}
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Initialize SSL certificates:
   ```bash
   chmod +x init-letsencrypt.sh
   ./init-letsencrypt.sh
   ```

## Deployment

1. Start the application:
   ```bash
   docker-compose up -d
   ```

2. Verify all services are running:
   ```bash
   docker-compose ps
   ```

3. Check the health endpoint:
   ```bash
   curl https://smm.bishalbudhathoki.engineer/health
   ```

## Scaling

To scale the Flask application horizontally:
```bash
docker-compose up -d --scale flask=3
```

## Monitoring

- View logs:
  ```bash
  # All logs
  docker-compose logs -f

  # Specific service
  docker-compose logs -f flask
  ```

- Monitor containers:
  ```bash
  docker stats
  ```

## SSL Certificate Renewal

Certificates are automatically renewed by the Certbot container. To manually renew:
```bash
docker-compose run --rm certbot renew
```

## Maintenance

1. Update containers:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

2. Backup Redis data:
   ```bash
   docker-compose exec redis redis-cli SAVE
   ```

3. Clean up old containers and images:
   ```bash
   docker-compose down
   docker system prune
   ```

## Troubleshooting

1. Check service health:
   ```bash
   curl https://smm.bishalbudhathoki.engineer/health
   ```

2. View logs:
   ```bash
   tail -f logs/flask/app.log
   tail -f logs/nginx/error.log
   tail -f logs/celery/tasks.log
   ```

3. Restart services:
   ```bash
   docker-compose restart flask
   docker-compose restart celery_worker
   ```

## Security Best Practices

1. Keep Docker and all packages updated
2. Use non-root users in containers
3. Implement rate limiting in Nginx
4. Regular security audits
5. Monitor logs for suspicious activity
6. Keep backups of Redis data
7. Use secure passwords and API keys

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

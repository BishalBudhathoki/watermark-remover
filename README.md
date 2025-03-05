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

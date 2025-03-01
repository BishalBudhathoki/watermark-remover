# VideoVault - Professional Video Management Platform

VideoVault is a powerful SaaS platform for downloading, processing, and managing videos from various social media platforms. Built with Python/Flask and modern web technologies, it offers a seamless experience for video content management.

## 🚀 Features

### Core Functionality
- **Multi-Platform Support**
  - Instagram Reels & Posts
  - TikTok Videos
  - YouTube Shorts
  - More platforms coming soon

### Video Processing
- **Watermark Removal**
  - AI-powered watermark detection
  - Clean removal without quality loss
  - Batch processing support

- **Video Enhancement**
  - Quality optimization
  - Format conversion
  - Custom resolution support

### User Management
- **Secure Authentication**
  - Email verification
  - Social login (Google, GitHub)
  - Password recovery

- **User Dashboard**
  - Download history
  - Processing status
  - Usage statistics

### API Integration
- **RESTful API**
  - Comprehensive endpoints
  - API key authentication
  - Rate limiting
  - Usage monitoring

## 🛠 Technology Stack

### Backend
- Python 3.8+
- Flask web framework
- Supabase (Authentication & Database)
- Redis (Caching & Rate Limiting)
- Celery (Background Tasks)

### Frontend
- HTML5/CSS3
- Tailwind CSS
- JavaScript (ES6+)
- Font Awesome Icons

### Infrastructure
- Docker containerization
- Gunicorn WSGI server
- Nginx reverse proxy
- SSL/TLS encryption

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/BishalBudhathoki/watermark-remover.git
   cd watermark-remover
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize the database**
   ```bash
   flask db upgrade
   ```

## 🔧 Configuration

### Required Environment Variables
```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
REDIS_URL=redis://localhost:6379
```

### Optional Features
```env
GOOGLE_CLIENT_ID=your-google-client-id
GITHUB_CLIENT_ID=your-github-client-id
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-password
```

## 🚀 Deployment

### Local Development Workflow
1. **Setup Development Environment**
   ```bash
   # Clone and setup as described in Installation section
   ./git-deploy.sh --help  # View deployment script options
   ```

2. **Development Workflow**
   - Create feature branch:
     ```bash
     ./git-deploy.sh -b feature/new-feature "Initial commit for new feature"
     ```
   - Make changes and commit:
     ```bash
     ./git-deploy.sh "Update feature implementation"
     ```
   - Create release:
     ```bash
     ./git-deploy.sh -b main -t v1.0.0 --backup "Release version 1.0.0"
     ```

3. **Pre-commit Hooks**
   The repository includes pre-commit hooks that:
   - Check Python syntax
   - Run code formatting
   - Detect sensitive data
   - Run tests
   - Validate commit messages

4. **Pre-push Checks**
   Before pushing to protected branches:
   - Runs comprehensive test suite
   - Checks for large files
   - Performs security scans
   - Validates development settings

### Docker Deployment
1. **Build the Docker image**
   ```bash
   docker build -t videovault .
   ```

2. **Run the container**
   ```bash
   docker run -p 5000:5000 videovault
   ```

### Production Deployment

1. **Preparation**
   ```bash
   # Create deployment configuration
   cp .env.example .env.production
   # Edit production environment variables
   nano .env.production
   ```

2. **Database Setup**
   ```bash
   # Backup existing database
   flask db-tools backup
   
   # Apply migrations
   flask db upgrade
   ```

3. **Static Files**
   ```bash
   # Collect and optimize static files
   flask static collect
   flask static optimize
   ```

4. **SSL/TLS Setup**
   ```bash
   # Generate SSL certificate using Let's Encrypt
   sudo certbot --nginx -d yourdomain.com
   ```

5. **Application Deployment**
   ```bash
   # Using the deployment script
   ./git-deploy.sh -b production --backup "Production release v1.0.0"
   
   # Or manual deployment
   git checkout production
   git pull origin production
   sudo systemctl restart videovault
   ```

6. **Post-Deployment**
   - Verify application status
   - Check error logs
   - Monitor performance
   - Test critical features

### Continuous Integration

The repository is configured with:
- GitHub Actions for automated testing
- CodeQL for security analysis
- Dependabot for dependency updates
- Automated docker builds

### Rollback Procedures

1. **Quick Rollback**
   ```bash
   # Revert to previous version
   git revert HEAD
   ./git-deploy.sh "Revert to previous version"
   ```

2. **Version Rollback**
   ```bash
   # Rollback to specific tag
   ./git-deploy.sh -b main -t v0.9.0 --backup "Rollback to v0.9.0"
   ```

3. **Database Rollback**
   ```bash
   # Revert last migration
   flask db downgrade
   ```

### Monitoring & Maintenance

1. **Health Checks**
   ```bash
   # Check application status
   flask health-check
   
   # View logs
   flask logs --tail 100
   ```

2. **Backup Schedule**
   ```bash
   # Manual backup
   ./git-deploy.sh --backup "Pre-maintenance backup"
   
   # Automated backups are configured in crontab
   0 2 * * * /path/to/backup-script.sh
   ```

3. **Performance Monitoring**
   - Application metrics dashboard
   - Resource usage alerts
   - Error rate monitoring
   - Response time tracking

## 📈 API Documentation

### Authentication
```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
```

### Video Operations
```http
POST /api/v1/videos/download
POST /api/v1/videos/process
GET /api/v1/videos/status/:id
```

### User Management
```http
GET /api/v1/user/profile
PUT /api/v1/user/settings
GET /api/v1/user/usage
```

## 🔒 Security Features

- CSRF protection
- Rate limiting
- Input sanitization
- XSS prevention
- SQL injection protection
- Secure session handling

## 📊 Monitoring & Analytics

- Request logging
- Error tracking
- Performance monitoring
- User analytics
- API usage statistics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Documentation: [docs.videovault.com](https://docs.videovault.com)
- Email: support@videovault.com
- Discord: [VideoVault Community](https://discord.gg/videovault)

## 🙏 Acknowledgments

- [Flask](https://flask.palletsprojects.com/)
- [Supabase](https://supabase.io/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Font Awesome](https://fontawesome.com/)

## 🏃‍♂️ Running the Application

### Using Python

1. **Start the Development Server**
   After setting up your environment and installing dependencies, you can run the application using the following command:

   ```bash
   python app.py
   ```

   This will start the Flask development server, and you can access the application at `http://127.0.0.1:5000/`.

### Using Docker

1. **Build the Docker Image**
   If you prefer to run the application in a Docker container, first build the Docker image using the following command:

   ```bash
   docker build -t videovault .
   ```

2. **Run the Docker Container**
   After building the image, you can run the container with the following command:

   ```bash
   docker run -p 5000:5000 videovault
   ```

   This command maps port 5000 of the container to port 5000 on your host machine, allowing you to access the application at `http://127.0.0.1:5000/`.

### Summary of Running the Application

- **For Development**: Use `python app.py` to run the application locally.
- **For Production**: Use Docker to build and run the application in a containerized environment.

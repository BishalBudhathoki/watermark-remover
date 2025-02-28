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
   git clone https://github.com/yourusername/videovault.git
   cd videovault
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

### Docker Deployment
1. **Build the Docker image**
   ```bash
   docker build -t videovault .
   ```

2. **Run the container**
   ```bash
   docker run -p 5000:5000 videovault
   ```

### Nginx Configuration
1. **Install Nginx** on your server (Ubuntu recommended):
   ```bash
   sudo apt update
   sudo apt install nginx
   ```

2. **Configure Nginx** to reverse proxy to your Flask application:
   Create a new configuration file in `/etc/nginx/sites-available/videovault`:
   ```nginx
   server {
       listen 80;
       server_name your_domain.com;  # Replace with your domain

       location / {
           proxy_pass http://localhost:5000;  # Flask app
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **Enable the configuration**:
   ```bash
   sudo ln -s /etc/nginx/sites-available/videovault /etc/nginx/sites-enabled
   sudo nginx -t  # Test the configuration
   sudo systemctl restart nginx  # Restart Nginx
   ```

### Celery Setup
1. **Install Redis** (if not already installed):
   ```bash
   sudo apt install redis-server
   ```

2. **Start the Redis server**:
   ```bash
   sudo systemctl start redis
   ```

3. **Run Celery worker**:
   In a new terminal, activate your virtual environment and run:
   ```bash
   celery -A app.celery worker --loglevel=info
   ```

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

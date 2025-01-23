# Watermark Remover API

A FastAPI-based service for removing watermarks from videos and downloading content from various platforms.

## Project Structure

```
.
├── src/
│   ├── api/           # API routes
│   ├── services/      # Business logic
│   ├── models/        # Data models
│   ├── utils/         # Utility functions
│   ├── config/        # Configuration
│   └── database/      # Database files
├── config/            # Project configuration files
├── static/           # Static files
├── templates/        # HTML templates
├── tests/           # Test files
│   ├── unit/
│   └── integration/
├── docs/            # Documentation
├── downloads/       # Downloaded files
├── processed/       # Processed files
├── uploads/         # Uploaded files
├── main.py         # Application entry point
└── dockerfile      # Docker configuration
```

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd watermark-remover
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r config/requirements.txt
```

4. Set up environment variables:
```bash
cp config/.env.example config/.env
# Edit config/.env with your settings
```

5. Run the application:
```bash
uvicorn main:app --reload
```

## Docker Setup

1. Build the Docker image:
```bash
docker build -t watermark-remover .
```

2. Run the container:
```bash
docker run -p 8000:8000 watermark-remover
```

## API Documentation

Once the application is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Features

- Video watermark removal
- TikTok video downloading
- Batch video processing
- User authentication
- API rate limiting

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

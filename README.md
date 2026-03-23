# FieldPulse Django Project

A Django 5.x project with REST Framework, JWT authentication, and containerized deployment.

## Project Structure

```
fieldpulse/
├── config/
│   ├── settings/
│   │   ├── base.py      # Shared settings
│   │   └── local.py     # Local development settings
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── authentication/  # User authentication and JWT
│   ├── jobs/           # Job management
│   ├── media_app/      # Media file handling
│   └── sync/           # Data synchronization
├── core/
│   ├── exceptions.py   # Custom exceptions
│   ├── pagination.py   # Custom pagination
│   └── permissions.py  # Custom permissions
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── manage.py
```

## Features

- Django 5.x with Django REST Framework
- JWT Authentication (15min access, 7day refresh tokens)
- PostgreSQL database
- MinIO S3-compatible storage
- Redis caching
- Rate limiting
- Custom pagination (cursor-based)
- Comprehensive permissions system
- Docker containerization

## Quick Start

### Using Docker Compose (Recommended)

1. Copy environment file:

```bash
cp .env.example .env
```

2. Start all services:

```bash
docker-compose up -d
```

3. Run migrations:

```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

4. Seed database (optional - for development data):

```bash
docker-compose exec db psql -U postgres -d fieldpulse -f /docker-entrypoint-initdb.d/init-db.sql
```

5. Create superuser (optional):

```bash
docker-compose exec backend python manage.py createsuperuser
```

6. Access services:

- API: http://localhost:8000
- Admin: http://localhost:8000/admin
- MinIO Console: http://localhost:9001

### Local Development

1. Create virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create superuser:

```bash
python manage.py createsuperuser
```

6. Start development server:

```bash
python manage.py runserver
```

## API Endpoints

### Authentication

- `POST /api/auth/login/` - Get JWT tokens
- `POST /api/auth/refresh/` - Refresh access token
- `POST /api/auth/verify/` - Verify token validity

### Health Check

- `GET /api/health/` - Service health status

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

- `SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (True/False)
- `DB_*` - Database connection settings
- `REDIS_URL` - Redis connection URL
- `AWS_*` - MinIO/S3 storage settings
- `JWT_*` - JWT token settings

### Database

The project uses PostgreSQL. Make sure PostgreSQL is running and accessible with the credentials in your `.env` file.

### Storage

Files are stored in MinIO (S3-compatible). Configure the AWS credentials in your environment to connect to MinIO or AWS S3.

## Development

### Running Tests

```bash
python manage.py test
```

### Code Formatting

```bash
black .
isort .
flake8 .
```

### Creating New Apps

```bash
python manage.py startapp app_name apps/
```

## Deployment

The project is containerized and ready for deployment. Use the provided Dockerfile and docker-compose.yml for production deployment.

## Troubleshooting

### Common Issues

1. **Migration errors**: If migrations fail, run them manually:

   ```bash
   docker-compose exec backend python manage.py makemigrations
   docker-compose exec backend python manage.py migrate
   ```

2. **Database connection issues**: Ensure PostgreSQL is running and check `.env` settings.

3. **Container restart loops**: Check logs with:

   ```bash
   docker-compose logs [service_name]
   ```

4. **MinIO connection issues**: Verify AWS credentials in environment variables.

### Database Seeding

If you need to reset and reseed the database:

```bash
# Clear existing data and reseed
docker-compose exec db psql -U postgres -d fieldpulse -f /docker-entrypoint-initdb.d/init-db.sql
```

**Test Users Created:**

- Email: `tech1@fieldpulse.com` - Password: `password123`
- Email: `tech2@fieldpulse.com` - Password: `password123`
- Email: `tech3@fieldpulse.com` - Password: `password123`

These users are technicians with sample jobs assigned to them.

## Security Notes

- Change `SECRET_KEY` in production
- Set `DEBUG=False` in production
- Use strong database passwords
- Configure proper CORS settings
- Enable HTTPS in production
- Review and update security headers

## License

This project is proprietary software.

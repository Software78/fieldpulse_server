# FieldPulse Django Project

A Django 5.x project with REST Framework, JWT authentication, and containerized deployment.

## Quick Start

### Docker Compose Deployment

1. Start all services:

```bash
docker-compose up -d
```

2. Run migrations:

```bash
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

3. Seed database (optional - for development data):

```bash
docker-compose exec db psql -U postgres -d fieldpulse -f /docker-entrypoint-initdb.d/init-db.sql
```

4. Create superuser (optional):

```bash
docker-compose exec backend python manage.py createsuperuser
```

## Service Access & Dashboards

### Application URLs

- **API Base URL**: http://localhost:8000
- **Admin Dashboard**: http://localhost:8000/admin
- **API Documentation (Swagger)**: http://localhost:8000/api/docs/
- **API Documentation (ReDoc)**: http://localhost:8000/api/redoc/

### Infrastructure Dashboards

- **MinIO Console**: http://localhost:9001
- **Database**: PostgreSQL (port 5432, accessible via `docker-compose exec db`)

### Default Login Credentials

**Test Users (after database seeding):**

- Email: `tech1@fieldpulse.com` - Password: `password123`
- Email: `tech2@fieldpulse.com` - Password: `password123`
- Email: `tech3@fieldpulse.com` - Password: `password123`

**MinIO Console:**

- Access Key: Check `.env` file for `AWS_ACCESS_KEY_ID`
- Secret Key: Check `.env` file for `AWS_SECRET_ACCESS_KEY`

**Admin Dashboard:**

- Use superuser credentials created with `createsuperuser` command
- Or use test user credentials above (limited permissions)

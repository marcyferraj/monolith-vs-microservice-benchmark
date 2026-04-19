# Microservices Project

A modular microservices architecture with an authentication service built with Flask and PostgreSQL.

## Project Structure

```
.
├── docker-compose.yml      # Docker Compose configuration
├── auth-service/           # Authentication microservice
│   ├── app.py             # Flask application
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile         # Docker image configuration
│   └── init-auth.sql      # Database initialization script
├── .env                    # Environment variables
└── README.md              # This file
```

## Prerequisites

- Docker and Docker Compose
- Or Python 3.11+ and PostgreSQL 15

## Getting Started

### Using Docker Compose (Recommended)

1. Start all services:
```bash
docker-compose up -d
```

2. Verify services are running:
```bash
docker-compose ps
```

3. Check health of auth service:
```bash
curl http://localhost:5000/health
```

### Local Development

1. Install dependencies:
```bash
cd auth-service
pip install -r requirements.txt
```

2. Start PostgreSQL database separately

3. Run the Flask app:
```bash
flask run
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Authentication
- `POST /auth/register` - Register new user
  ```json
  {
    "username": "user123",
    "email": "user@example.com",
    "password": "password123"
  }
  ```

- `POST /auth/login` - Login and get JWT token
  ```json
  {
    "username": "user123",
    "password": "password123"
  }
  ```

- `POST /auth/verify` - Verify JWT token
  - Header: `Authorization: Bearer <token>`

## Default Test User

- Username: `testuser`
- Email: `test@example.com`
- Password: `password123`

## Stopping Services

```bash
docker-compose down
```

## Logs

View logs from all services:
```bash
docker-compose logs -f
```

View logs from specific service:
```bash
docker-compose logs -f auth-service
```

## Environment Variables

Configure settings in `.env` file:
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_NAME` - Database name
- `FLASK_ENV` - Flask environment (development/production)
- `SECRET_KEY` - JWT secret key

## Development

### Database Migrations

The schema is automatically created on first run. For schema changes, update `init-auth.sql` and recreate the database volume:

```bash
docker-compose down -v
docker-compose up -d
```

### Adding New Services

1. Create service directory: `mkdir service-name`
2. Add `Dockerfile` and `requirements.txt`
3. Update `docker-compose.yml` with new service definition

# Docker Deployment Guide

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Generate a secure secret key
python generate_secret_key.py

# Copy the generated key and paste it into .env file
# Windows: notepad .env
# Linux/Mac: nano .env (or vim, code, etc.)
```

**Note:** The `generate_secret_key.py` script will output a formatted key that you can copy directly to your `.env` file.

### 2. Build and Run

```bash
# Build and start container (first time)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop container
docker-compose down
```

**Note:** Use `--build` flag on first run or after code changes to rebuild the image.

### 3. Access Application

Open browser: http://localhost:5000

---

## Files Structure

```
inventory_optimization/
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Container orchestration
├── .dockerignore          # Files to exclude from image
├── .env.example           # Environment template
├── .env                   # Your environment config (create this)
└── DOCKER_README.md       # This file
```

---

## Volumes (Persisted Data)

The following folders are mounted as volumes to persist data:

- `./uploads/` → `/app/uploads` - Uploaded CSV files
- `./flask_session/` → `/app/flask_session` - Session storage
- `./output/` → `/app/output` - Optimization results

**Important:** These folders will persist even after container restart.

---

## Environment Variables

### Required:
- `FLASK_SECRET_KEY` - Secret key for session encryption (generate new one!)

### Optional:
- `FLASK_APP=app.py` - Entry point
- `PYTHONUNBUFFERED=1` - Real-time logging

---

## Common Commands

### View running containers
```bash
docker ps
```

### View all containers (including stopped)
```bash
docker ps -a
```

### Restart container
```bash
docker-compose restart
```

### Rebuild image (after code changes)
```bash
docker-compose up -d --build
```

### Remove all data (clean start)
```bash
docker-compose down -v
rm -rf uploads/* flask_session/* output/*
```

### Access container shell
```bash
docker exec -it inventory_optimization bash
```

### View resource usage
```bash
docker stats inventory_optimization
```

---

## Troubleshooting

### Port 5000 already in use
```bash
# Find process using port 5000
lsof -i :5000  # macOS/Linux
netstat -ano | findstr :5000  # Windows

# Kill the process or change port in docker-compose.yml:
ports:
  - "5001:5000"  # Map to different host port
```

### Permission issues with volumes
```bash
# Linux: Fix permissions
sudo chown -R $USER:$USER uploads/ flask_session/ output/
```

### Container crashes on startup
```bash
# Check logs
docker-compose logs web

# Check if dependencies are installed
docker exec inventory_optimization pip list
```

### Changes not reflected
```bash
# Rebuild image
docker-compose up -d --build

# Or force recreate
docker-compose up -d --force-recreate
```

---

## Production Deployment

### Security Checklist:
- [ ] Generated unique `FLASK_SECRET_KEY`
- [ ] Changed default ports if needed
- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Configured firewall rules
- [ ] Setup reverse proxy (nginx/traefik)
- [ ] Enable HTTPS/SSL
- [ ] Regular backups of volumes
- [ ] Monitor disk usage (session/output files)

### Recommended: Add nginx reverse proxy
```yaml
# docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - web
```

---

## Cleanup

### Stop and remove container
```bash
docker-compose down
```

### Remove image
```bash
docker rmi inventory_optimization_web
```

### Remove all unused Docker resources
```bash
docker system prune -a
```

---

## Moving Docker Files to `docker/` Folder (Optional)

If you prefer to organize Docker files in a separate folder:

```bash
# Create folder
mkdir docker

# Move files
mv Dockerfile docker/
mv docker-compose.yml docker/
mv .dockerignore docker/

# Build from new location
cd docker
docker-compose up -d --build

# Or from root
docker-compose -f docker/docker-compose.yml up -d --build
```

**Note:** You'll need to update paths in `docker-compose.yml`:
```yaml
build:
  context: ..
  dockerfile: docker/Dockerfile
```

# Docker Deployment Guide

## Quick Start

### Build and run with Docker Compose (Recommended)
```bash
docker-compose up -d
```

Access the application at: http://localhost:5000

### Stop the application
```bash
docker-compose down
```

## Manual Docker Commands

### Build the image
```bash
docker build -t inventory-optimization .
```

### Run the container
```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/flask_session:/app/flask_session \
  -v $(pwd)/output:/app/output \
  --name inventory_optimization \
  inventory-optimization
```

### View logs
```bash
docker logs -f inventory_optimization
```

### Stop and remove container
```bash
docker stop inventory_optimization
docker rm inventory_optimization
```

## Configuration

### Environment Variables
You can customize the deployment by setting environment variables:

```bash
docker run -d \
  -p 5000:5000 \
  -e FLASK_APP=app.py \
  -e PYTHONUNBUFFERED=1 \
  --name inventory_optimization \
  inventory-optimization
```

### Persistent Data
The following directories are mounted as volumes for data persistence:
- `./flask_session` - Flask session data
- `./output` - Optimization results and exported files

## Production Deployment

For production, consider:

1. **Change secret key** in `app.py` line 10 to a strong random value
2. **Set DEBUG=False** in `app.py` line 77
3. **Use production WSGI server** (gunicorn):

Update Dockerfile CMD:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

Add to requirements.txt:
```
gunicorn==21.2.0
```

4. **Enable HTTPS** and update session cookie settings in `app.py`

## Troubleshooting

### Check if container is running
```bash
docker ps
```

### View container logs
```bash
docker logs inventory_optimization
```

### Access container shell
```bash
docker exec -it inventory_optimization bash
```

### Remove all stopped containers
```bash
docker container prune
```

### Rebuild without cache
```bash
docker-compose build --no-cache
```

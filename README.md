# Object Storage Service

HTTP service for storing objects in buckets with automatic content deduplication.

**Co-authored-by:** Claude (Anthropic)

## Features

- Store data as objects in buckets
- REST API for object storage (PUT, GET, DELETE)
- Content deduplication per bucket using SHA-256
- Memory or disk storage backends
- Fedora-based container support

## Quick Start

### Using Podman

```bash
# Build the container
podman build -t object-storage .

# Run on default port (8080)
podman run -d -p 8080:8080 --name object-storage object-storage

# Or run on custom port (e.g., 3000)
podman run -d -p 3000:3000 -e PORT=3000 --name object-storage object-storage

# Test the service
curl http://localhost:8080/health
```

### Local Development

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup and run (one command)
uv run --no-sync python -m src.object_storage.app

# Or setup once, then run
uv venv
uv pip install -r pyproject.toml
source .venv/bin/activate
python -m src.object_storage.app
```

## API

### Upload Object
```bash
PUT /objects/{bucket}/{objectID}

# Store data in an object
curl -X PUT http://localhost:8080/objects/my-bucket/obj1 \
  -d "some data"
```

### Download Object
```bash
GET /objects/{bucket}/{objectID}

# Retrieve stored data
curl http://localhost:8080/objects/my-bucket/obj1
# Returns: some data
```

### Delete Object
```bash
DELETE /objects/{bucket}/{objectID}

curl -X DELETE http://localhost:8080/objects/my-bucket/obj1
```

### Bucket Management
```bash
# Create bucket
POST /buckets/{name}

# List buckets
GET /buckets

# Delete bucket
DELETE /buckets/{name}
```

## Configuration

Set via environment variables:

```bash
PORT=8080              # Server port (default: 8080)
STORAGE_TYPE=memory    # Storage: memory or disk (default: memory)
STORAGE_PATH=./storage # Path for disk storage
```

## Testing

```bash
# Install dev dependencies
uv pip install -r pyproject.toml --extra dev

# Run tests
pytest

# With coverage
pytest --cov

# Lint code
ruff check src/ tests/
```

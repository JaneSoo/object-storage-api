"""Main application module for object storage service."""

from flask import Flask
import os

from .storage import MemoryStorage, DiskStorage
from .routes import create_routes

app = Flask(__name__)

STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'memory')
STORAGE_PATH = os.getenv('STORAGE_PATH', './storage')
PORT = int(os.getenv('PORT', 8080))
HOST = os.getenv('HOST', '0.0.0.0')

# Storage backend initialization
if STORAGE_TYPE == 'disk':
    storage = DiskStorage(STORAGE_PATH)
else:
    storage = MemoryStorage()

# Register routes
routes_blueprint = create_routes(storage)
app.register_blueprint(routes_blueprint)

if __name__ == '__main__':
    print(f'Starting Object Storage API on {HOST}:{PORT}')
    print(f'Storage type: {STORAGE_TYPE}')
    if STORAGE_TYPE == 'disk':
        print(f'Storage path: {STORAGE_PATH}')
    app.run(debug=True, host=HOST, port=PORT)

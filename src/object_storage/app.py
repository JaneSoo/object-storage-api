from flask import Flask, jsonify, request
from datetime import datetime
import uuid
import os
import json
import hashlib
from pathlib import Path

app = Flask(__name__)

STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'memory')
STORAGE_PATH = os.getenv('STORAGE_PATH', './storage')
PORT = int(os.getenv('PORT', 8080))
HOST = os.getenv('HOST', '0.0.0.0')

class MemoryStorage:
    def __init__(self):
        self.buckets = {}

    def _compute_hash(self, data):
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def create_bucket(self, bucket_name):
        if bucket_name in self.buckets:
            return False
        self.buckets[bucket_name] = {
            'created_at': datetime.utcnow().isoformat(),
            'objects': {},
            'content_store': {},
            'hash_refs': {}
        }
        return True

    def delete_bucket(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, 'not_found'
        if len(self.buckets[bucket_name]['objects']) > 0:
            return False, 'not_empty'
        del self.buckets[bucket_name]
        return True, None

    def list_buckets(self):
        return [
            {
                'name': name,
                'created_at': info['created_at'],
                'object_count': len(info['objects']),
                'unique_objects': len(info['content_store'])
            }
            for name, info in self.buckets.items()
        ]

    def bucket_exists(self, bucket_name):
        return bucket_name in self.buckets

    def put_object(self, bucket_name, object_id, data, content_type):
        if bucket_name not in self.buckets:
            return False, None, None

        content_hash = self._compute_hash(data)
        bucket = self.buckets[bucket_name]

        if content_hash not in bucket['content_store']:
            bucket['content_store'][content_hash] = {
                'data': data,
                'created_at': datetime.utcnow().isoformat(),
                'content_type': content_type
            }
            bucket['hash_refs'][content_hash] = 0

        bucket['hash_refs'][content_hash] += 1

        if object_id in bucket['objects']:
            old_hash = bucket['objects'][object_id]['content_hash']
            bucket['hash_refs'][old_hash] -= 1
            if bucket['hash_refs'][old_hash] == 0:
                del bucket['content_store'][old_hash]
                del bucket['hash_refs'][old_hash]

        etag = content_hash[:16]
        bucket['objects'][object_id] = {
            'content_hash': content_hash,
            'etag': etag,
            'created_at': datetime.utcnow().isoformat()
        }

        is_duplicate = bucket['hash_refs'][content_hash] > 1
        return True, etag, is_duplicate

    def get_object(self, bucket_name, object_id):
        if bucket_name not in self.buckets:
            return None, 'bucket_not_found'

        bucket = self.buckets[bucket_name]
        if object_id not in bucket['objects']:
            return None, 'object_not_found'

        obj_meta = bucket['objects'][object_id]
        content = bucket['content_store'][obj_meta['content_hash']]

        return {
            'data': content['data'],
            'created_at': obj_meta['created_at'],
            'content_type': content['content_type'],
            'etag': obj_meta['etag'],
            'content_hash': obj_meta['content_hash']
        }, None

    def delete_object(self, bucket_name, object_id):
        if bucket_name not in self.buckets:
            return False, 'bucket_not_found'

        bucket = self.buckets[bucket_name]
        if object_id not in bucket['objects']:
            return False, 'object_not_found'

        content_hash = bucket['objects'][object_id]['content_hash']
        del bucket['objects'][object_id]

        bucket['hash_refs'][content_hash] -= 1
        if bucket['hash_refs'][content_hash] == 0:
            del bucket['content_store'][content_hash]
            del bucket['hash_refs'][content_hash]

        return True, None

    def list_objects(self, bucket_name):
        if bucket_name not in self.buckets:
            return None

        bucket = self.buckets[bucket_name]
        return [
            {
                'id': key,
                'size': len(bucket['content_store'][obj['content_hash']]['data']),
                'created_at': obj['created_at'],
                'content_type': bucket['content_store'][obj['content_hash']]['content_type'],
                'etag': obj['etag'],
                'content_hash': obj['content_hash']
            }
            for key, obj in bucket['objects'].items()
        ]

class DiskStorage:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def _compute_hash(self, data):
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def _bucket_path(self, bucket_name):
        return self.base_path / bucket_name

    def _bucket_meta_path(self, bucket_name):
        return self._bucket_path(bucket_name) / '.metadata.json'

    def _content_store_path(self, bucket_name):
        return self._bucket_path(bucket_name) / '.content'

    def _content_file_path(self, bucket_name, content_hash):
        return self._content_store_path(bucket_name) / content_hash

    def _object_meta_path(self, bucket_name, object_id):
        return self._bucket_path(bucket_name) / f'{object_id}.json'

    def _hash_refs_path(self, bucket_name):
        return self._bucket_path(bucket_name) / '.hash_refs.json'

    def _load_hash_refs(self, bucket_name):
        refs_path = self._hash_refs_path(bucket_name)
        if refs_path.exists():
            return json.loads(refs_path.read_text())
        return {}

    def _save_hash_refs(self, bucket_name, refs):
        refs_path = self._hash_refs_path(bucket_name)
        refs_path.write_text(json.dumps(refs))

    def create_bucket(self, bucket_name):
        bucket_path = self._bucket_path(bucket_name)
        if bucket_path.exists():
            return False
        bucket_path.mkdir(parents=True)
        self._content_store_path(bucket_name).mkdir()
        meta = {
            'created_at': datetime.utcnow().isoformat()
        }
        self._bucket_meta_path(bucket_name).write_text(json.dumps(meta))
        self._save_hash_refs(bucket_name, {})
        return True

    def delete_bucket(self, bucket_name):
        bucket_path = self._bucket_path(bucket_name)
        if not bucket_path.exists():
            return False, 'not_found'

        objects = [f for f in bucket_path.iterdir() if f.suffix == '.json' and not f.name.startswith('.')]
        if len(objects) > 0:
            return False, 'not_empty'

        import shutil
        shutil.rmtree(bucket_path)
        return True, None

    def list_buckets(self):
        buckets = []
        for bucket_path in self.base_path.iterdir():
            if bucket_path.is_dir():
                meta_path = bucket_path / '.metadata.json'
                meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
                objects = [f for f in bucket_path.iterdir() if f.suffix == '.json' and not f.name.startswith('.')]
                content_store = bucket_path / '.content'
                unique_count = len(list(content_store.iterdir())) if content_store.exists() else 0
                buckets.append({
                    'name': bucket_path.name,
                    'created_at': meta.get('created_at', ''),
                    'object_count': len(objects),
                    'unique_objects': unique_count
                })
        return buckets

    def bucket_exists(self, bucket_name):
        return self._bucket_path(bucket_name).exists()

    def put_object(self, bucket_name, object_id, data, content_type):
        if not self.bucket_exists(bucket_name):
            return False, None, None

        content_hash = self._compute_hash(data)
        content_path = self._content_file_path(bucket_name, content_hash)
        hash_refs = self._load_hash_refs(bucket_name)

        obj_meta_path = self._object_meta_path(bucket_name, object_id)
        old_hash = None
        if obj_meta_path.exists():
            old_meta = json.loads(obj_meta_path.read_text())
            old_hash = old_meta.get('content_hash')

        if not content_path.exists():
            content_path.write_text(data)
            hash_refs[content_hash] = 0

        hash_refs[content_hash] = hash_refs.get(content_hash, 0) + 1

        if old_hash and old_hash != content_hash:
            hash_refs[old_hash] -= 1
            if hash_refs[old_hash] == 0:
                self._content_file_path(bucket_name, old_hash).unlink()
                del hash_refs[old_hash]

        etag = content_hash[:16]
        meta = {
            'content_hash': content_hash,
            'created_at': datetime.utcnow().isoformat(),
            'content_type': content_type,
            'etag': etag
        }
        obj_meta_path.write_text(json.dumps(meta))
        self._save_hash_refs(bucket_name, hash_refs)

        is_duplicate = hash_refs[content_hash] > 1
        return True, etag, is_duplicate

    def get_object(self, bucket_name, object_id):
        if not self.bucket_exists(bucket_name):
            return None, 'bucket_not_found'

        obj_meta_path = self._object_meta_path(bucket_name, object_id)
        if not obj_meta_path.exists():
            return None, 'object_not_found'

        meta = json.loads(obj_meta_path.read_text())
        content_hash = meta['content_hash']
        content_path = self._content_file_path(bucket_name, content_hash)

        return {
            'data': content_path.read_text(),
            'created_at': meta.get('created_at', ''),
            'content_type': meta.get('content_type', 'text/plain'),
            'etag': meta.get('etag', ''),
            'content_hash': content_hash
        }, None

    def delete_object(self, bucket_name, object_id):
        if not self.bucket_exists(bucket_name):
            return False, 'bucket_not_found'

        obj_meta_path = self._object_meta_path(bucket_name, object_id)
        if not obj_meta_path.exists():
            return False, 'object_not_found'

        meta = json.loads(obj_meta_path.read_text())
        content_hash = meta['content_hash']
        hash_refs = self._load_hash_refs(bucket_name)

        obj_meta_path.unlink()

        hash_refs[content_hash] -= 1
        if hash_refs[content_hash] == 0:
            self._content_file_path(bucket_name, content_hash).unlink()
            del hash_refs[content_hash]

        self._save_hash_refs(bucket_name, hash_refs)
        return True, None

    def list_objects(self, bucket_name):
        if not self.bucket_exists(bucket_name):
            return None

        bucket_path = self._bucket_path(bucket_name)
        objects = []
        for obj_meta_path in bucket_path.iterdir():
            if obj_meta_path.suffix == '.json' and not obj_meta_path.name.startswith('.'):
                meta = json.loads(obj_meta_path.read_text())
                content_hash = meta['content_hash']
                content_path = self._content_file_path(bucket_name, content_hash)
                objects.append({
                    'id': obj_meta_path.stem,
                    'size': content_path.stat().st_size if content_path.exists() else 0,
                    'created_at': meta.get('created_at', ''),
                    'content_type': meta.get('content_type', 'text/plain'),
                    'etag': meta.get('etag', ''),
                    'content_hash': content_hash
                })
        return objects

if STORAGE_TYPE == 'disk':
    storage = DiskStorage(STORAGE_PATH)
else:
    storage = MemoryStorage()

@app.route('/')
def index():
    return jsonify({
        'message': 'Object Storage API',
        'version': '1.0.0',
        'storage_type': STORAGE_TYPE,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/buckets', methods=['GET'])
def list_buckets():
    buckets = storage.list_buckets()
    return jsonify({'buckets': buckets})

@app.route('/buckets/<bucket_name>', methods=['POST'])
def create_bucket(bucket_name):
    if not storage.create_bucket(bucket_name):
        return jsonify({'error': 'Bucket already exists'}), 409

    return jsonify({'name': bucket_name}), 201

@app.route('/buckets/<bucket_name>', methods=['DELETE'])
def delete_bucket(bucket_name):
    success, error = storage.delete_bucket(bucket_name)

    if not success:
        if error == 'not_found':
            return jsonify({'error': 'Bucket not found'}), 404
        elif error == 'not_empty':
            return jsonify({'error': 'Bucket is not empty'}), 400

    return '', 204

@app.route('/objects/<bucket_name>', methods=['GET'])
def list_objects(bucket_name):
    objects = storage.list_objects(bucket_name)
    if objects is None:
        return jsonify({'error': 'Bucket not found'}), 404

    return jsonify({'objects': objects})

@app.route('/objects/<bucket_name>/<object_id>', methods=['PUT'])
def put_object(bucket_name, object_id):
    data = request.get_data(as_text=True)
    content_type = request.content_type or 'text/plain'

    success, etag, is_duplicate = storage.put_object(bucket_name, object_id, data, content_type)

    if not success:
        return jsonify({'error': 'Bucket not found'}), 404

    return jsonify({'id': object_id}), 201

@app.route('/objects/<bucket_name>/<object_id>', methods=['GET'])
def get_object(bucket_name, object_id):
    obj, error = storage.get_object(bucket_name, object_id)

    if error == 'bucket_not_found':
        return jsonify({'error': 'Bucket not found'}), 404
    elif error == 'object_not_found':
        return jsonify({'error': 'Object not found'}), 404

    return obj['data'], 200, {'Content-Type': obj['content_type']}

@app.route('/objects/<bucket_name>/<object_id>', methods=['DELETE'])
def delete_object(bucket_name, object_id):
    success, error = storage.delete_object(bucket_name, object_id)

    if not success:
        if error == 'bucket_not_found':
            return '', 404
        elif error == 'object_not_found':
            return '', 404

    return '', 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print(f'Starting Object Storage API on {HOST}:{PORT}')
    print(f'Storage type: {STORAGE_TYPE}')
    if STORAGE_TYPE == 'disk':
        print(f'Storage path: {STORAGE_PATH}')
    app.run(debug=True, host=HOST, port=PORT)

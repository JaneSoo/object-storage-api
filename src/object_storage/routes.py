"""API routes for object storage service."""

from flask import Blueprint, jsonify, request
from datetime import datetime


def create_routes(storage):
    """Create and configure API routes blueprint."""
    bp = Blueprint('api', __name__)

    @bp.route('/')
    def index():
        return jsonify({
            'message': 'Object Storage API',
            'version': '1.0.0',
            'storage_type': storage.__class__.__name__.replace('Storage', '').lower(),
            'timestamp': datetime.utcnow().isoformat()
        })

    @bp.route('/health')
    def health():
        return jsonify({'status': 'healthy'}), 200

    @bp.route('/buckets', methods=['GET'])
    def list_buckets():
        buckets = storage.list_buckets()
        return jsonify({'buckets': buckets})

    @bp.route('/buckets/<bucket_name>', methods=['POST'])
    def create_bucket(bucket_name):
        if not storage.create_bucket(bucket_name):
            return jsonify({'error': 'Bucket already exists'}), 409

        return jsonify({'name': bucket_name}), 201

    @bp.route('/buckets/<bucket_name>', methods=['DELETE'])
    def delete_bucket(bucket_name):
        success, error = storage.delete_bucket(bucket_name)

        if not success:
            if error == 'not_found':
                return jsonify({'error': 'Bucket not found'}), 404
            elif error == 'not_empty':
                return jsonify({'error': 'Bucket is not empty'}), 400

        return '', 204

    @bp.route('/objects/<bucket_name>', methods=['GET'])
    def list_objects(bucket_name):
        objects = storage.list_objects(bucket_name)
        if objects is None:
            return jsonify({'error': 'Bucket not found'}), 404

        return jsonify({'objects': objects})

    @bp.route('/objects/<bucket_name>/<object_id>', methods=['PUT'])
    def put_object(bucket_name, object_id):
        # Store the body data
        data = request.get_data(as_text=True)
        content_type = request.content_type or 'text/plain'

        success, etag, is_duplicate = storage.put_object(bucket_name, object_id, data, content_type)

        if not success:
            return jsonify({'error': 'Bucket not found'}), 404

        return jsonify({'id': object_id}), 201

    @bp.route('/objects/<bucket_name>/<object_id>', methods=['GET'])
    def get_object(bucket_name, object_id):
        obj, error = storage.get_object(bucket_name, object_id)

        if error == 'bucket_not_found':
            return jsonify({'error': 'Bucket not found'}), 404
        elif error == 'object_not_found':
            return jsonify({'error': 'Object not found'}), 404

        return obj['data'], 200, {'Content-Type': obj['content_type']}

    @bp.route('/objects/<bucket_name>/<object_id>', methods=['DELETE'])
    def delete_object(bucket_name, object_id):
        success, error = storage.delete_object(bucket_name, object_id)

        if not success:
            if error == 'bucket_not_found':
                return 'Bucket not found', 404
            elif error == 'object_not_found':
                return 'Object not found', 404

        return 'Object deleted successfully', 200

    @bp.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @bp.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return bp

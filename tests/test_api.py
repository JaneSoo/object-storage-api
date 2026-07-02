"""Tests for the object storage API."""

import pytest
from src.object_storage import app as app_module


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    # Reset storage before each test
    if isinstance(app_module.storage, app_module.MemoryStorage):
        app_module.storage.buckets = {}

    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as client:
        yield client


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'healthy'}


def test_service_info(client):
    """Test the service info endpoint."""
    response = client.get('/')
    assert response.status_code == 200
    data = response.json
    assert data['message'] == 'Object Storage API'
    assert data['version'] == '1.0.0'
    assert 'storage_type' in data
    assert 'timestamp' in data


def test_create_bucket(client):
    """Test bucket creation."""
    response = client.post('/buckets/test-bucket')
    assert response.status_code == 201
    assert response.json['name'] == 'test-bucket'


def test_create_duplicate_bucket(client):
    """Test creating a duplicate bucket returns 409."""
    client.post('/buckets/test-bucket')
    response = client.post('/buckets/test-bucket')
    assert response.status_code == 409


def test_list_buckets(client):
    """Test listing buckets."""
    client.post('/buckets/bucket1')
    client.post('/buckets/bucket2')

    response = client.get('/buckets')
    assert response.status_code == 200
    data = response.json
    assert len(data['buckets']) >= 2


def test_put_object(client):
    """Test uploading an object."""
    client.post('/buckets/test-bucket')

    response = client.put(
        '/objects/test-bucket/obj1',
        data='GET /api/test HTTP/1.1\nHost: example.com',
        content_type='text/plain'
    )
    assert response.status_code == 201
    assert response.json['id'] == 'obj1'


def test_get_object(client):
    """Test retrieving an object."""
    client.post('/buckets/test-bucket')
    test_data = 'GET /api/test HTTP/1.1\nHost: example.com'

    client.put(
        '/objects/test-bucket/obj1',
        data=test_data,
        content_type='text/plain'
    )

    response = client.get('/objects/test-bucket/obj1')
    assert response.status_code == 200
    # Object stores the body data
    assert response.data.decode('utf-8') == test_data


def test_get_nonexistent_object(client):
    """Test retrieving a non-existent object returns 404."""
    client.post('/buckets/test-bucket')
    response = client.get('/objects/test-bucket/nonexistent')
    assert response.status_code == 404


def test_delete_object(client):
    """Test deleting an object."""
    client.post('/buckets/test-bucket')
    client.put('/objects/test-bucket/obj1', data='test data')

    response = client.delete('/objects/test-bucket/obj1')
    assert response.status_code == 200

    # Verify object is gone
    response = client.get('/objects/test-bucket/obj1')
    assert response.status_code == 404


def test_delete_nonexistent_object(client):
    """Test deleting a non-existent object returns 404."""
    client.post('/buckets/test-bucket')
    response = client.delete('/objects/test-bucket/nonexistent')
    assert response.status_code == 404


def test_deduplication(client):
    """Test that duplicate content is deduplicated."""
    client.post('/buckets/test-bucket')
    test_data = 'duplicate content'

    # Upload same content with different IDs
    client.put('/objects/test-bucket/obj1', data=test_data)
    client.put('/objects/test-bucket/obj2', data=test_data)

    # Check bucket stats
    response = client.get('/buckets')
    buckets = response.json['buckets']
    test_bucket = next(b for b in buckets if b['name'] == 'test-bucket')

    assert test_bucket['object_count'] == 2
    assert test_bucket['unique_objects'] == 1  # Content deduplicated


def test_list_objects_in_bucket(client):
    """Test listing objects in a bucket."""
    client.post('/buckets/test-bucket')
    client.put('/objects/test-bucket/obj1', data='data1')
    client.put('/objects/test-bucket/obj2', data='data2')

    response = client.get('/objects/test-bucket')
    assert response.status_code == 200
    objects = response.json['objects']
    assert len(objects) == 2


def test_delete_bucket(client):
    """Test deleting an empty bucket."""
    client.post('/buckets/test-bucket')

    response = client.delete('/buckets/test-bucket')
    assert response.status_code == 204


def test_delete_non_empty_bucket(client):
    """Test deleting a non-empty bucket returns 400."""
    client.post('/buckets/test-bucket')
    client.put('/objects/test-bucket/obj1', data='test')

    response = client.delete('/buckets/test-bucket')
    assert response.status_code == 400

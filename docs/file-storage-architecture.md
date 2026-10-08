# Voice2Gov File Storage Architecture

## Overview
Image storage architecture for complaint evidence, progress photos, completion photos, and profile images. Uses metadata in MongoDB with pluggable storage backend.

---

## Image Types

| Type | Description | Max Size | Retention |
|------|-------------|----------|-----------|
| `evidence` | Citizen-submitted complaint photos | 10 MB | Permanent |
| `progress` | Staff progress updates | 5 MB | Permanent |
| `completion` | Staff completion evidence | 5 MB | Permanent |
| `profile` | User avatar | 2 MB | Until replaced |

---

## Storage Abstraction

### Storage Provider Interface
```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from dataclasses import dataclass

@dataclass
class UploadResult:
    storage_key: str          # Unique key in storage
    public_url: str           # CDN/signed URL for access
    file_size: int
    checksum: str             # SHA-256 hex

@dataclass
class StorageConfig:
    bucket: str
    region: str
    base_url: str             # CDN or direct access URL

class StorageProvider(ABC):
    @abstractmethod
    async def upload(
        self,
        file: BinaryIO,
        key: str,
        content_type: str,
        metadata: dict = None
    ) -> UploadResult:
        pass
    
    @abstractmethod
    async def download(self, key: str) -> BinaryIO:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate time-limited access URL"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

class LocalStorageProvider(StorageProvider):
    """Development provider - stores on local filesystem"""
    def __init__(self, base_path: str, base_url: str):
        self.base_path = Path(base_path)
        self.base_url = base_url
    
    async def upload(self, file, key, content_type, metadata=None):
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        
        content = file.read()
        checksum = hashlib.sha256(content).hexdigest()
        
        async with aiofiles.open(path, 'wb') as f:
            await f.write(content)
        
        return UploadResult(
            storage_key=key,
            public_url=f"{self.base_url}/{key}",
            file_size=len(content),
            checksum=checksum
        )

class S3StorageProvider(StorageProvider):
    """Production provider - AWS S3 / MinIO compatible"""
    def __init__(self, config: StorageConfig, credentials: dict):
        self.config = config
        self.client = boto3.client('s3', **credentials)
    
    async def upload(self, file, key, content_type, metadata=None):
        content = file.read()
        checksum = hashlib.sha256(content).hexdigest()
        
        extra_args = {'ContentType': content_type}
        if metadata:
            extra_args['Metadata'] = metadata
        
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.client.put_object(
                Bucket=self.config.bucket,
                Key=key,
                Body=content,
                **extra_args
            )
        )
        
        url = f"https://{self.config.bucket}.s3.{self.config.region}.amazonaws.com/{key}"
        return UploadResult(key, url, len(content), checksum)

class GridFSProvider(StorageProvider):
    """MongoDB GridFS - alternative for small deployments.
    
    Note: pymongo 4.18 async driver does not yet include async GridFS support.
    This implementation uses the synchronous gridfs package with asyncio.to_thread.
    """
    def __init__(self, db):
        from gridfs import GridFSBucket
        self.fs = GridFSBucket(db)
    
    async def upload(self, file, key, content_type, metadata=None):
        import asyncio
        content = file.read()
        checksum = hashlib.sha256(content).hexdigest()
        
        def _upload():
            upload_stream = self.fs.open_upload_stream(
                key,
                metadata={'contentType': content_type, **(metadata or {})}
            )
            upload_stream.write(content)
            upload_stream.close()
        
        await asyncio.to_thread(_upload)
        
        # GridFS doesn't have public URLs, use API endpoint
        url = f"/api/v1/images/{key}"
        return UploadResult(key, url, len(content), checksum)
```

---

## File Validation

### Validation Rules
```python
class FileValidator:
    ALLOWED_MIME_TYPES = {
        'evidence': ['image/jpeg', 'image/png', 'image/webp', 'image/heic'],
        'progress': ['image/jpeg', 'image/png', 'image/webp'],
        'completion': ['image/jpeg', 'image/png', 'image/webp'],
        'profile': ['image/jpeg', 'image/png', 'image/webp']
    }
    
    MAX_FILE_SIZES = {
        'evidence': 10 * 1024 * 1024,      # 10 MB
        'progress': 5 * 1024 * 1024,       # 5 MB
        'completion': 5 * 1024 * 1024,     # 5 MB
        'profile': 2 * 1024 * 1024         # 2 MB
    }
    
    MAX_DIMENSIONS = (4096, 4096)  # Max width/height
    
    @classmethod
    def validate(cls, file: UploadFile, image_type: str) -> ValidationResult:
        # 1. MIME type
        if file.content_type not in cls.ALLOWED_MIME_TYPES.get(image_type, []):
            return ValidationResult(
                valid=False,
                error="INVALID_FILE_TYPE",
                message=f"MIME type {file.content_type} not allowed for {image_type}"
            )
        
        # 2. File size (check Content-Length header first)
        content_length = file.headers.get('content-length')
        if content_length and int(content_length) > cls.MAX_FILE_SIZES[image_type]:
            return ValidationResult(
                valid=False,
                error="FILE_TOO_LARGE",
                message=f"File exceeds {cls.MAX_FILE_SIZES[image_type] / 1024 / 1024}MB limit"
            )
        
        # 3. Filename sanitization
        safe_filename = cls.sanitize_filename(file.filename)
        if safe_filename != file.filename:
            return ValidationResult(
                valid=False,
                error="INVALID_FILENAME",
                message="Filename contains invalid characters"
            )
        
        return ValidationResult(valid=True)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        # Remove path components
        filename = os.path.basename(filename)
        # Keep only alphanumeric, dash, underscore, dot
        filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
        # Limit length
        name, ext = os.path.splitext(filename)
        return f"{name[:100]}{ext[:10]}"
```

### Magic Bytes Validation (Additional Security)
```python
MAGIC_BYTES = {
    'image/jpeg': b'\xFF\xD8\xFF',
    'image/png': b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A',
    'image/webp': b'\x52\x49\x46\x46',  # RIFF header, need more check
    'image/heic': b'\x00\x00\x00\x20\x66\x74\x79\x70\x68\x65\x69\x63'
}

def validate_magic_bytes(content: bytes, mime_type: str) -> bool:
    magic = MAGIC_BYTES.get(mime_type)
    if not magic:
        return True  # Unknown type, skip
    return content.startswith(magic)
```

---

## Storage Key Structure

### Key Format
```
{image_type}/{year}/{month}/{day}/{complaint_id_or_user_id}/{uuid}_{sanitized_filename}
```

### Examples
```
evidence/2024/01/15/507f1f77bcf86cd799439013/a1b2c3d4_pothole_photo.jpg
progress/2024/01/16/507f1f77bcf86cd799439013/e5f6g7h8_work_in_progress.png
completion/2024/01/18/507f1f77bcf86cd799439013/i9j0k1l2_completed_road.jpg
profile/2024/01/15/507f1f77bcf86cd799439011/m3n4o5p6_avatar.png
```

### Benefits
- Time-based partitioning for cleanup/archival
- Entity-scoped for access control
- UUID prefix prevents enumeration/collision
- Human-readable for debugging

---

## Image Service

```python
class ImageService:
    def __init__(
        self,
        repo: ComplaintImageRepository,
        storage: StorageProvider,
        validator: FileValidator
    ):
        self.repo = repo
        self.storage = storage
        self.validator = validator
    
    async def upload_complaint_image(
        self,
        complaint_id: ObjectId,
        user: User,
        file: UploadFile,
        image_type: str
    ) -> ComplaintImage:
        # 1. Validate complaint access
        complaint = await self._verify_complaint_access(complaint_id, user, image_type)
        
        # 2. Validate file
        validation = self.validator.validate(file, image_type)
        if not validation.valid:
            raise ValidationException(validation.error, validation.message)
        
        # 3. Read and validate content
        content = await file.read()
        if len(content) > self.validator.MAX_FILE_SIZES[image_type]:
            raise ValidationException("FILE_TOO_LARGE", "File exceeds size limit")
        
        if not validate_magic_bytes(content, file.content_type):
            raise ValidationException("INVALID_FILE_TYPE", "File content doesn't match MIME type")
        
        # 4. Generate storage key
        safe_name = self.validator.sanitize_filename(file.filename)
        key = self._generate_key(image_type, complaint_id, safe_name)
        
        # 5. Upload to storage
        upload_result = await self.storage.upload(
            io.BytesIO(content),
            key,
            file.content_type,
            metadata={
                'complaint_id': str(complaint_id),
                'uploaded_by': str(user.id),
                'image_type': image_type
            }
        )
        
        # 6. Create metadata record
        image = await self.repo.create(
            complaint_id=complaint_id,
            image_type=image_type,
            storage_path=upload_result.storage_key,
            original_filename=safe_name,
            mime_type=file.content_type,
            file_size=upload_result.file_size,
            checksum=upload_result.checksum,
            uploaded_by=user.id
        )
        
        return image
    
    async def get_image_url(self, image_id: ObjectId, user: User) -> str:
        image = await self.repo.get_by_id(image_id)
        
        # Authorization check
        await self._verify_image_access(image, user)
        
        # Generate signed URL (expires in 1 hour)
        return await self.storage.generate_presigned_url(image.storage_path, expires_in=3600)
    
    async def delete_image(self, image_id: ObjectId, user: User) -> bool:
        image = await self.repo.get_by_id(image_id)
        await self._verify_image_access(image, user, require_owner=True)
        
        # Soft delete
        await self.repo.soft_delete(image_id)
        
        # Optional: Delete from storage (or schedule cleanup job)
        # await self.storage.delete(image.storage_path)
        
        return True
    
    def _generate_key(self, image_type: str, entity_id: ObjectId, filename: str) -> str:
        now = datetime.utcnow()
        uuid_prefix = uuid.uuid4().hex[:8]
        return f"{image_type}/{now.year}/{now.month:02d}/{now.day:02d}/{entity_id}/{uuid_prefix}_{filename}"
    
    async def _verify_complaint_access(self, complaint_id, user, image_type):
        complaint = await self.complaint_repo.get_by_id(complaint_id)
        if not complaint:
            raise NotFoundException("Complaint not found")
        
        if image_type == 'evidence':
            # Only citizen who created complaint
            if complaint.user_id != user.id:
                raise ForbiddenException("Cannot add evidence to other's complaint")
        elif image_type in ['progress', 'completion']:
            # Only assigned staff or org admin
            if user.role not in ['organization_staff', 'organization_admin', 'admin']:
                raise ForbiddenException("Only staff can add progress/completion images")
            if complaint.assigned_to != user.id and user.role != 'organization_admin':
                raise ForbiddenException("Not assigned to this complaint")
        
        return complaint
    
    async def _verify_image_access(self, image, user, require_owner=False):
        complaint = await self.complaint_repo.get_by_id(image.complaint_id)
        
        if user.role == 'citizen':
            if complaint.user_id != user.id:
                raise ForbiddenException("Cannot access images for other's complaint")
        elif user.role in ['organization_staff', 'organization_admin']:
            if complaint.organization_id != user.organization_id:
                raise ForbiddenException("Cross-organization access denied")
        # Admin has access to all
        
        if require_owner and image.uploaded_by != user.id:
            raise ForbiddenException("Only uploader can delete")
```

---

## API Endpoints

### POST /complaints/{id}/images
**Request**: multipart/form-data
- `files`: Image file(s) (max 5 per request)
- `image_type`: "evidence" | "progress" | "completion"

**Response** (201):
```json
{
  "success": true,
  "message": "Images uploaded",
  "data": {
    "images": [
      {
        "id": "507f1f77bcf86cd799439016",
        "image_type": "evidence",
        "url": "https://cdn.example.com/evidence/2024/01/15/.../a1b2c3d4_photo.jpg",
        "file_size": 2048576,
        "mime_type": "image/jpeg",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ]
  }
}
```

### GET /complaints/{id}/images
**Response**: List of image metadata with signed URLs

### DELETE /complaints/{id}/images/{image_id}
Soft delete image (requires ownership)

---

## Profile Images

### POST /users/me/avatar
Upload profile image (type: `profile`)

### GET /users/me/avatar
Get signed URL for current user's avatar

---

## Security Considerations

### Access Control
| Image Type | Who Can Upload | Who Can View |
|------------|----------------|--------------|
| Evidence | Complaint owner (citizen) | Complaint owner, assigned staff, org admin, admin |
| Progress | Assigned staff, org admin | Same as evidence |
| Completion | Assigned staff, org admin | Same as evidence |
| Profile | User themselves | Public (if user allows) / authenticated users |

### URL Security
- **Signed URLs**: 1-hour expiry for private images
- **Public profile images**: Long-lived CDN URLs (if user makes public)
- **No direct storage access**: All access via API with auth

### Upload Security
- **File type validation**: MIME + magic bytes
- **Size limits**: Per image type
- **Filename sanitization**: Prevent path traversal
- **Virus scanning**: Future integration point (ClamAV)
- **Rate limiting**: 10 uploads/minute per user

---

## Cleanup & Retention

### Soft Delete
- `is_deleted` flag in metadata
- Actual storage deletion via background job
- 30-day grace period before permanent deletion

### Orphan Cleanup
- Job: Find storage objects without DB reference
- Job: Find DB records without storage object

### Compliance
- **GDPR**: User can request deletion of their images
- **Audit**: All upload/delete logged to audit_logs

---

## Configuration

### Environment Variables
```env
# Storage Provider: local | s3 | gridfs
STORAGE_PROVIDER=s3

# Local
STORAGE_LOCAL_PATH=/app/uploads
STORAGE_LOCAL_URL=http://localhost:8000/uploads

# S3 / MinIO
STORAGE_S3_BUCKET=voice2gov-images
STORAGE_S3_REGION=us-east-1
STORAGE_S3_ACCESS_KEY=xxx
STORAGE_S3_SECRET_KEY=xxx
STORAGE_S3_ENDPOINT=https://s3.amazonaws.com  # or MinIO endpoint
STORAGE_CDN_URL=https://cdn.voice2gov.example.com

# Limits (override defaults)
MAX_EVIDENCE_SIZE_MB=10
MAX_PROGRESS_SIZE_MB=5
MAX_PROFILE_SIZE_MB=2
```

---

## Testing

### Unit Tests
1. Key generation format
2. File validation (MIME, size, magic bytes)
3. Filename sanitization
4. Authorization logic per image type

### Integration Tests
1. Upload → metadata created → file in storage
2. Signed URL generation and expiry
3. Access control (citizen vs staff vs admin)
4. Soft delete → metadata marked, file remains
5. Multiple file upload in single request

### Mock Storage Provider
```python
class MockStorageProvider(StorageProvider):
    def __init__(self):
        self.files = {}
    
    async def upload(self, file, key, content_type, metadata=None):
        content = file.read()
        self.files[key] = content
        return UploadResult(key, f"mock://{key}", len(content), hashlib.sha256(content).hexdigest())
    
    async def generate_presigned_url(self, key, expires_in=3600):
        return f"mock://{key}?expires={expires_in}"
```
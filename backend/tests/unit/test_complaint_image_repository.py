"""Phase 1.3.4 — Complaint image repository unit tests (fake async collection)."""

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.repositories.complaint_image_repository import (
    ComplaintImageRepository,
    to_object_id,
)
from app.schemas.complaint_image import ImageType

CID = "507f1f77bcf86cd799439013"
CID2 = "507f1f77bcf86cd799439099"
UID = "507f1f77bcf86cd799439011"


class _InsertOne:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class _InsertMany:
    def __init__(self, ids: list[ObjectId]) -> None:
        self.inserted_ids = ids


class _Update:
    def __init__(self, modified: int) -> None:
        self.modified_count = modified


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = list(docs)

    def sort(self, field: str, direction: int = 1) -> "_Cursor":
        self._docs.sort(key=lambda doc: doc.get(field), reverse=direction < 0)
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self._docs if length is None else self._docs[:length]


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self._counter = 0

    async def create_index(self, keys: Any, **options: Any) -> str:
        self.indexes.append((keys, options))
        return options.get("name", "")

    async def insert_one(self, document: dict[str, Any]) -> _InsertOne:
        self._counter += 1
        oid = document.get("_id") or ObjectId(f"{self._counter:024x}")
        self.docs[str(oid)] = {**document, "_id": oid}
        return _InsertOne(oid)

    async def insert_many(self, documents: list[dict[str, Any]]) -> _InsertMany:
        ids = []
        for document in documents:
            ids.append((await self.insert_one(document)).inserted_id)
        return _InsertMany(ids)

    @staticmethod
    def _match(document: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in query.items())

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for document in self.docs.values():
            if self._match(document, query):
                return document
        return None

    def find(self, query: dict[str, Any]) -> _Cursor:
        return _Cursor([d for d in self.docs.values() if self._match(d, query)])

    async def count_documents(self, query: dict[str, Any]) -> int:
        return sum(1 for d in self.docs.values() if self._match(d, query))

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> _Update:
        for document in self.docs.values():
            if self._match(document, query):
                document.update(update.get("$set", {}))
                return _Update(1)
        return _Update(0)


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())


def make_metadata(
    complaint_id: str = CID,
    image_type: str = "evidence",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "complaint_id": ObjectId(complaint_id),
        "image_type": image_type,
        "storage_path": f"evidence/2024/01/15/{complaint_id}/abc_photo.jpg",
        "original_filename": "photo.jpg",
        "mime_type": "image/jpeg",
        "file_size": 1024,
        "width": None,
        "height": None,
        "checksum": "a" * 64,
        "uploaded_by": ObjectId(UID),
        "is_deleted": False,
        "created_at": created_at or datetime(2024, 1, 15, tzinfo=UTC),
    }


def make_repo() -> tuple[ComplaintImageRepository, FakeCollection]:
    database = FakeDatabase()
    repo = ComplaintImageRepository(database)  # type: ignore[arg-type]
    return repo, database["complaint_images"]


class TestToObjectId:
    def test_valid_string(self) -> None:
        assert to_object_id(CID) == ObjectId(CID)

    def test_object_id_passthrough(self) -> None:
        oid = ObjectId()
        assert to_object_id(oid) is oid

    def test_invalid_string(self) -> None:
        assert to_object_id("nope") is None

    def test_injection_dict(self) -> None:
        assert to_object_id({"$ne": None}) is None


class TestCreate:
    async def test_create_returns_id_and_persists(self) -> None:
        repo, collection = make_repo()
        image_id = await repo.create(make_metadata())
        assert image_id in collection.docs
        stored = collection.docs[image_id]
        assert stored["image_type"] == "evidence"
        assert stored["complaint_id"] == ObjectId(CID)
        assert stored["is_deleted"] is False

    async def test_create_many_returns_all_ids(self) -> None:
        repo, collection = make_repo()
        ids = await repo.create_many(
            [make_metadata(), make_metadata(image_type="progress"), make_metadata()]
        )
        assert len(ids) == 3
        assert len(collection.docs) == 3


class TestFindById:
    async def test_finds_by_id(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        found = await repo.find_by_id(image_id)
        assert found is not None
        assert str(found["_id"]) == image_id

    async def test_scoped_by_complaint(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        assert await repo.find_by_id(image_id, CID) is not None
        assert await repo.find_by_id(image_id, CID2) is None

    async def test_invalid_id_returns_none(self) -> None:
        repo, _ = make_repo()
        assert await repo.find_by_id("not-an-id") is None

    async def test_injection_operator_returns_none(self) -> None:
        repo, _ = make_repo()
        await repo.create(make_metadata())
        assert await repo.find_by_id({"$ne": None}) is None
        assert await repo.find_by_id(CID, {"$ne": None}) is None

    async def test_soft_deleted_hidden_by_default(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        await repo.soft_delete(image_id)
        assert await repo.find_by_id(image_id) is None
        assert await repo.find_by_id(image_id, include_deleted=True) is not None


class TestFindByComplaint:
    async def test_returns_only_matching_complaint(self) -> None:
        repo, _ = make_repo()
        await repo.create(make_metadata(CID))
        await repo.create(make_metadata(CID2))
        results = await repo.find_by_complaint(CID)
        assert len(results) == 1
        assert results[0]["complaint_id"] == ObjectId(CID)

    async def test_sorted_by_created_at(self) -> None:
        repo, _ = make_repo()
        early = make_metadata(created_at=datetime(2024, 1, 1, tzinfo=UTC))
        late = make_metadata(created_at=datetime(2024, 6, 1, tzinfo=UTC))
        await repo.create(late)
        await repo.create(early)
        results = await repo.find_by_complaint(CID)
        assert results[0]["created_at"] < results[1]["created_at"]

    async def test_type_filter(self) -> None:
        repo, _ = make_repo()
        await repo.create(make_metadata(image_type="evidence"))
        await repo.create(make_metadata(image_type="progress"))
        results = await repo.find_by_complaint(CID, image_type=ImageType.PROGRESS)
        assert len(results) == 1
        assert results[0]["image_type"] == "progress"

    async def test_excludes_deleted_by_default(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        await repo.soft_delete(image_id)
        assert await repo.find_by_complaint(CID) == []
        assert len(await repo.find_by_complaint(CID, include_deleted=True)) == 1

    async def test_invalid_complaint_id_returns_empty(self) -> None:
        repo, _ = make_repo()
        await repo.create(make_metadata())
        assert await repo.find_by_complaint("bogus") == []

    async def test_injection_returns_empty(self) -> None:
        repo, _ = make_repo()
        await repo.create(make_metadata())
        assert await repo.find_by_complaint({"$ne": None}) == []
        assert await repo.find_by_complaint(CID, image_type={"$ne": None}) == []


class TestCount:
    async def test_counts_active_only(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        await repo.create(make_metadata())
        assert await repo.count_by_complaint(CID) == 2
        await repo.soft_delete(image_id)
        assert await repo.count_by_complaint(CID) == 1
        assert await repo.count_by_complaint(CID, include_deleted=True) == 2

    async def test_invalid_id_returns_zero(self) -> None:
        repo, _ = make_repo()
        assert await repo.count_by_complaint("nope") == 0


class TestSoftDelete:
    async def test_marks_deleted(self) -> None:
        repo, collection = make_repo()
        image_id = await repo.create(make_metadata())
        assert await repo.soft_delete(image_id, CID) is True
        assert collection.docs[image_id]["is_deleted"] is True

    async def test_second_delete_returns_false(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata())
        await repo.soft_delete(image_id)
        assert await repo.soft_delete(image_id) is False

    async def test_unknown_returns_false(self) -> None:
        repo, _ = make_repo()
        assert await repo.soft_delete("000000000000000000000000") is False

    async def test_wrong_complaint_returns_false(self) -> None:
        repo, _ = make_repo()
        image_id = await repo.create(make_metadata(CID))
        assert await repo.soft_delete(image_id, CID2) is False


class TestIndexes:
    async def test_four_expected_indexes(self) -> None:
        repo, collection = make_repo()
        await repo.create_indexes()
        names = [options.get("name") for _, options in collection.indexes]
        assert names == [
            "idx_images_complaint_id",
            "idx_images_complaint_type",
            "idx_images_uploaded_by",
            "idx_images_created_at",
        ]

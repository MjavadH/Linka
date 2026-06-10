from enum import StrEnum


class StorageType(StrEnum):
    TELEGRAM = "telegram"
    MINIO = "minio"
    S3 = "s3"
    LOCAL = "local"


class FileAccessLevel(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class SubscriptionSource(StrEnum):
    MANUAL = "manual"
    PAYMENT_REQUEST = "payment_request"


class PaymentRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TemporaryMessageStatus(StrEnum):
    PENDING = "pending"
    DELETED = "deleted"
    FAILED = "failed"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class BroadcastRecipientStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class SponsorStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REVOKED = "revoked"


class SponsorExpirationType(StrEnum):
    DATE = "date"
    MEMBERS = "members"
    NONE = "none"

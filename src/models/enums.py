from enum import StrEnum


class StorageType(StrEnum):
    TELEGRAM = "telegram"
    MINIO = "minio"
    S3 = "s3"
    LOCAL = "local"


class FileAccessLevel(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


class ContentType(StrEnum):
    MOVIE = "movie"
    EPISODE = "episode"


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
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BroadcastTargetType(StrEnum):
    ALL = "all"
    PREMIUM = "premium"
    FREE = "free"


class BroadcastResultStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    BLOCKED = "blocked"
    DELIVERY_ERROR = "delivery_error"
    FAILED = "failed"


# Backward-compatible alias for older imports.
BroadcastRecipientStatus = BroadcastResultStatus


class SponsorStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REVOKED = "revoked"


class SponsorExpirationType(StrEnum):
    DATE = "date"
    MEMBERS = "members"
    NONE = "none"

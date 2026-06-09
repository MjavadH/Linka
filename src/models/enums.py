from enum import StrEnum


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

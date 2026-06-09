from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from models.enums import PaymentRequestStatus, SubscriptionSource
from models.payment import PaymentRequest
from repositories.base import BaseRepository
from repositories.subscriptions import SubscriptionRepository


class PaymentRequestRepository(BaseRepository[PaymentRequest]):
    async def create(
        self,
        user_id: int,
        phone_number: str,
        payment_notes: str | None,
        screenshots_metadata: list[dict[str, str]],
    ) -> PaymentRequest:
        request = PaymentRequest(
            user_id=user_id,
            phone_number=phone_number,
            payment_notes=payment_notes,
            screenshots_metadata=screenshots_metadata,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get_pending(self, request_id: int) -> PaymentRequest | None:
        result = await self.session.execute(
            select(PaymentRequest).where(
                PaymentRequest.id == request_id,
                PaymentRequest.status == PaymentRequestStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def approve(
        self, request_id: int, admin_user_id: int, duration: timedelta, note: str | None
    ) -> PaymentRequest:
        request = await self.get_pending(request_id)
        if request is None:
            raise ValueError("Payment request is not pending")
        request.status = PaymentRequestStatus.APPROVED
        request.reviewed_by_admin_id = admin_user_id
        request.review_note = note
        request.reviewed_at = datetime.now(UTC)
        await SubscriptionRepository(self.session).extend(
            request.user_id,
            duration,
            source=SubscriptionSource.PAYMENT_REQUEST,
            admin_id=admin_user_id,
            note=note,
        )
        await self.session.flush()
        return request

    async def reject(self, request_id: int, admin_user_id: int, note: str | None) -> PaymentRequest:
        request = await self.get_pending(request_id)
        if request is None:
            raise ValueError("Payment request is not pending")
        request.status = PaymentRequestStatus.REJECTED
        request.reviewed_by_admin_id = admin_user_id
        request.review_note = note
        request.reviewed_at = datetime.now(UTC)
        await self.session.flush()
        return request

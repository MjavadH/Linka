from datetime import timedelta

from models.payment import PaymentRequest
from repositories.payment_requests import PaymentRequestRepository


class PaymentRequestService:
    def __init__(self, repository: PaymentRequestRepository) -> None:
        self.repository = repository

    async def create_request(
        self,
        user_id: int,
        phone_number: str,
        payment_notes: str | None,
        screenshots_metadata: list[dict[str, str]],
    ) -> PaymentRequest:
        return await self.repository.create(
            user_id=user_id,
            phone_number=phone_number,
            payment_notes=payment_notes,
            screenshots_metadata=screenshots_metadata,
        )

    async def approve(
        self, request_id: int, admin_user_id: int, days: int, note: str | None
    ) -> PaymentRequest:
        if days <= 0:
            raise ValueError("Premium duration must be positive")
        return await self.repository.approve(request_id, admin_user_id, timedelta(days=days), note)

    async def reject(self, request_id: int, admin_user_id: int, note: str | None) -> PaymentRequest:
        return await self.repository.reject(request_id, admin_user_id, note)

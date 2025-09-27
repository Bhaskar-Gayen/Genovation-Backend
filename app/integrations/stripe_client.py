import stripe
import logging
from config import settings
from fastapi import Request, HTTPException, status
from typing import Dict, Any, Optional

logger = logging.getLogger("stripe_client")

# Configure Stripe
stripe.api_key = settings.stripe_secret_key
stripe.api_version = "2022-11-15"


class StripeClient:
    @staticmethod
    def create_checkout_session(
            user_id: str,
            customer_email: str,
            success_url: str,
            cancel_url: str
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session for Pro subscription"""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{
                    "price": settings.stripe_price_id_pro,
                    "quantity": 1,
                }],
                customer_email=customer_email,
                client_reference_id=str(user_id),
                metadata={"user_id": str(user_id)},
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
            )

            logger.info(f"Created checkout session for user {user_id}: {session.id}")
            return {
                "session_id": session.id,
                "checkout_url": session.url,
                "status": "created"
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create checkout session"
            )

    @staticmethod
    def get_customer(customer_id: str) -> Optional[stripe.Customer]:
        """Retrieve a Stripe customer"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if customer.get("deleted"):
                return None
            return customer
        except stripe.error.InvalidRequestError:
            logger.warning(f"Customer not found: {customer_id}")
            return None
        except stripe.error.StripeError as e:
            logger.error(f"Stripe get customer error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    def create_customer(email: str, user_id: str, name: str = None) -> stripe.Customer:
        """Create a new Stripe customer"""
        try:
            customer_data = {
                "email": email,
                "metadata": {"user_id": str(user_id)}
            }
            if name:
                customer_data["name"] = name

            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created Stripe customer for user {user_id}: {customer.id}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Stripe create customer error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    def update_customer(customer_id: str, **kwargs) -> stripe.Customer:
        """Update a Stripe customer"""
        try:
            customer = stripe.Customer.modify(customer_id, **kwargs)
            logger.info(f"Updated Stripe customer: {customer_id}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Stripe update customer error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
        """Retrieve a Stripe subscription"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.InvalidRequestError:
            logger.warning(f"Subscription not found: {subscription_id}")
            return None
        except stripe.error.StripeError as e:
            logger.error(f"Stripe get subscription error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> stripe.Subscription:
        """Cancel a Stripe subscription"""
        try:
            if at_period_end:
                # Cancel at period end (recommended)
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
                logger.info(f"Scheduled subscription cancellation at period end: {subscription_id}")
            else:
                # Cancel immediately
                subscription = stripe.Subscription.delete(subscription_id)
                logger.info(f"Cancelled subscription immediately: {subscription_id}")

            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancel subscription error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    def get_customer_subscriptions(customer_id: str) -> list:
        """Get all subscriptions for a customer"""
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status="all",
                limit=10
            )
            return subscriptions.data
        except stripe.error.StripeError as e:
            logger.error(f"Stripe get customer subscriptions error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )

    @staticmethod
    async def handle_webhook(request: Request) -> Dict[str, Any]:
        """Handle and validate Stripe webhook"""
        try:
            # Get the request body
            payload = await request.body()
            sig_header = request.headers.get("stripe-signature")

            if not sig_header:
                logger.error("Missing Stripe signature header")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing Stripe signature"
                )

            # Verify the webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )

            logger.info(f"Received verified Stripe webhook: {event['type']} - {event['id']}")
            return event

        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed"
            )

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Construct and verify webhook event (helper method)"""
        try:
            return stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            raise
        except Exception:
            raise
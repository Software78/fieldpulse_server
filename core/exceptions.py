"""
Custom exceptions and exception handler for fieldpulse project.
"""
import logging
import traceback
from rest_framework.exceptions import APIException
from rest_framework import status
from rest_framework.views import exception_handler
from django.http import Http404
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    NotFound,
    Throttled,
)

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that returns consistent error format.
    
    Response format:
    {
        "error": "error_code",
        "message": "...",
        "details": {}
    }
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    # Determine error code and status
    error_code = "server_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "An internal server error occurred."
    details = {}
    
    # Map DRF exceptions to error codes
    if isinstance(exc, ValidationError):
        error_code = "validation_error"
        status_code = status.HTTP_400_BAD_REQUEST
        message = "Validation failed."
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            details = exc.detail
        else:
            message = str(exc)
    
    elif isinstance(exc, AuthenticationFailed):
        error_code = "authentication_failed"
        status_code = status.HTTP_401_UNAUTHORIZED
        message = "Authentication failed."
        details = {"detail": str(exc)}
    
    elif isinstance(exc, NotAuthenticated):
        error_code = "not_authenticated"
        status_code = status.HTTP_401_UNAUTHORIZED
        message = "Authentication credentials were not provided."
        details = {"detail": str(exc)}
    
    elif isinstance(exc, (PermissionDenied, DRFPermissionDenied)):
        error_code = "permission_denied"
        status_code = status.HTTP_403_FORBIDDEN
        message = "Permission denied."
        details = {"detail": str(exc)}
    
    elif isinstance(exc, (NotFound, Http404)):
        error_code = "not_found"
        status_code = status.HTTP_404_NOT_FOUND
        message = "Resource not found."
        details = {"detail": str(exc)}
    
    elif isinstance(exc, Throttled):
        error_code = "rate_limited"
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        message = "Rate limit exceeded."
        details = {
            "detail": str(exc),
            "retry_after": getattr(exc, 'wait', None)
        }
    
    # Handle our custom exceptions
    elif isinstance(exc, BaseServiceError):
        error_code = exc.default_code
        status_code = exc.status_code
        message = str(exc.default_detail)
        details = {"detail": str(exc)}
    
    # If DRF handler returned a response, use its status code
    if response is not None:
        status_code = response.status_code
    
    # Log unhandled exceptions
    if error_code == "server_error":
        logger.error(
            f"Unhandled exception: {exc.__class__.__name__}: {str(exc)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
    
    # Create consistent error response
    error_response = {
        "error": error_code,
        "message": message,
        "details": details
    }
    
    # If DRF handler returned a response, modify its data
    if response is not None:
        response.data = error_response
        return response
    
    # Otherwise create a new response
    from rest_framework.response import Response
    return Response(error_response, status=status_code)


class BaseServiceError(APIException):
    """Base exception for service errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'A service error occurred.'
    default_code = 'service_error'


class ValidationError(BaseServiceError):
    """Exception for validation errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Validation failed.'
    default_code = 'validation_error'


class NotFoundError(BaseServiceError):
    """Exception for resource not found errors."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'not_found'


class PermissionDeniedError(BaseServiceError):
    """Exception for permission denied errors."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied.'
    default_code = 'permission_denied'


class AuthenticationError(BaseServiceError):
    """Exception for authentication errors."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication failed.'
    default_code = 'authentication_error'


class RateLimitError(BaseServiceError):
    """Exception for rate limit exceeded errors."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Rate limit exceeded.'
    default_code = 'rate_limit_exceeded'


class ServiceUnavailableError(BaseServiceError):
    """Exception for service unavailable errors."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service temporarily unavailable.'
    default_code = 'service_unavailable'


class ConflictError(BaseServiceError):
    """Exception for conflict errors."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Resource conflict.'
    default_code = 'conflict_error'


class PaymentRequiredError(BaseServiceError):
    """Exception for payment required errors."""
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment required.'
    default_code = 'payment_required'

"""
Custom permission classes for fieldpulse project.
"""
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Read-only access is allowed for any authenticated user.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions are only allowed to the owner
        return hasattr(obj, 'owner') and obj.owner == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit.
    Read-only access is allowed for any authenticated user.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions are only allowed to admin users
        return request.user and request.user.is_staff


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        return hasattr(obj, 'owner') and obj.owner == request.user


class IsStaffOrOwner(permissions.BasePermission):
    """
    Custom permission to allow staff users or owners to access an object.
    """
    
    def has_object_permission(self, request, view, obj):
        # Staff users can access any object
        if request.user and request.user.is_staff:
            return True
        
        # Owners can access their own objects
        return hasattr(obj, 'owner') and obj.owner == request.user


class IsAuthenticatedAndActive(permissions.BasePermission):
    """
    Custom permission to only allow authenticated and active users.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            not isinstance(request.user, AnonymousUser) and
            request.user.is_authenticated and
            request.user.is_active
        )


class HasCompanyAccess(permissions.BasePermission):
    """
    Custom permission to check if user has access to a specific company.
    """
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if object has a company field
        if not hasattr(obj, 'company'):
            return True  # If no company field, allow access
        
        # Check if user is associated with the company
        user_company = getattr(request.user, 'company', None)
        return user_company == obj.company


class IsSuperUserOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow superusers to edit.
    Read-only access is allowed for any authenticated user.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions are only allowed to superusers
        return request.user and request.user.is_superuser


class CanManageMedia(permissions.BasePermission):
    """
    Custom permission for media management.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers and staff can manage all media
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check specific permissions based on action
        if request.method in ['POST', 'PUT', 'PATCH']:
            return hasattr(request.user, 'can_upload_media') and request.user.can_upload_media
        elif request.method == 'DELETE':
            return hasattr(request.user, 'can_delete_media') and request.user.can_delete_media
        
        return True  # GET requests are allowed for authenticated users


class IsTechnicianOwner(permissions.BasePermission):
    """
    Custom permission to only allow technicians who own a job to access it.
    Checks obj.technician == request.user for Job objects.
    Used by job detail, status, and checklist views.
    """
    
    def has_object_permission(self, request, view, obj):
        # Check if object has a technician field
        if not hasattr(obj, 'technician'):
            return False
        
        # Check if the current user is the assigned technician
        return obj.technician == request.user


class CanSyncData(permissions.BasePermission):
    """
    Custom permission for data synchronization.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers and staff can sync data
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check if user has sync permission
        return hasattr(request.user, 'can_sync_data') and request.user.can_sync_data

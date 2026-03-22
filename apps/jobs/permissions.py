from rest_framework import permissions


class IsTechnicianOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a job to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return obj.technician == request.user
        
        # Write permissions are only allowed to the technician of the job
        return obj.technician == request.user

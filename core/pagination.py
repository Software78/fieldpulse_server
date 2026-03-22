"""
Custom pagination classes for fieldpulse project.
"""
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class CursorPagination(CursorPagination):
    """Cursor pagination with configurable page size."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'
    
    def get_paginated_response_schema(self, schema):
        """Return schema for paginated response."""
        return {
            'type': 'object',
            'properties': {
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': 'http://api.example.org/accounts/?cursor=cD00ODY1NDQ2MDE%3D'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri',
                    'example': 'http://api.example.org/accounts/?cursor=cj0xJnA9NDg2NTQ2MDE%3D'
                },
                'results': schema,
                'count': {
                    'type': 'integer',
                    'example': 123
                },
                'page_info': {
                    'type': 'object',
                    'properties': {
                        'has_next': {
                            'type': 'boolean',
                            'example': True
                        },
                        'has_previous': {
                            'type': 'boolean',
                            'example': False
                        },
                        'page_size': {
                            'type': 'integer',
                            'example': 20
                        }
                    }
                }
            }
        }
    
    def get_paginated_response(self, data):
        """Return paginated response with additional metadata."""
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'count': len(data),
            'page_info': {
                'has_next': self.has_next,
                'has_previous': self.has_previous,
                'page_size': self.page_size
            }
        })


class LargeResultSetPagination(CursorPagination):
    """Pagination optimized for large result sets."""
    
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    ordering = '-id'


class SmallResultSetPagination(CursorPagination):
    """Pagination optimized for small result sets."""
    
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    ordering = '-id'

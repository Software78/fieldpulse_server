import django_filters
from django.db.models import Q
from .models import Job


class JobFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='scheduled_start', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='scheduled_start', lookup_expr='lte')
    sync_since = django_filters.DateTimeFilter(field_name='server_updated_at', lookup_expr='gte')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Job
        fields = ['status', 'date_from', 'date_to', 'search', 'sync_since']
    
    def filter_search(self, queryset, name, value):
        """
        Search across customer_name, address, and id fields
        """
        if value:
            queryset = queryset.filter(
                Q(customer_name__icontains=value) |
                Q(address__icontains=value) |
                Q(id__icontains=value)
            )
        return queryset

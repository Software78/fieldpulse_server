import uuid
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from faker import Faker

from apps.sync.models import Job, ChecklistSchema, ChecklistResponse

User = get_user_model()
fake = Faker('en_US')

# US cities with approximate coordinates
US_CITIES = [
    {'name': 'New York, NY', 'lat': 40.7128, 'lng': -74.0060},
    {'name': 'Los Angeles, CA', 'lat': 34.0522, 'lng': -118.2437},
    {'name': 'Chicago, IL', 'lat': 41.8781, 'lng': -87.6298},
    {'name': 'Houston, TX', 'lat': 29.7604, 'lng': -95.3698},
    {'name': 'Phoenix, AZ', 'lat': 33.4484, 'lng': -112.0740},
    {'name': 'Philadelphia, PA', 'lat': 39.9526, 'lng': -75.1652},
]

# Job descriptions for field service scenarios
JOB_DESCRIPTIONS = [
    'HVAC inspection and maintenance',
    'Plumbing repair for kitchen sink',
    'Electrical fault diagnosis and repair',
    'Appliance installation (washing machine)',
    'Air conditioning unit replacement',
    'Water heater installation and setup',
    'Electrical panel upgrade',
    'Gas line inspection and repair',
    'Commercial refrigeration service',
    'Home security system installation',
]

class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--jobs',
            type=int,
            default=120,
            help='Number of jobs to create (default: 120)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding'
        )

    def handle(self, *args, **options):
        num_jobs = options['jobs']
        clear_data = options['clear']
        
        if clear_data:
            self.clear_existing_data()
            self.stdout.write(self.style.SUCCESS('Cleared existing data'))
        
        # Create technician users
        technicians = self.create_technicians()
        
        # Create jobs
        jobs = self.create_jobs(technicians, num_jobs)
        
        # Create checklist schemas and responses
        self.create_checklists(jobs)
        
        # Print summary
        pending_count = Job.objects.filter(status='pending').count()
        in_progress_count = Job.objects.filter(status='in_progress').count()
        completed_count = Job.objects.filter(status='completed').count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded: {len(technicians)} users, {len(jobs)} jobs '
                f'({pending_count} pending, {in_progress_count} in_progress, {completed_count} completed)'
            )
        )

    def clear_existing_data(self):
        """Clear all existing jobs, checklists, and technician users"""
        ChecklistResponse.objects.all().delete()
        ChecklistSchema.objects.all().delete()
        Job.objects.all().delete()
        
        # Delete only the technician users we create
        User.objects.filter(email__in=[
            'tech1@fieldpulse.com',
            'tech2@fieldpulse.com', 
            'tech3@fieldpulse.com'
        ]).delete()

    def create_technicians(self):
        """Create three technician users"""
        technicians_data = [
            {
                'email': 'tech1@fieldpulse.com',
                'first_name': 'Alex',
                'last_name': 'Torres',
            },
            {
                'email': 'tech2@fieldpulse.com',
                'first_name': 'Jordan',
                'last_name': 'Lee',
            },
            {
                'email': 'tech3@fieldpulse.com',
                'first_name': 'Sam',
                'last_name': 'Patel',
            },
        ]
        
        technicians = []
        for tech_data in technicians_data:
            user, created = User.objects.get_or_create(
                email=tech_data['email'],
                defaults={
                    'username': tech_data['email'],
                    'first_name': tech_data['first_name'],
                    'last_name': tech_data['last_name'],
                    'is_staff': False,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('password123')
                user.save()
            
            technicians.append(user)
        
        return technicians

    def create_jobs(self, technicians, num_jobs):
        """Create jobs distributed evenly across technicians"""
        jobs = []
        jobs_per_status = num_jobs // 3
        statuses = ['pending'] * jobs_per_status + ['in_progress'] * jobs_per_status + ['completed'] * jobs_per_status
        
        # Add remaining jobs to pending if not evenly divisible
        remaining = num_jobs - len(statuses)
        statuses.extend(['pending'] * remaining)
        
        random.shuffle(statuses)
        
        for i, status in enumerate(statuses):
            technician = technicians[i % len(technicians)]
            city = random.choice(US_CITIES)
            
            # Generate coordinates within ~0.1 degrees of city center
            lat_offset = random.uniform(-0.1, 0.1)
            lng_offset = random.uniform(-0.1, 0.1)
            
            # Generate dates spread over past 30 days and next 14 days
            days_offset = random.randint(-30, 14)
            scheduled_start = timezone.now() + timedelta(days=days_offset)
            duration_hours = random.randint(2, 8)
            scheduled_end = scheduled_start + timedelta(hours=duration_hours)
            
            # For overdue jobs, make scheduled_end in the past
            if status in ['pending', 'in_progress'] and random.random() < 0.3:  # 30% chance of overdue
                scheduled_start = timezone.now() - timedelta(days=random.randint(1, 10))
                scheduled_end = scheduled_start + timedelta(hours=duration_hours)
            
            job = Job.objects.create(
                technician=technician,
                customer_name=fake.name(),
                customer_phone=self.generate_us_phone(),
                address=fake.street_address() + ', ' + city['name'],
                latitude=city['lat'] + lat_offset,
                longitude=city['lng'] + lng_offset,
                job_description=random.choice(JOB_DESCRIPTIONS),
                notes=fake.sentence() if random.random() < 0.7 else '',  # 30% chance of blank notes
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                status=status,
            )
            
            jobs.append(job)
        
        return jobs

    def create_checklists(self, jobs):
        """Create checklist schemas and responses for all jobs"""
        for job in jobs:
            # Create checklist schema with all 9 field types
            schema_fields = self.generate_checklist_schema()
            checklist_schema = ChecklistSchema.objects.create(
                job=job,
                fields=schema_fields
            )
            
            # Create response for completed jobs
            if job.status == 'completed':
                response_data = self.generate_checklist_response(schema_fields)
                ChecklistResponse.objects.create(
                    job=job,
                    data=response_data,
                    is_complete=True,
                    completed_at=timezone.now() - timedelta(hours=random.randint(1, 24))
                )

    def generate_checklist_schema(self):
        """Generate checklist schema with all 9 field types"""
        return {
            'fields': [
                {
                    'id': 'customer_signature',
                    'label': 'Customer Signature',
                    'type': 'signature',
                    'required': True
                },
                {
                    'id': 'work_area_photo',
                    'label': 'Work Area Photo',
                    'type': 'photo',
                    'required': True
                },
                {
                    'id': 'completion_photo',
                    'label': 'Completion Photo',
                    'type': 'photo',
                    'required': False
                },
                {
                    'id': 'technician_notes',
                    'label': 'Technician Notes',
                    'type': 'textarea',
                    'required': False
                },
                {
                    'id': 'customer_rating',
                    'label': 'Customer Rating',
                    'type': 'select',
                    'required': True,
                    'options': ['Excellent', 'Good', 'Fair', 'Poor']
                },
                {
                    'id': 'services_performed',
                    'label': 'Services Performed',
                    'type': 'multi_select',
                    'required': True,
                    'options': ['Inspection', 'Repair', 'Installation', 'Maintenance', 'Consultation']
                },
                {
                    'id': 'hours_worked',
                    'label': 'Hours Worked',
                    'type': 'number',
                    'required': True,
                    'min_value': 0.5,
                    'max_value': 12
                },
                {
                    'id': 'safety_check_passed',
                    'label': 'Safety Check Passed',
                    'type': 'checkbox',
                    'required': True
                },
                {
                    'id': 'customer_reference',
                    'label': 'Customer Reference Number',
                    'type': 'text',
                    'required': False,
                    'max_length': 50
                }
            ]
        }

    def generate_checklist_response(self, schema_fields):
        """Generate realistic response data for checklist fields"""
        response = {}
        
        for field in schema_fields['fields']:
            field_id = field['id']
            field_type = field['type']
            
            if field_type == 'signature':
                response[field_id] = str(uuid.uuid4())
            elif field_type == 'photo':
                response[field_id] = [str(uuid.uuid4()) for _ in range(random.randint(1, 2))]
            elif field_type == 'text':
                response[field_id] = fake.bothify(text='REF-????')
            elif field_type == 'textarea':
                response[field_id] = fake.sentence()
            elif field_type == 'number':
                min_val = field.get('min_value', 1)
                max_val = field.get('max_value', 10)
                response[field_id] = round(random.uniform(min_val, max_val), 2)
            elif field_type == 'select':
                response[field_id] = random.choice(field['options'])
            elif field_type == 'multi_select':
                num_choices = random.randint(1, min(3, len(field['options'])))
                response[field_id] = random.sample(field['options'], num_choices)
            elif field_type == 'checkbox':
                response[field_id] = True
        
        return response

    def generate_us_phone(self):
        """Generate a US phone number in standard format"""
        area_code = random.randint(200, 999)
        exchange = random.randint(200, 999)
        number = random.randint(1000, 9999)
        return f"({area_code}) {exchange}-{number}"

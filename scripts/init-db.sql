-- Initialize database for fieldpulse project
-- This script runs when PostgreSQL container starts for the first time

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types if needed
-- (Will be added as models are created)

-- Seed data for fieldpulse project
-- This section creates realistic test data for development

-- Clear existing seed data (only our test data)
-- Delete in proper order to respect foreign key constraints
DELETE FROM sync_checklistresponse WHERE job_id IN (
    SELECT id FROM sync_job WHERE technician_id IN (
        SELECT id FROM auth_users WHERE email IN (
            'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
        )
    )
);
DELETE FROM sync_checklistschema WHERE job_id IN (
    SELECT id FROM sync_job WHERE technician_id IN (
        SELECT id FROM auth_users WHERE email IN (
            'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
        )
    )
);
DELETE FROM media_app_photoupload WHERE job_id IN (
    SELECT id FROM sync_job WHERE technician_id IN (
        SELECT id FROM auth_users WHERE email IN (
            'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
        )
    )
);
DELETE FROM media_app_signatureupload WHERE job_id IN (
    SELECT id FROM sync_job WHERE technician_id IN (
        SELECT id FROM auth_users WHERE email IN (
            'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
        )
    )
);
DELETE FROM sync_job WHERE technician_id IN (
    SELECT id FROM auth_users WHERE email IN (
        'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
    )
);
DELETE FROM auth_users WHERE email IN (
    'tech1@fieldpulse.com', 'tech2@fieldpulse.com', 'tech3@fieldpulse.com'
);

-- Create technician users
INSERT INTO auth_users (username, email, first_name, last_name, password, is_staff, is_active, is_superuser, date_joined, phone, updated_at) VALUES
('tech1@fieldpulse.com', 'tech1@fieldpulse.com', 'Alex', 'Torres', 'pbkdf2_sha256$720000$W2gLAYHa5AsLbuA9JEHkp2$14qhYa8wccmxD7THYKJ3PQgaLEC1GWqF8hrIlPXf+Pw=', false, true, false, NOW() - INTERVAL '30 days', '', NOW()),
('tech2@fieldpulse.com', 'tech2@fieldpulse.com', 'Jordan', 'Lee', 'pbkdf2_sha256$720000$W2gLAYHa5AsLbuA9JEHkp2$14qhYa8wccmxD7THYKJ3PQgaLEC1GWqF8hrIlPXf+Pw=', false, true, false, NOW() - INTERVAL '30 days', '', NOW()),
('tech3@fieldpulse.com', 'tech3@fieldpulse.com', 'Sam', 'Patel', 'pbkdf2_sha256$720000$W2gLAYHa5AsLbuA9JEHkp2$14qhYa8wccmxD7THYKJ3PQgaLEC1GWqF8hrIlPXf+Pw=', false, true, false, NOW() - INTERVAL '30 days', '', NOW())
ON CONFLICT (username) DO NOTHING;

-- Create 90 jobs with realistic field service data (10 per category per user)
-- Categories: HVAC, Plumbing, Electrical, Appliance, Air Conditioning, Water Heater, 
-- Electrical Panel, Gas Line, Commercial Refrigeration, Home Security

-- Create a function to generate random US phone numbers
CREATE OR REPLACE FUNCTION generate_us_phone() RETURNS TEXT AS $$
BEGIN
    RETURN '(555)' || LPAD(floor(random() * 900 + 100)::text, 3, '0') || '-' || LPAD(floor(random() * 9000 + 1000)::text, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- Create a function to generate random names
CREATE OR REPLACE FUNCTION generate_name() RETURNS TEXT AS $$
DECLARE
    first_names TEXT[] := ARRAY['Jennifer', 'Robert', 'Maria', 'David', 'Sarah', 'Michael', 'Lisa', 'James', 'Patricia', 'Charles', 'Nancy', 'Daniel', 'Betty', 'Richard', 'Linda', 'William', 'Barbara', 'Joseph', 'Susan', 'Thomas', 'Jessica', 'Christopher', 'Ashley', 'Matthew', 'Kimberly', 'Anthony', 'Emily', 'Mark', 'Donna', 'Steven'];
    last_names TEXT[] := ARRAY['Martinez', 'Johnson', 'Garcia', 'Smith', 'Williams', 'Brown', 'Anderson', 'Wilson', 'Moore', 'Taylor', 'Thomas', 'Jackson', 'White', 'Harris', 'Martin', 'Thompson', 'Garcia', 'Martinez', 'Robinson', 'Clark'];
BEGIN
    RETURN first_names[floor(random() * array_length(first_names, 1) + 1)] || ' ' || last_names[floor(random() * array_length(last_names, 1) + 1)];
END;
$$ LANGUAGE plpgsql;

-- Create a function to generate random addresses
CREATE OR REPLACE FUNCTION generate_address() RETURNS TEXT AS $$
DECLARE
    street_numbers TEXT[] := ARRAY['123', '456', '789', '321', '654', '987', '147', '258', '369', '741', '852', '963'];
    street_names TEXT[] := ARRAY['Main St', 'Oak Ave', 'Pine Rd', 'Elm St', 'Maple Dr', 'Cedar Ln', 'Birch St', 'Spruce Way', 'Willow Ave', 'Aspen Ct', 'Redwood Blvd', 'Sequoia Dr', 'Fir St', 'Pine Ln'];
    cities TEXT[] := ARRAY['New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Houston, TX', 'Phoenix, AZ', 'Philadelphia, PA'];
BEGIN
    RETURN street_numbers[floor(random() * array_length(street_numbers, 1) + 1)] || ' ' || 
           street_names[floor(random() * array_length(street_names, 1) + 1)] || ', ' ||
           cities[floor(random() * array_length(cities, 1) + 1)];
END;
$$ LANGUAGE plpgsql;

-- Create a function to generate coordinates near city centers
CREATE OR REPLACE FUNCTION generate_lat(city_name TEXT) RETURNS DECIMAL AS $$
BEGIN
    CASE city_name
        WHEN 'New York, NY' THEN RETURN 40.7128 + (random() - 0.5) * 0.2;
        WHEN 'Los Angeles, CA' THEN RETURN 34.0522 + (random() - 0.5) * 0.2;
        WHEN 'Chicago, IL' THEN RETURN 41.8781 + (random() - 0.5) * 0.2;
        WHEN 'Houston, TX' THEN RETURN 29.7604 + (random() - 0.5) * 0.2;
        WHEN 'Phoenix, AZ' THEN RETURN 33.4484 + (random() - 0.5) * 0.2;
        WHEN 'Philadelphia, PA' THEN RETURN 39.9526 + (random() - 0.5) * 0.2;
        ELSE RETURN 40.7128 + (random() - 0.5) * 0.2;
    END CASE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generate_lng(city_name TEXT) RETURNS DECIMAL AS $$
BEGIN
    CASE city_name
        WHEN 'New York, NY' THEN RETURN -74.0060 + (random() - 0.5) * 0.2;
        WHEN 'Los Angeles, CA' THEN RETURN -118.2437 + (random() - 0.5) * 0.2;
        WHEN 'Chicago, IL' THEN RETURN -87.6298 + (random() - 0.5) * 0.2;
        WHEN 'Houston, TX' THEN RETURN -95.3698 + (random() - 0.5) * 0.2;
        WHEN 'Phoenix, AZ' THEN RETURN -112.0740 + (random() - 0.5) * 0.2;
        WHEN 'Philadelphia, PA' THEN RETURN -75.1652 + (random() - 0.5) * 0.2;
        ELSE RETURN -74.0060 + (random() - 0.5) * 0.2;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Create all 90 jobs using a single INSERT with generated data (10 per category per user)
INSERT INTO sync_job (id, technician_id, customer_name, customer_phone, address, latitude, longitude, job_description, notes, scheduled_start, scheduled_end, status, created_at, server_updated_at)
SELECT 
    uuid_generate_v4(),
    technician_id,
    generate_name() as customer_name,
    generate_us_phone() as customer_phone,
    address,
    generate_lat(SPLIT_PART(address, ', ', 2)) as latitude,
    generate_lng(SPLIT_PART(address, ', ', 2)) as longitude,
    job_descriptions[category_index + 1] as job_description,
    CASE WHEN random() < 0.7 THEN 'Customer contacted and confirmed appointment' ELSE '' END as notes,
    scheduled_start,
    scheduled_start + (floor(random() * 7 + 2) || ' hours')::interval as scheduled_end,
    job_status,
    NOW() - (random() * 30 || ' days')::interval as created_at,
    NOW() as server_updated_at
FROM (
    -- Generate 90 rows: 3 technicians × 10 categories × 3 jobs per category
    SELECT 
        CASE technician_index 
            WHEN 0 THEN (SELECT id FROM auth_users WHERE email = 'tech1@fieldpulse.com')
            WHEN 1 THEN (SELECT id FROM auth_users WHERE email = 'tech2@fieldpulse.com')
            WHEN 2 THEN (SELECT id FROM auth_users WHERE email = 'tech3@fieldpulse.com')
        END as technician_id,
        category_index,
        CASE 
            WHEN (technician_index * 10 + category_index) < 30 THEN 'pending'
            WHEN (technician_index * 10 + category_index) < 60 THEN 'in_progress'
            ELSE 'completed'
        END as job_status,
        CASE 
            WHEN (technician_index * 10 + category_index) < 30 THEN NOW() + (random() * 14 || ' days')::interval
            WHEN (technician_index * 10 + category_index) < 60 THEN NOW() - (random() * 1 || ' days')::interval
            ELSE NOW() - (random() * 30 || ' days')::interval
        END as scheduled_start,
        generate_address() as address
    FROM generate_series(0, 2) technician_index,
         generate_series(0, 9) category_index
) job_data,
LATERAL (
    SELECT ARRAY[
        'HVAC inspection and maintenance',
        'Plumbing repair for kitchen sink',
        'Electrical fault diagnosis and repair',
        'Appliance installation (washing machine)',
        'Air conditioning unit replacement',
        'Water heater installation and setup',
        'Electrical panel upgrade',
        'Gas line inspection and repair',
        'Commercial refrigeration service',
        'Home security system installation'
    ] as job_descriptions
) descriptions;

-- Clean up temporary functions
DROP FUNCTION IF EXISTS generate_us_phone();
DROP FUNCTION IF EXISTS generate_name();
DROP FUNCTION IF EXISTS generate_address();
DROP FUNCTION IF EXISTS generate_lat(TEXT);
DROP FUNCTION IF EXISTS generate_lng(TEXT);

-- Create checklist schemas for all jobs
-- Generate schemas for all 90 jobs
INSERT INTO sync_checklistschema (job_id, fields, version)
SELECT id, '{
    "fields": [
        {"id": "customer_signature", "label": "Customer Signature", "type": "signature", "required": true},
        {"id": "work_area_photo", "label": "Work Area Photo", "type": "photo", "required": true},
        {"id": "safety_check", "label": "Safety Check Passed", "type": "toggle", "required": true},
        {"id": "work_description", "label": "Work Description", "type": "text", "required": true},
        {"id": "parts_used", "label": "Parts Used", "type": "multiselect", "required": false, "options": ["Filter", "Valve", "Pipe", "Wire", "Other"]},
        {"id": "labor_hours", "label": "Labor Hours", "type": "number", "required": true},
        {"id": "customer_rating", "label": "Customer Rating", "type": "rating", "required": false},
        {"id": "follow_up_required", "label": "Follow-up Required", "type": "toggle", "required": false},
        {"id": "technician_notes", "label": "Technician Notes", "type": "textarea", "required": false}
    ]
}', 1 FROM sync_job;

-- Create checklist responses for all completed jobs
-- Generate responses for all 30 completed jobs
INSERT INTO sync_checklistresponse (job_id, data, is_complete, last_modified_at, client_modified_at, completed_at)
SELECT 
    id,
    jsonb_build_object(
        'customer_signature', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
        'work_area_photo', 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/8A8A',
        'safety_check', true,
        'work_description', 'Service completed according to specifications',
        'parts_used', ARRAY['Filter', 'Valve'],
        'labor_hours', (random() * 6 + 1)::text,
        'customer_rating', (random() * 5 + 1)::integer,
        'follow_up_required', CASE WHEN random() < 0.3 THEN true ELSE false END,
        'technician_notes', 'Job completed successfully'
    ),
    true,
    NOW() - (random() * 24 || ' hours')::interval,
    NOW() - (random() * 24 || ' hours')::interval,
    NOW() - (random() * 24 || ' hours')::interval
FROM sync_job 
WHERE status = 'completed';

-- Full seed data creation complete
-- Total: 3 users, 90 jobs (30 pending, 30 in_progress, 30 completed)
-- Each user has 10 jobs per category (10 categories total)
-- Each job has a checklist schema, completed jobs have responses

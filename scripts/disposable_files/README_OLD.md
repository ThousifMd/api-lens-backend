# API Lens Backend Scripts

This directory contains all utility scripts organized by their purpose. These scripts were created to help with database management, testing, and data population.

## Directory Structure

```
scripts/
├── checks/          # Database validation and inspection scripts
├── tests/           # API testing and verification scripts
├── data_population/ # Scripts to populate database with test data
├── utilities/       # Maintenance and fix utilities
└── migrations/      # Database migration helpers
```

## 📊 Checks Directory

Scripts for validating database schema and data integrity:

- `check_all_tables.py` - Comprehensive database table inspection
- `check_client_users_schema.py` - Verify client_users table structure
- `check_critical_issues.py` - Identify critical database problems
- `check_existing_api_keys.py` - List available API keys
- `check_location_data.py` - Validate location data population
- `check_model_query.py` - Test model-related queries
- `check_null_values.py` - Find null/missing data in requests
- `check_partitions.py` - Check request table partitions
- `check_populated_data.py` - Summary of populated data
- `check_requests_schema.py` - Verify requests table structure
- `check_schema.py` - General schema validation
- `check_tables.py` - List all database tables
- `check_vendor_models_schema.py` - Verify vendor_models structure

## 🧪 Tests Directory

API endpoint and functionality testing:

- `test_image_generation.py` - Test image generation endpoints
- `test_location_simple.py` - Basic location detection tests
- `test_single_call.py` - Test a single API call
- `test_token_population.py` - Verify token calculation
- `test_varied_models.py` - Test different AI models
- `test_with_locations.py` - Location-aware API tests
- `complete_test_with_all_fields.py` - Comprehensive field testing

## 📝 Data Population Directory

Scripts to populate database with realistic test data:

- `populate_data.py` - Main data population script
- `populate_missing_tables.py` - Fill empty tables
- `populate_remaining_tables.py` - Complete data population
- `populate_requests.py` - Add request records
- `populate_requests_simple.py` - Simple request population
- `direct_populate.py` - Direct database population (bypasses API)
- `make_api_calls.py` - Simulate API calls via endpoints
- `simulate_api_calls.py` - Advanced API simulation with auth

## 🔧 Utilities Directory

Maintenance and data fixing utilities:

### Data Fixes
- `fix_null_data.py` - Fix null tokens and location data
- `refix_with_varied_tokens.py` - Re-populate with varied token values
- `clean_requests_table.py` - Remove all request records for fresh start

### Verification Tools
- `verify_clean_state.py` - Ensure database is clean
- `verify_schema_compliance.py` - Check schema v2 compliance
- `verify_schema_issues.py` - Identify schema problems
- `verify_system_ready.py` - Pre-flight system check

### Display Tools
- `show_api_keys.py` - Display available API keys
- `show_token_variety.py` - Analyze token distribution

## 🚀 Quick Start Guide

### 1. Check Database Health
```bash
python scripts/checks/check_all_tables.py
python scripts/checks/check_populated_data.py
```

### 2. Clean & Populate Data
```bash
# Clean existing data
python scripts/utilities/clean_requests_table.py

# Populate with test data
python scripts/data_population/direct_populate.py
```

### 3. Verify Data Quality
```bash
python scripts/utilities/show_token_variety.py
python scripts/utilities/verify_schema_compliance.py
```

### 4. Test API Endpoints
```bash
python scripts/tests/test_single_call.py
python scripts/tests/test_varied_models.py
```

## 📌 Important Notes

1. **Database Connection**: All scripts use the `DATABASE_URL` from `.env`
2. **Authentication**: API test scripts need valid API keys
3. **Data Safety**: Always backup before running clean/fix scripts
4. **Token Variety**: Scripts ensure realistic, varied token counts
5. **Location Data**: Automatic fallback to default locations if IP detection fails

## 🎯 Common Tasks

### Fix Missing Data
```bash
python scripts/utilities/fix_null_data.py
```

### Add More Test Data
```bash
python scripts/data_population/direct_populate.py
```

### Verify Everything is Working
```bash
python scripts/utilities/verify_system_ready.py
```

### Check Schema Compliance
```bash
python scripts/utilities/verify_schema_compliance.py
```

## 🔍 Troubleshooting

- **401 Errors**: Check API key validity with `show_api_keys.py`
- **Null Data**: Run `fix_null_data.py` to populate missing fields
- **Schema Issues**: Use `verify_schema_compliance.py` to identify problems
- **No Data**: Run `direct_populate.py` to add test records

## 📊 Data Characteristics

The scripts ensure:
- **Varied token counts** based on model type (no hardcoding)
- **Multiple locations** (US, UK, Japan, India, Australia)
- **Realistic latencies** per model type
- **Proper error rates** (~5% failure simulation)
- **Time distribution** over 24 hours
- **User diversity** (developers, support, writers, etc.)
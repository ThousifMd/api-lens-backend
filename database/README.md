# Database Schema and Migrations

This directory contains database schema files and migration scripts for the API Lens backend.

## Structure

```
database/
├── schema/                          # Schema definitions
│   ├── 01_core_system.sql          # Core system tables
│   ├── 02_company_schema.sql       # Company-specific schema function
│   └── 03_cost_calculation_schema.sql # Cost calculation tables
├── migrations/                      # Migration scripts
│   └── 001_cost_and_rate_limiting_migration.sql
├── init_db.py                      # Database initialization script
└── README.md                       # This file
```

## Required Tables for Cost Calculation & Rate Limiting

The following tables are required for the cost calculation and rate limiting system to function properly:

### Core Tables

1. **global_vendor_pricing** - System-wide vendor pricing data
2. **cost_calculations** - Individual cost calculation records
3. **cost_accuracy_validations** - Cost accuracy tracking
4. **cost_alerts** - Cost alert management
5. **cost_alerts_log** - Real-time cost alert logging
6. **billing_data** - Vendor billing data for validation
7. **company_quotas** - Company cost quotas
8. **rate_limit_configs** - Rate limiting configurations
9. **rate_limit_resets** - Rate limit reset audit trail

### Updated Tables

The migration also updates the existing `vendor_pricing` table to match the new schema requirements.

## Running Migrations

### Prerequisites

1. Ensure your database connection is configured in the environment
2. Make sure all dependencies are installed: `pip install -r requirements.txt`

### Apply Migration

To apply the cost calculation and rate limiting migration:

```bash
cd /path/to/api-lens-backend
python scripts/run_migration.py
```

Or explicitly:

```bash
python scripts/run_migration.py run
```

### Check Migration Status

```bash
python scripts/run_migration.py status
```

### Rollback Migration (if needed)

⚠️ **Warning**: This will remove all cost calculation and rate limiting data!

```bash
python scripts/run_migration.py rollback
```

### Manual Migration

If you prefer to run the migration manually:

```bash
# Connect to your PostgreSQL database
psql -h localhost -d your_database -U your_user

# Run the migration file
\i database/migrations/001_cost_and_rate_limiting_migration.sql
```

## Migration Details

### What the Migration Does

1. **Updates existing vendor_pricing table**:
   - Adds new columns for input/output pricing
   - Updates pricing model enum values
   - Maintains backward compatibility with existing data

2. **Creates new tables**:
   - Cost calculation and tracking tables
   - Rate limiting configuration tables
   - Alert and notification tables
   - Billing validation tables

3. **Inserts default data**:
   - Current vendor pricing for OpenAI, Anthropic, Google, Cohere
   - Default rate limit configurations for existing companies
   - Default quota settings for existing companies

4. **Creates indexes**:
   - Performance indexes for all new tables
   - Optimized for cost calculation and rate limiting queries

### Safety Features

- **Backup**: Creates backup of existing vendor_pricing data
- **Rollback**: Includes complete rollback SQL
- **Idempotent**: Safe to run multiple times
- **Validation**: Verifies table creation and data insertion

## Post-Migration Verification

After running the migration, verify the setup:

1. **Check tables exist**:
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_name IN (
     'cost_calculations', 'cost_alerts', 'global_vendor_pricing', 
     'rate_limit_configs', 'company_quotas'
   );
   ```

2. **Verify default data**:
   ```sql
   SELECT COUNT(*) FROM global_vendor_pricing;
   SELECT COUNT(*) FROM rate_limit_configs;
   SELECT COUNT(*) FROM company_quotas;
   ```

3. **Test cost calculation functions**:
   ```python
   from app.services.cost import load_vendor_pricing
   pricing = await load_vendor_pricing('openai', 'gpt-4')
   print(pricing)
   ```

## Troubleshooting

### Common Issues

1. **Migration already applied**: Check with `python scripts/run_migration.py status`
2. **Permission errors**: Ensure database user has CREATE TABLE permissions
3. **Connection errors**: Verify database configuration in environment variables

### Database Permissions

The migration requires the following PostgreSQL permissions:

```sql
GRANT CREATE ON DATABASE your_database TO your_user;
GRANT CREATE ON SCHEMA public TO your_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO your_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

### Environment Variables

Ensure these environment variables are set:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/database
# or individual components:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

## Schema Documentation

### Cost Calculations Flow

1. **Usage Parsing**: Vendor responses → `app/services/usage_parsers.py`
2. **Cost Calculation**: Usage data → `app/services/cost.py`
3. **Storage**: Results → `cost_calculations` table
4. **Analytics**: Aggregation → `billing_data` table

### Rate Limiting Flow

1. **Configuration**: `rate_limit_configs` table
2. **Real-time Tracking**: Redis counters + database logging
3. **Quota Enforcement**: `company_quotas` table
4. **Alerts**: `cost_alerts` and `cost_alerts_log` tables

## Performance Notes

- All tables include optimized indexes for common query patterns
- Cost calculations table is partitioned-ready for high-volume scenarios
- Rate limiting uses Redis for real-time counters with database backup
- Analytics queries are optimized with compound indexes

## Support

If you encounter issues with the migration:

1. Check the migration logs for specific error messages
2. Verify database permissions and connectivity
3. Ensure all required environment variables are set
4. Check that no other processes are using the database during migration
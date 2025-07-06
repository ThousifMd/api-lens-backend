# Essential Scripts Only - API Lens Backend

This directory contains only the essential scripts needed for operating and maintaining the API Lens backend. All debugging and one-time scripts have been moved to `disposable_files/`.

## 📁 Streamlined Structure

```
scripts/
├── data_population/    # 1 essential script
├── tests/             # 2 useful test scripts  
├── utilities/         # 6 core utilities
├── migrations/        # 2 database scripts
└── disposable_files/  # 30 archived scripts
```

## ✅ Essential Scripts (11 total)

### 📝 Data Population (1 script)
- **`direct_populate.py`** - Main tool to populate database with realistic test data
  ```bash
  python scripts/data_population/direct_populate.py
  ```

### 🧪 Tests (2 scripts)
- **`test_image_generation.py`** - Test image generation models
- **`test_varied_models.py`** - Test multiple AI models with variety

### 🔧 Utilities (6 scripts)
- **`clean_requests_table.py`** - Clear all request data for fresh start
  ```bash
  python scripts/utilities/clean_requests_table.py
  ```

- **`fix_null_data.py`** - Fix any null/missing data in requests
  ```bash
  python scripts/utilities/fix_null_data.py
  ```

- **`show_api_keys.py`** - Display available API keys
- **`show_token_variety.py`** - Analyze token distribution and variety
- **`verify_schema_compliance.py`** - Ensure database matches schema v2
- **`verify_system_ready.py`** - Pre-flight check before using system

### 🗄️ Migrations (2 scripts)
- **`init_db.py`** - Initialize database structure
- **`migrate_db.py`** - Run database migrations

## 🚀 Common Workflows

### 1. Fresh Start
```bash
# Clean existing data
python scripts/utilities/clean_requests_table.py

# Populate with test data
python scripts/data_population/direct_populate.py

# Verify everything
python scripts/utilities/verify_system_ready.py
```

### 2. Fix Data Issues
```bash
# Fix null values
python scripts/utilities/fix_null_data.py

# Check token variety
python scripts/utilities/show_token_variety.py
```

### 3. System Health Check
```bash
# Full system check
python scripts/utilities/verify_system_ready.py

# Schema compliance
python scripts/utilities/verify_schema_compliance.py
```

## 🗑️ Disposable Files

30 scripts were moved to `disposable_files/` including:
- One-time debugging scripts
- Duplicate functionality scripts
- Old versions of current tools
- Development test scripts
- Failed API simulation attempts

These scripts served their purpose during development but are not needed for normal operation. They're preserved in case you need to reference them later.

## 📌 Key Points

1. **Only 11 scripts** are truly essential for operating the system
2. **direct_populate.py** is the main tool for adding test data
3. **verify_system_ready.py** should be run before starting
4. All scripts connect using DATABASE_URL from .env
5. Token variety and location diversity are automatically handled

## 🎯 Quick Reference

| Task | Script |
|------|---------|
| Add test data | `direct_populate.py` |
| Clean all data | `clean_requests_table.py` |
| Fix missing data | `fix_null_data.py` |
| Check system | `verify_system_ready.py` |
| View analytics | `show_token_variety.py` |
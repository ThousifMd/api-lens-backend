#!/usr/bin/env python3
"""
Apply migration 008 - Add image generation support
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg
from pathlib import Path

# Load environment variables
load_dotenv()

async def apply_migration_008():
    # Get database URL from environment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    migration_file = Path(__file__).parent / "migrations" / "008_add_image_generation_support.sql"
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        return
    
    print(f"📂 Found migration file: {migration_file}")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("\n🚀 Applying migration 008_add_image_generation_support...")
        print("=" * 80)
        
        # Read the migration file
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Split into statements (simple approach - split by semicolon)
        # Remove comments and empty lines
        statements = []
        current_statement = []
        
        for line in migration_sql.split('\n'):
            # Skip comment-only lines
            if line.strip().startswith('--') or not line.strip():
                continue
            
            current_statement.append(line)
            
            # Check if line ends with semicolon (end of statement)
            if line.strip().endswith(';'):
                stmt = '\n'.join(current_statement)
                if stmt.strip():
                    statements.append(stmt)
                current_statement = []
        
        # Add any remaining statement
        if current_statement:
            stmt = '\n'.join(current_statement)
            if stmt.strip():
                statements.append(stmt)
        
        print(f"📊 Found {len(statements)} SQL statements to execute")
        
        # Execute each statement in a transaction
        async with conn.transaction():
            for i, statement in enumerate(statements, 1):
                try:
                    # Show what we're executing (first 100 chars)
                    stmt_preview = statement.strip()[:100].replace('\n', ' ')
                    if len(statement.strip()) > 100:
                        stmt_preview += "..."
                    
                    print(f"\n🔧 Executing statement {i}/{len(statements)}: {stmt_preview}")
                    
                    await conn.execute(statement)
                    print(f"   ✅ Success")
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    raise
        
        print("\n✅ Migration 008 applied successfully!")
        
        # Verify the changes
        print("\n🔍 Verifying migration results...")
        print("-" * 80)
        
        # Check columns
        columns_query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'requests'
        AND column_name IN (
            'image_count', 'image_urls', 'image_dimensions', 
            'image_quality', 'image_style', 'prompt', 
            'negative_prompt', 'seed', 'generation_steps', 'guidance_scale'
        )
        ORDER BY column_name;
        """
        
        columns = await conn.fetch(columns_query)
        
        print(f"\n✅ Image generation columns added ({len(columns)}/10):")
        for col in columns:
            print(f"  - {col['column_name']:<25} {col['data_type']}")
        
        # Check vendors
        vendors_query = """
        SELECT name, display_name, is_active
        FROM vendors
        WHERE name IN ('stability-ai', 'midjourney', 'adobe')
        ORDER BY name;
        """
        
        vendors = await conn.fetch(vendors_query)
        
        print(f"\n✅ Image generation vendors added ({len(vendors)}):")
        for vendor in vendors:
            status = "active" if vendor['is_active'] else "inactive"
            print(f"  - {vendor['name']:<15} {vendor['display_name']:<15} ({status})")
        
        # Check models
        models_query = """
        SELECT v.name as vendor_name, vm.name as model_name, vm.model_type
        FROM vendor_models vm
        JOIN vendors v ON vm.vendor_id = v.id
        WHERE vm.model_type = 'image_generation'
        ORDER BY v.name, vm.name;
        """
        
        models = await conn.fetch(models_query)
        
        print(f"\n✅ Image generation models added ({len(models)}):")
        for model in models:
            print(f"  - {model['vendor_name']:<15} {model['model_name']}")
        
        await conn.close()
        
        print("\n" + "=" * 80)
        print("🎉 Migration completed successfully!")
        print("   The requests table now supports image generation tracking.")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(apply_migration_008())
#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')
from app.database import DatabaseUtils

async def analyze_timestamp_columns():
    """Analyze existing timestamp columns to plan location-based timezone additions"""
    
    query = '''
    SELECT 
        table_name,
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns 
    WHERE data_type IN ('timestamp with time zone', 'timestamp without time zone')
    AND table_schema = 'public'
    ORDER BY table_name, column_name
    '''
    
    results = await DatabaseUtils.execute_query(query, [], fetch_all=True)
    
    print('📅 CURRENT TIMESTAMP COLUMNS ANALYSIS')
    print('=' * 60)
    
    current_table = None
    tables_with_timestamps = {}
    
    for row in results:
        table_name = row['table_name']
        if table_name not in tables_with_timestamps:
            tables_with_timestamps[table_name] = []
        
        tables_with_timestamps[table_name].append({
            'column': row['column_name'],
            'type': row['data_type'],
            'nullable': row['is_nullable'] == 'YES',
            'default': row['column_default']
        })
    
    # Display organized results
    for table_name, columns in tables_with_timestamps.items():
        print(f'\n🗂️  TABLE: {table_name}')
        for col in columns:
            nullable = 'NULL' if col['nullable'] else 'NOT NULL'
            default = f"DEFAULT {col['default']}" if col['default'] else "NO DEFAULT"
            print(f'   📍 {col["column"]} ({col["type"]}) {nullable} {default}')
    
    print(f'\n📊 SUMMARY:')
    print(f'   Tables with timestamps: {len(tables_with_timestamps)}')
    print(f'   Total timestamp columns: {sum(len(cols) for cols in tables_with_timestamps.values())}')
    
    return tables_with_timestamps

if __name__ == "__main__":
    asyncio.run(analyze_timestamp_columns())
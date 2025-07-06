"""
Optimized Bulk Database Operations using PostgreSQL COPY
Provides high-performance bulk insert and update operations
"""
import csv
import io
from typing import List, Dict, Any, Optional, Union, TypeVar, Generic
from datetime import datetime
import asyncpg
import json
import logging
from dataclasses import dataclass, fields
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class BulkOperationResult:
    """Result of a bulk operation"""
    success: bool
    rows_affected: int
    execution_time_ms: float
    error: Optional[str] = None
    
class BulkOperationManager:
    """Manager for optimized bulk database operations using COPY"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.batch_size = 10000  # Default batch size for COPY operations
        
    async def bulk_copy_from(self,
                           table_name: str,
                           records: List[Dict[str, Any]],
                           columns: Optional[List[str]] = None,
                           on_conflict: Optional[str] = None,
                           batch_size: Optional[int] = None) -> BulkOperationResult:
        """
        Perform bulk insert using PostgreSQL COPY command
        
        Args:
            table_name: Target table name
            records: List of dictionaries containing data
            columns: List of column names (inferred from first record if not provided)
            on_conflict: Conflict resolution strategy ('update' or 'ignore')
            batch_size: Number of records per batch
            
        Returns:
            BulkOperationResult with operation details
        """
        if not records:
            return BulkOperationResult(success=True, rows_affected=0, execution_time_ms=0)
        
        start_time = asyncio.get_event_loop().time()
        batch_size = batch_size or self.batch_size
        
        try:
            # Determine columns from first record if not provided
            if not columns:
                columns = list(records[0].keys())
            
            # Process in batches
            total_rows = 0
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                if on_conflict:
                    # Use temporary table for conflict resolution
                    rows = await self._copy_with_conflict_resolution(
                        table_name, batch, columns, on_conflict
                    )
                else:
                    # Direct COPY for best performance
                    rows = await self._direct_copy(table_name, batch, columns)
                
                total_rows += rows
            
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return BulkOperationResult(
                success=True,
                rows_affected=total_rows,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Bulk copy failed: {e}")
            return BulkOperationResult(
                success=False,
                rows_affected=0,
                execution_time_ms=execution_time,
                error=str(e)
            )
    
    async def _direct_copy(self,
                          table_name: str,
                          records: List[Dict[str, Any]],
                          columns: List[str]) -> int:
        """Direct COPY operation without conflict handling"""
        
        # Convert records to CSV format in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        
        for record in records:
            # Handle special types
            processed_record = self._process_record_for_copy(record, columns)
            writer.writerow(processed_record)
        
        # Reset to beginning
        output.seek(0)
        
        async with self.pool.acquire() as conn:
            # Use COPY FROM stdin
            result = await conn.copy_from_table(
                table_name,
                source=output,
                columns=columns,
                format='csv'
            )
            
            # Extract row count from result
            rows_affected = int(result.split()[-1])
            return rows_affected
    
    async def _copy_with_conflict_resolution(self,
                                           table_name: str,
                                           records: List[Dict[str, Any]],
                                           columns: List[str],
                                           conflict_action: str) -> int:
        """COPY with conflict resolution using temporary table"""
        
        temp_table = f"temp_{table_name}_{id(records)}"
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Create temporary table
                    await conn.execute(f"""
                        CREATE TEMP TABLE {temp_table} 
                        (LIKE {table_name} INCLUDING ALL)
                        ON COMMIT DROP
                    """)
                    
                    # Copy data to temp table
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
                    
                    for record in records:
                        processed_record = self._process_record_for_copy(record, columns)
                        writer.writerow(processed_record)
                    
                    output.seek(0)
                    
                    await conn.copy_from_table(
                        temp_table,
                        source=output,
                        columns=columns,
                        format='csv'
                    )
                    
                    # Merge from temp table with conflict resolution
                    if conflict_action == 'update':
                        # Assume first column is the primary key
                        pk_column = columns[0]
                        update_columns = [col for col in columns if col != pk_column]
                        update_clause = ', '.join([
                            f"{col} = EXCLUDED.{col}" for col in update_columns
                        ])
                        
                        result = await conn.execute(f"""
                            INSERT INTO {table_name} ({', '.join(columns)})
                            SELECT {', '.join(columns)} FROM {temp_table}
                            ON CONFLICT ({pk_column}) DO UPDATE SET {update_clause}
                        """)
                    else:  # ignore
                        result = await conn.execute(f"""
                            INSERT INTO {table_name} ({', '.join(columns)})
                            SELECT {', '.join(columns)} FROM {temp_table}
                            ON CONFLICT DO NOTHING
                        """)
                    
                    # Extract affected rows
                    rows_affected = int(result.split()[-1])
                    return rows_affected
                    
                except Exception as e:
                    logger.error(f"Error in conflict resolution: {e}")
                    raise
    
    def _process_record_for_copy(self, record: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
        """Process record values for COPY compatibility"""
        processed = {}
        
        for col in columns:
            value = record.get(col)
            
            # Handle None/NULL
            if value is None:
                processed[col] = '\\N'
            # Handle JSON types
            elif isinstance(value, (dict, list)):
                processed[col] = json.dumps(value)
            # Handle datetime
            elif isinstance(value, datetime):
                processed[col] = value.isoformat()
            # Handle boolean
            elif isinstance(value, bool):
                processed[col] = 't' if value else 'f'
            else:
                processed[col] = str(value)
        
        return processed
    
    async def bulk_update_by_id(self,
                              table_name: str,
                              updates: List[Dict[str, Any]],
                              id_column: str = 'id') -> BulkOperationResult:
        """
        Perform bulk updates using temporary table and JOIN
        
        Args:
            table_name: Target table name
            updates: List of dicts with id and fields to update
            id_column: Name of the ID column
            
        Returns:
            BulkOperationResult
        """
        if not updates:
            return BulkOperationResult(success=True, rows_affected=0, execution_time_ms=0)
        
        start_time = asyncio.get_event_loop().time()
        temp_table = f"temp_updates_{id(updates)}"
        
        try:
            # Get columns to update (exclude id column)
            columns = list(updates[0].keys())
            update_columns = [col for col in columns if col != id_column]
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Create temp table with update data
                    column_defs = [f"{id_column} BIGINT"]
                    for col in update_columns:
                        # Infer type from first non-null value
                        sample_value = next((u[col] for u in updates if u.get(col) is not None), None)
                        col_type = self._infer_column_type(sample_value)
                        column_defs.append(f"{col} {col_type}")
                    
                    await conn.execute(f"""
                        CREATE TEMP TABLE {temp_table} (
                            {', '.join(column_defs)}
                        ) ON COMMIT DROP
                    """)
                    
                    # Copy update data to temp table
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
                    
                    for update in updates:
                        processed = self._process_record_for_copy(update, columns)
                        writer.writerow(processed)
                    
                    output.seek(0)
                    
                    await conn.copy_from_table(
                        temp_table,
                        source=output,
                        columns=columns,
                        format='csv'
                    )
                    
                    # Perform bulk update via JOIN
                    set_clause = ', '.join([
                        f"{col} = t.{col}" for col in update_columns
                    ])
                    
                    result = await conn.execute(f"""
                        UPDATE {table_name} AS target
                        SET {set_clause}
                        FROM {temp_table} AS t
                        WHERE target.{id_column} = t.{id_column}
                    """)
                    
                    rows_affected = int(result.split()[-1])
                    
                    execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    return BulkOperationResult(
                        success=True,
                        rows_affected=rows_affected,
                        execution_time_ms=execution_time
                    )
                    
        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Bulk update failed: {e}")
            return BulkOperationResult(
                success=False,
                rows_affected=0,
                execution_time_ms=execution_time,
                error=str(e)
            )
    
    def _infer_column_type(self, value: Any) -> str:
        """Infer PostgreSQL column type from Python value"""
        if value is None:
            return "TEXT"
        elif isinstance(value, bool):
            return "BOOLEAN"
        elif isinstance(value, int):
            return "BIGINT"
        elif isinstance(value, float):
            return "DOUBLE PRECISION"
        elif isinstance(value, datetime):
            return "TIMESTAMP WITH TIME ZONE"
        elif isinstance(value, (dict, list)):
            return "JSONB"
        else:
            return "TEXT"
    
    async def bulk_upsert(self,
                         table_name: str,
                         records: List[Dict[str, Any]],
                         unique_columns: List[str],
                         update_columns: Optional[List[str]] = None) -> BulkOperationResult:
        """
        Perform bulk upsert (INSERT ... ON CONFLICT UPDATE)
        
        Args:
            table_name: Target table name
            records: List of records to upsert
            unique_columns: Columns that define uniqueness constraint
            update_columns: Columns to update on conflict (all non-unique columns if not specified)
            
        Returns:
            BulkOperationResult
        """
        if not records:
            return BulkOperationResult(success=True, rows_affected=0, execution_time_ms=0)
        
        # Determine all columns and update columns
        all_columns = list(records[0].keys())
        if not update_columns:
            update_columns = [col for col in all_columns if col not in unique_columns]
        
        # Use copy with conflict resolution
        return await self.bulk_copy_from(
            table_name=table_name,
            records=records,
            columns=all_columns,
            on_conflict='update'
        )

# Example usage
async def example_usage(pool: asyncpg.Pool):
    """Example of using bulk operations"""
    
    bulk_manager = BulkOperationManager(pool)
    
    # Example 1: Bulk insert with COPY
    records = [
        {'company_id': 1, 'user_id': f'user_{i}', 'created_at': datetime.utcnow()}
        for i in range(100000)
    ]
    
    result = await bulk_manager.bulk_copy_from(
        table_name='client_users',
        records=records,
        on_conflict='ignore'
    )
    
    print(f"Inserted {result.rows_affected} records in {result.execution_time_ms:.2f}ms")
    
    # Example 2: Bulk update
    updates = [
        {'id': i, 'last_seen': datetime.utcnow(), 'status': 'active'}
        for i in range(1, 1001)
    ]
    
    result = await bulk_manager.bulk_update_by_id(
        table_name='client_users',
        updates=updates
    )
    
    print(f"Updated {result.rows_affected} records in {result.execution_time_ms:.2f}ms")
    
    # Example 3: Bulk upsert
    upsert_records = [
        {
            'company_id': 1,
            'vendor_id': i,
            'api_key': f'key_{i}',
            'created_at': datetime.utcnow()
        }
        for i in range(1, 101)
    ]
    
    result = await bulk_manager.bulk_upsert(
        table_name='vendor_keys',
        records=upsert_records,
        unique_columns=['company_id', 'vendor_id']
    )
    
    print(f"Upserted {result.rows_affected} records in {result.execution_time_ms:.2f}ms")
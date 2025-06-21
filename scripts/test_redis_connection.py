#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cache import redis_client, get_cache_stats

async def test_redis_connection():
    """Test Redis connection and basic operations"""
    try:
        print("🔄 Testing Redis connection...")
        
        # Test basic ping
        pong = await redis_client.ping()
        print(f"✅ Redis ping successful: {pong}")
        
        # Test set/get operations
        test_key = "test:connection"
        test_value = "Hello from API Lens!"
        
        await redis_client.set(test_key, test_value)
        retrieved_value = await redis_client.get(test_key)
        
        if retrieved_value == test_value:
            print("✅ Redis set/get operations working correctly")
        else:
            print("❌ Redis set/get operations failed")
            return False
            
        # Test cache stats
        try:
            stats = await get_cache_stats()
            print(f"✅ Redis stats: {stats}")
        except Exception as e:
            print(f"⚠️  Redis stats partially available: {e}")
            # Get basic info instead
            dbsize = await redis_client.dbsize()
            print(f"✅ Redis database size: {dbsize} keys")
        
        # Clean up test key
        await redis_client.delete(test_key)
        print("✅ Test cleanup completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    success = asyncio.run(test_redis_connection())
    if success:
        print("\n🎉 Redis connection test passed!")
        sys.exit(0)
    else:
        print("\n💥 Redis connection test failed!")
        sys.exit(1)
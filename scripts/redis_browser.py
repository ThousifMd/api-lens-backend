#!/usr/bin/env python3
"""
Redis Database Browser - View and interact with Redis data
"""
import asyncio
import sys
import os
import json
from typing import List, Dict, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cache import redis_client, close_redis_connection

class RedisBrowser:
    def __init__(self):
        self.client = redis_client
        
    async def list_all_keys(self, pattern: str = "*") -> List[str]:
        """List all keys matching pattern"""
        try:
            keys = await self.client.keys(pattern)
            return sorted(keys) if keys else []
        except Exception as e:
            print(f"❌ Error listing keys: {e}")
            return []
    
    async def get_key_info(self, key: str) -> Dict[str, Any]:
        """Get detailed information about a key"""
        try:
            # Get key type
            key_type = await self.client.type(key)
            
            # Get TTL
            ttl = await self.client.ttl(key)
            
            # Get value based on type
            if key_type == "string":
                value = await self.client.get(key)
                # Try to parse as JSON
                try:
                    parsed_value = json.loads(value)
                    value = parsed_value
                except (json.JSONDecodeError, TypeError):
                    pass
            elif key_type == "hash":
                value = await self.client.hgetall(key)
            elif key_type == "list":
                value = await self.client.lrange(key, 0, -1)
            elif key_type == "set":
                value = await self.client.smembers(key)
            elif key_type == "zset":
                value = await self.client.zrange(key, 0, -1, withscores=True)
            else:
                value = f"Unsupported type: {key_type}"
                
            return {
                "key": key,
                "type": key_type,
                "ttl": ttl,
                "value": value
            }
        except Exception as e:
            return {
                "key": key,
                "error": str(e)
            }
    
    async def search_keys_by_pattern(self, pattern: str) -> None:
        """Search and display keys by pattern"""
        print(f"🔍 Searching for keys matching: {pattern}")
        keys = await self.list_all_keys(pattern)
        
        if not keys:
            print("No keys found matching the pattern.")
            return
            
        print(f"Found {len(keys)} keys:")
        for i, key in enumerate(keys, 1):
            print(f"{i:3d}. {key}")
    
    async def inspect_key(self, key: str) -> None:
        """Inspect a specific key"""
        print(f"🔍 Inspecting key: {key}")
        info = await self.get_key_info(key)
        
        if "error" in info:
            print(f"❌ Error: {info['error']}")
            return
            
        print(f"📋 Key Information:")
        print(f"   Type: {info['type']}")
        print(f"   TTL:  {info['ttl']} seconds" + (" (no expiry)" if info['ttl'] == -1 else ""))
        print(f"   Value:")
        
        # Format value for display
        value = info['value']
        if isinstance(value, dict):
            print(json.dumps(value, indent=4))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                print(f"     [{i}] {item}")
        else:
            print(f"     {value}")
    
    async def browse_by_namespace(self) -> None:
        """Browse keys organized by namespace"""
        print("🗂️  Browsing by namespace...")
        
        # Get all keys
        all_keys = await self.list_all_keys()
        
        if not all_keys:
            print("No keys found in database.")
            return
            
        # Group by namespace (first part before :)
        namespaces = {}
        for key in all_keys:
            if ":" in key:
                namespace = key.split(":", 1)[0]
                if namespace not in namespaces:
                    namespaces[namespace] = []
                namespaces[namespace].append(key)
            else:
                if "no_namespace" not in namespaces:
                    namespaces["no_namespace"] = []
                namespaces["no_namespace"].append(key)
        
        for namespace, keys in namespaces.items():
            print(f"\\n📁 {namespace} ({len(keys)} keys):")
            for key in sorted(keys):
                print(f"   • {key}")
    
    async def get_database_stats(self) -> None:
        """Get database statistics"""
        print("📊 Database Statistics:")
        
        try:
            # Get basic stats
            dbsize = await self.client.dbsize()
            print(f"   Total Keys: {dbsize}")
            
            # Get info
            info = await self.client.info()
            if "used_memory" in info:
                memory_mb = info["used_memory"] / (1024 * 1024)
                print(f"   Memory Used: {memory_mb:.2f} MB")
            
            if "connected_clients" in info:
                print(f"   Connected Clients: {info['connected_clients']}")
                
            # Get key types distribution
            all_keys = await self.list_all_keys()
            if all_keys:
                type_counts = {}
                for key in all_keys[:100]:  # Sample first 100 keys
                    key_type = await self.client.type(key)
                    type_counts[key_type] = type_counts.get(key_type, 0) + 1
                
                print("   Key Types:")
                for key_type, count in type_counts.items():
                    print(f"     {key_type}: {count}")
                    
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
    
    async def interactive_mode(self) -> None:
        """Interactive Redis browser"""
        print("🚀 Redis Interactive Browser")
        print("=" * 50)
        
        while True:
            print("\\nOptions:")
            print("1. List all keys")
            print("2. Search keys by pattern")
            print("3. Inspect specific key")
            print("4. Browse by namespace")
            print("5. Database statistics")
            print("6. Exit")
            
            try:
                choice = input("\\nEnter your choice (1-6): ").strip()
                
                if choice == "1":
                    print("\\n" + "="*50)
                    keys = await self.list_all_keys()
                    if keys:
                        print(f"All keys ({len(keys)}):")
                        for i, key in enumerate(keys, 1):
                            print(f"{i:3d}. {key}")
                    else:
                        print("No keys found.")
                        
                elif choice == "2":
                    pattern = input("Enter search pattern (e.g., dev:*, *api_key*): ").strip()
                    if pattern:
                        print("\\n" + "="*50)
                        await self.search_keys_by_pattern(pattern)
                        
                elif choice == "3":
                    key = input("Enter key name: ").strip()
                    if key:
                        print("\\n" + "="*50)
                        await self.inspect_key(key)
                        
                elif choice == "4":
                    print("\\n" + "="*50)
                    await self.browse_by_namespace()
                    
                elif choice == "5":
                    print("\\n" + "="*50)
                    await self.get_database_stats()
                    
                elif choice == "6":
                    print("👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice. Please enter 1-6.")
                    
            except KeyboardInterrupt:
                print("\\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

async def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        browser = RedisBrowser()
        
        try:
            if command == "keys":
                pattern = sys.argv[2] if len(sys.argv) > 2 else "*"
                await browser.search_keys_by_pattern(pattern)
            elif command == "get":
                if len(sys.argv) < 3:
                    print("Usage: python redis_browser.py get <key_name>")
                    sys.exit(1)
                key = sys.argv[2]
                await browser.inspect_key(key)
            elif command == "stats":
                await browser.get_database_stats()
            elif command == "browse":
                await browser.browse_by_namespace()
            else:
                print("Available commands:")
                print("  keys [pattern]  - List keys (optional pattern)")
                print("  get <key>       - Get key value")
                print("  stats           - Database statistics")
                print("  browse          - Browse by namespace")
                print("  (no args)       - Interactive mode")
        finally:
            await close_redis_connection()
    else:
        # Interactive mode
        browser = RedisBrowser()
        try:
            await browser.interactive_mode()
        finally:
            await close_redis_connection()

if __name__ == "__main__":
    asyncio.run(main())
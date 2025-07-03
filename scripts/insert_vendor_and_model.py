import asyncio
from app.database import DatabaseUtils

async def main():
    print("Inserting 'openai' vendor if not present...")
    await DatabaseUtils.execute_query('''
        INSERT INTO vendors (name, slug, description, is_active)
        VALUES ('openai', 'openai', 'OpenAI LLM vendor', true)
        ON CONFLICT (name) DO NOTHING;
    ''', fetch_all=False)
    print("Inserting 'gpt-4' model for 'openai' if not present...")
    await DatabaseUtils.execute_query('''
        INSERT INTO vendor_models (vendor_id, name, slug, model_type, is_active)
        VALUES ((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4', 'gpt-4', 'chat', true)
        ON CONFLICT (vendor_id, name) DO NOTHING;
    ''', fetch_all=False)
    print("✅ Done. 'openai' vendor and 'gpt-4' model are present.")

if __name__ == "__main__":
    asyncio.run(main()) 
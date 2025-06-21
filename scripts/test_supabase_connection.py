from app.utils.supabase_client import get_supabase_client

def main():
    supabase = get_supabase_client()
    # TODO: Replace 'test_table' with an actual table name from your Supabase DB
    try:
        response = supabase.table('test_table').select('*').limit(10).execute()
        print('Connection successful!')
        print('Full response:', response)
        print('Sample data:', response.data)
    except Exception as e:
        print('Connection failed:', e)

if __name__ == "__main__":
    main() 
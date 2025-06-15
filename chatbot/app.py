import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import openai
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Schema for the request_logs table
SCHEMA = """
CREATE TABLE request_logs (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    vendor VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost FLOAT,
    latency FLOAT,
    status_code INTEGER,
    request_id VARCHAR NOT NULL,
    prompt_hash VARCHAR NOT NULL
);
"""

def generate_sql_query(question: str) -> str:
    """Generate SQL query from natural language question."""
    prompt = f"""Convert this question to a SQL query for the following schema:
{SCHEMA}

Question: {question}

Return only the SQL query without any explanation."""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a SQL expert. Convert natural language questions to SQL queries."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    return response.choices[0].message.content.strip()

def execute_query(query: str) -> pd.DataFrame:
    """Execute SQL query and return results as DataFrame."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")
        return pd.DataFrame()

def main():
    st.title("LLM Proxy Analytics Dashboard")
    
    # Sidebar
    st.sidebar.title("Query Options")
    query_type = st.sidebar.radio(
        "Choose query type",
        ["Natural Language", "Custom SQL"]
    )

    if query_type == "Natural Language":
        st.subheader("Ask a question about the LLM usage data")
        question = st.text_input("Enter your question", 
            placeholder="e.g., What was the total cost per vendor last week?")
        
        if question:
            try:
                sql_query = generate_sql_query(question)
                st.code(sql_query, language="sql")
                
                if st.button("Execute Query"):
                    df = execute_query(sql_query)
                    if not df.empty:
                        st.dataframe(df)
                        
                        # Add visualization if appropriate
                        if len(df.columns) == 2 and df.dtypes[1] in ['float64', 'int64']:
                            st.bar_chart(df.set_index(df.columns[0]))
            except Exception as e:
                st.error(f"Error generating SQL: {str(e)}")
    
    else:  # Custom SQL
        st.subheader("Write your own SQL query")
        sql_query = st.text_area("Enter SQL query", height=150)
        
        if st.button("Execute Custom Query"):
            df = execute_query(sql_query)
            if not df.empty:
                st.dataframe(df)

    # Quick Stats
    st.subheader("Quick Stats")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_requests = execute_query("SELECT COUNT(*) FROM request_logs")[0][0]
        st.metric("Total Requests", total_requests)
    
    with col2:
        total_cost = execute_query("SELECT SUM(cost) FROM request_logs")[0][0]
        st.metric("Total Cost", f"${total_cost:.2f}")
    
    with col3:
        avg_latency = execute_query("SELECT AVG(latency) FROM request_logs")[0][0]
        st.metric("Avg Latency", f"{avg_latency:.2f}s")

    # Recent Activity
    st.subheader("Recent Activity")
    recent_activity = execute_query("""
        SELECT timestamp, vendor, model, cost, latency 
        FROM request_logs 
        ORDER BY timestamp DESC 
        LIMIT 10
    """)
    st.dataframe(recent_activity)

if __name__ == "__main__":
    main()

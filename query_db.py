#!/usr/bin/env python
"""Quick database query utility"""
import sqlite3
import sys

def query_db(query):
    try:
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Get column names
        columns = [description[0] for description in cursor.description]
        
        # Print results
        print("\t".join(columns))
        print("-" * 60)
        for row in rows:
            print("\t".join(str(val) for val in row))
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "SELECT run_id, status, conclusion FROM pipeline_runs;"
    query_db(query)

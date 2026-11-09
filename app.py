import os
import math
from fastapi import FastAPI, HTTPException, Query
import duckdb

app = FastAPI(title="Simple Search API")

# ---------------- YOUR SINGLE KEY ----------------
MASTER_KEY = "my_secret_key_123"  # Change this to your desired secret key

# Target the 7 files in the bucket
BUCKET_PATH = "hf://buckets/secrethure/aadhar-family-bucket/idx_aadhar.*.parquet"

# ---------------- HELPERS ----------------
def clean_records(df):
    """Cleans pandas NaN and numpy types for JSON serialization."""
    records = df.to_dict(orient="records")
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                clean[k] = None
            elif hasattr(v, "item"):  # numpy scalar -> python native
                clean[k] = v.item()
            else:
                clean[k] = v
        out.append(clean)
    return out

# ---------------- PUBLIC SEARCH ----------------
@app.get("/search")
async def dynamic_search(
    field: str = Query(..., description="Column to search (e.g., aadharNumber, phoneNumber)"),
    value: str = Query(..., description="The value to search for"),
    key: str = Query(..., description="Your API key"),
):
    # 1. Simple Key Check
    if key != MASTER_KEY:
        raise HTTPException(status_code=401, detail="ACCESS_DENIED: Invalid API key")

    # 2. Security: Validate field name to prevent SQL injection
    allowed_fields = [
        "name", "fathersName", "phoneNumber", "aadharNumber", 
        "otherNumber", "address", "district", "pincode", 
        "state", "town", "source"
    ]
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid field name.")

    # 3. Initialize a fresh connection for this specific request
    con = None
    try:
        con = duckdb.connect()
        con.execute("SET home_directory = '/tmp';")
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        
        # Quick ping to ensure the connection is alive
        con.execute("SELECT 1")
        
        query = f"SELECT * FROM read_parquet('{BUCKET_PATH}') WHERE {field} = ? LIMIT 10"
        df = con.execute(query, [value]).fetchdf()
        
        if df.empty:
            return {"message": "NO_DATA_FOUND", "field": field, "value": value}
        return clean_records(df)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QUERY_FAILED: {str(e)}")
        
    finally:
        # 4. CRITICAL: Always close the connection to free up Vercel's memory
        if con is not None:
            con.close()
            print("DuckDB connection closed successfully.")

@app.get("/")
async def root():
    return {"status": "ONLINE", "message": "Use /search?field=...&value=...&key=..."}

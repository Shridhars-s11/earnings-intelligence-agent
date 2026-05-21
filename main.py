import uvicorn
from app.db import test_connection, init_db

if __name__ == "__main__":
    test_connection()
    init_db()
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
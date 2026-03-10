import asyncio
import os
import sys
import glob

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.config import settings
from libs.storage._timescale_client import TimescaleClient

async def apply_migrations():
    print("Starting Database Migrations...")
    client = TimescaleClient(settings.DATABASE_URL)
    await client.init_pool()
    migration_files = sorted(glob.glob("migrations/versions/*.sql"))
    for file in migration_files:
        print(f"Applying {file}...")
        with open(file, "r") as f:
            sql = f.read()
            try:
                await client.execute(sql)
            except Exception as e:
                print(f"Failed to execute {file}: {str(e)}")
                    
    await client.close()
    print("Migrations complete.")

if __name__ == "__main__":
    asyncio.run(apply_migrations())

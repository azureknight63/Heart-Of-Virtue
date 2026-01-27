import os
import libsql_client
from dotenv import load_dotenv

load_dotenv()

class Database:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def get_client(self):
        if self._client is None:
            url = os.getenv("TURSO_DATABASE_URL")
            auth_token = os.getenv("TURSO_AUTH_TOKEN")
            if not url:
                raise ValueError("TURSO_DATABASE_URL is not set")
            self._client = libsql_client.create_client(url, auth_token=auth_token)
        return self._client

    async def execute(self, sql, params=None):
        client = self.get_client()
        return await client.execute(sql, params)

    async def batch(self, statements):
        client = self.get_client()
        return await client.batch(statements)

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

db = Database()

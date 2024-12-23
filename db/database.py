import os
import asyncpg
from typing import Optional, List, Tuple

class Database:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                user=os.getenv('PGUSER'),
                password=os.getenv('PGPASSWORD'),
                database=os.getenv('PGDATABASE'),
                host=os.getenv('PGHOST'),
                port=os.getenv('PGPORT')
            )
        return cls._pool

async def init_db():
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance DECIMAL DEFAULT 100.0,
                username TEXT NOT NULL
            )
        ''')

async def create_user(user_id: int, username: str) -> bool:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                'INSERT INTO users (user_id, username) VALUES ($1, $2)',
                user_id, username
            )
            return True
        except asyncpg.UniqueViolationError:
            return False

async def get_balance(user_id: int) -> Optional[float]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            'SELECT balance FROM users WHERE user_id = $1',
            user_id
        )
        return record['balance'] if record else None

async def update_balance(user_id: int, amount: float) -> bool:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute('''
                UPDATE users 
                SET balance = balance + $2 
                WHERE user_id = $1 AND balance + $2 >= 0
            ''', user_id, amount)
            return 'UPDATE 1' in result

async def get_leaderboard() -> List[Tuple[str, float]]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch('''
            SELECT username, balance 
            FROM users 
            ORDER BY balance DESC 
            LIMIT 5
        ''')
        return [(record['username'], record['balance']) for record in records]

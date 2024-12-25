import os
import asyncpg
from typing import Optional, List, Tuple
from decimal import Decimal
from datetime import datetime

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
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance DECIMAL DEFAULT 100.0,
                username TEXT NOT NULL
            )
        ''')

        # Create lottery table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS lotteries (
                lottery_id SERIAL PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                total_pot DECIMAL DEFAULT 0.0,
                winner_id BIGINT REFERENCES users(user_id) NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Create lottery_entries table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS lottery_entries (
                entry_id SERIAL PRIMARY KEY,
                lottery_id INTEGER REFERENCES lotteries(lottery_id),
                user_id BIGINT REFERENCES users(user_id),
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lottery_id, user_id)
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

async def delete_user(user_id: int) -> bool:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM users WHERE user_id = $1',
            user_id
        )
        return 'DELETE 1' in result

async def get_balance(user_id: int) -> Optional[Decimal]:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            'SELECT balance FROM users WHERE user_id = $1',
            user_id
        )
        return Decimal(str(record['balance'])) if record else None

async def update_balance(user_id: int, amount: float) -> bool:
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute('''
                UPDATE users 
                SET balance = balance + $2 
                WHERE user_id = $1 AND balance + $2 >= 0
            ''', user_id, Decimal(str(amount)))
            return 'UPDATE 1' in result

async def set_balance(user_id: int, amount: Decimal) -> bool:
    """Set a user's balance to a specific amount. Used by admin commands."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute('''
                UPDATE users 
                SET balance = $2 
                WHERE user_id = $1
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
        return [(record['username'], float(record['balance'])) for record in records]

async def create_lottery(start_time: datetime, end_time: datetime) -> int:
    """Create a new lottery and return its ID"""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'INSERT INTO lotteries (start_time, end_time) VALUES ($1, $2) RETURNING lottery_id',
            start_time, end_time
        )
        return row['lottery_id']

async def add_lottery_entry(lottery_id: int, user_id: int) -> bool:
    """Add a user entry to the lottery. Returns True if successful."""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                # First check if lottery exists and is active
                lottery = await conn.fetchrow(
                    'SELECT * FROM lotteries WHERE lottery_id = $1 AND is_active = TRUE',
                    lottery_id
                )
                if not lottery:
                    return False

                # Add entry and update pot
                await conn.execute(
                    'INSERT INTO lottery_entries (lottery_id, user_id) VALUES ($1, $2)',
                    lottery_id, user_id
                )
                await conn.execute(
                    'UPDATE lotteries SET total_pot = total_pot + 2 WHERE lottery_id = $1',
                    lottery_id
                )
                return True
        except asyncpg.UniqueViolationError:
            return False

async def get_active_lottery() -> Optional[dict]:
    """Get the currently active lottery"""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT lottery_id, start_time, end_time, total_pot, winner_id 
            FROM lotteries 
            WHERE is_active = TRUE 
            ORDER BY start_time DESC 
            LIMIT 1
        ''')
        return dict(row) if row else None

async def get_lottery_entries(lottery_id: int) -> List[int]:
    """Get all user IDs who entered a specific lottery"""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT user_id FROM lottery_entries WHERE lottery_id = $1',
            lottery_id
        )
        return [row['user_id'] for row in rows]

async def set_lottery_winner(lottery_id: int, winner_id: int) -> bool:
    """Set the winner for a lottery and mark it as inactive"""
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute('''
            UPDATE lotteries 
            SET winner_id = $2, is_active = FALSE 
            WHERE lottery_id = $1 AND is_active = TRUE
        ''', lottery_id, winner_id)
        return 'UPDATE 1' in result
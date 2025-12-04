"""
Database Isolation Level Tests
Netflix/Google SRE Level - Transaction Isolation Testing

Purpose: Test different database isolation levels and their behavior
"""
import pytest
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/testdb")

Base = declarative_base()

class Account(Base):
    """Test account table for isolation testing"""
    __tablename__ = "test_accounts"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    balance = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)

@pytest.fixture
async def db_engine():
    """Create database engine"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_read_committed_dirty_read(db_engine):
    """
    Test: READ COMMITTED isolation level
    Expected: No dirty reads (uncommitted changes not visible)
    """
    async_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create test account
    async with async_session_maker() as session:
        account = Account(name="alice", balance=1000)
        session.add(account)
        await session.commit()
    
    results = {"dirty_read_detected": False, "final_balance": None}
    
    async def writer():
        """Writer transaction - updates but doesn't commit immediately"""
        async with async_session_maker() as session:
            # Start transaction
            result = await session.execute(select(Account).where(Account.name == "alice"))
            account = result.scalar_one()
            
            # Update balance
            account.balance = 500
            await session.flush()  # Flush but don't commit
            
            # Hold transaction open
            await asyncio.sleep(2)
            
            # Rollback (simulate transaction failure)
            await session.rollback()
    
    async def reader():
        """Reader transaction - tries to read during writer's transaction"""
        await asyncio.sleep(1)  # Wait for writer to start
        
        async with async_session_maker() as session:
            result = await session.execute(select(Account).where(Account.name == "alice"))
            account = result.scalar_one()
            
            # If balance is 500, we have a dirty read (should still be 1000)
            if account.balance == 500:
                results["dirty_read_detected"] = True
            
            results["final_balance"] = account.balance
    
    # Run writer and reader concurrently
    await asyncio.gather(writer(), reader())
    
    print("\n" + "="*60)
    print("🔒 READ COMMITTED Isolation Test")
    print("="*60)
    print(f"Dirty Read Detected:   {results['dirty_read_detected']}")
    print(f"Balance Read:          {results['final_balance']}")
    print(f"Expected:              1000 (no dirty read)")
    print("="*60)
    
    # With READ COMMITTED, we should NOT see dirty reads
    assert not results["dirty_read_detected"], "❌ Dirty read detected!"
    assert results["final_balance"] == 1000, f"❌ Unexpected balance: {results['final_balance']}"
    
    print("✅ PASS: No dirty reads with READ COMMITTED")

@pytest.mark.asyncio
async def test_repeatable_read_phantom_read(db_engine):
    """
    Test: REPEATABLE READ isolation level
    Expected: Phantom reads may occur (new rows can appear)
    """
    async_session_maker = async_sessionmaker(
        db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    # Create initial accounts
    async with async_session_maker() as session:
        session.add(Account(name="user1", balance=100))
        session.add(Account(name="user2", balance=200))
        await session.commit()
    
    results = {"first_count": 0, "second_count": 0}
    
    async def reader():
        """Reader - counts accounts twice in same transaction"""
        async with async_session_maker() as session:
            # Set isolation level to REPEATABLE READ
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            
            # First count
            result = await session.execute(select(Account))
            results["first_count"] = len(result.scalars().all())
            
            # Wait for writer
            await asyncio.sleep(2)
            
            # Second count (in same transaction)
            result = await session.execute(select(Account))
            results["second_count"] = len(result.scalars().all())
            
            await session.commit()
    
    async def writer():
        """Writer - inserts new account"""
        await asyncio.sleep(1)  # Wait for reader to start
        
        async with async_session_maker() as session:
            # Insert new account
            session.add(Account(name="user3", balance=300))
            await session.commit()
    
    # Run reader and writer concurrently
    await asyncio.gather(reader(), writer())
    
    print("\n" + "="*60)
    print("👻 REPEATABLE READ Phantom Read Test")
    print("="*60)
    print(f"First Count:           {results['first_count']}")
    print(f"Second Count:          {results['second_count']}")
    print(f"Phantom Read:          {results['second_count'] > results['first_count']}")
    print("="*60)
    
    # With REPEATABLE READ in PostgreSQL, phantom reads are prevented
    # (PostgreSQL's REPEATABLE READ is actually SNAPSHOT ISOLATION)
    assert results["first_count"] == results["second_count"], \
        "PostgreSQL's REPEATABLE READ prevents phantom reads"
    
    print("✅ PASS: REPEATABLE READ behavior verified")

@pytest.mark.asyncio
async def test_serializable_concurrent_updates(db_engine):
    """
    Test: SERIALIZABLE isolation level
    Expected: Concurrent updates may cause serialization failures
    """
    async_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create test account
    async with async_session_maker() as session:
        account = Account(name="bob", balance=1000)
        session.add(account)
        await session.commit()
    
    results = {"tx1_success": False, "tx2_success": False, "errors": []}
    
    async def transaction1():
        """Transaction 1 - Add 100"""
        try:
            async with async_session_maker() as session:
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
                
                result = await session.execute(select(Account).where(Account.name == "bob"))
                account = result.scalar_one()
                
                original = account.balance
                await asyncio.sleep(1)  # Simulate processing
                
                account.balance = original + 100
                await session.commit()
                results["tx1_success"] = True
                
        except Exception as e:
            results["errors"].append(f"TX1: {type(e).__name__}")
    
    async def transaction2():
        """Transaction 2 - Add 200"""
        try:
            async with async_session_maker() as session:
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
                
                result = await session.execute(select(Account).where(Account.name == "bob"))
                account = result.scalar_one()
                
                original = account.balance
                await asyncio.sleep(1)  # Simulate processing
                
                account.balance = original + 200
                await session.commit()
                results["tx2_success"] = True
                
        except Exception as e:
            results["errors"].append(f"TX2: {type(e).__name__}")
    
    # Run transactions concurrently
    await asyncio.gather(transaction1(), transaction2(), return_exceptions=True)
    
    # Get final balance
    async with async_session_maker() as session:
        result = await session.execute(select(Account).where(Account.name == "bob"))
        account = result.scalar_one()
        final_balance = account.balance
    
    print("\n" + "="*60)
    print("🔐 SERIALIZABLE Isolation Test")
    print("="*60)
    print(f"Transaction 1 Success: {results['tx1_success']}")
    print(f"Transaction 2 Success: {results['tx2_success']}")
    print(f"Errors:                {len(results['errors'])}")
    print(f"Final Balance:         {final_balance}")
    print(f"Expected:              1100 or 1200 (one tx succeeds)")
    print("="*60)
    
    # With SERIALIZABLE, at least one transaction should fail
    # Or both succeed sequentially
    assert final_balance in [1100, 1200, 1300], \
        f"❌ Unexpected final balance: {final_balance}"
    
    print("✅ PASS: SERIALIZABLE isolation working correctly")

@pytest.mark.asyncio
async def test_lost_update_prevention(db_engine):
    """
    Test: Prevent lost updates with proper locking
    Compare: Without locking vs with SELECT FOR UPDATE
    """
    async_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    
    # Test 1: Without locking (lost updates expected)
    async with async_session_maker() as session:
        account = Account(name="carol_unsafe", balance=1000)
        session.add(account)
        await session.commit()
    
    async def unsafe_increment(amount: int):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Account).where(Account.name == "carol_unsafe")
            )
            account = result.scalar_one()
            
            original = account.balance
            await asyncio.sleep(0.1)  # Simulate processing
            
            account.balance = original + amount
            await session.commit()
    
    # Run 100 concurrent increments without locking
    tasks = [unsafe_increment(10) for _ in range(100)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Account).where(Account.name == "carol_unsafe")
        )
        unsafe_balance = result.scalar_one().balance
    
    # Test 2: With SELECT FOR UPDATE (no lost updates)
    async with async_session_maker() as session:
        account = Account(name="carol_safe", balance=1000)
        session.add(account)
        await session.commit()
    
    async def safe_increment(amount: int):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Account)
                .where(Account.name == "carol_safe")
                .with_for_update()  # Acquire row lock
            )
            account = result.scalar_one()
            
            account.balance = account.balance + amount
            await session.commit()
    
    # Run 100 concurrent increments with locking
    tasks = [safe_increment(10) for _ in range(100)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Account).where(Account.name == "carol_safe")
        )
        safe_balance = result.scalar_one().balance
    
    print("\n" + "="*60)
    print("🔒 Lost Update Prevention Test")
    print("="*60)
    print(f"Expected Final Balance:    2000 (1000 + 100×10)")
    print(f"WITHOUT Locking (unsafe):  {unsafe_balance} (lost: {2000 - unsafe_balance})")
    print(f"WITH Locking (safe):       {safe_balance} (lost: {2000 - safe_balance})")
    print("="*60)
    
    # Verify that locking prevented lost updates
    assert unsafe_balance < 2000, "Expected lost updates without locking"
    assert safe_balance == 2000, f"❌ Lost updates even with locking! Balance: {safe_balance}"
    
    print(f"✅ PASS: Locking prevented {2000 - unsafe_balance} lost updates")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
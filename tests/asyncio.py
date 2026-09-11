import asyncio
import time

async def io_bound_task(task_id: int):
    print(f"Task {task_id} started")
    await asyncio.sleep(1)  # Simulates I/O (e.g., fetching data)
    print(f"Task {task_id} finished")
    return f"Result {task_id}"

async def main():
    start = time.time()
    # Run 3 tasks concurrently
    results = await asyncio.gather(
        io_bound_task(1), 
        io_bound_task(2), 
        io_bound_task(3)
    )
    print(f"Completed in {time.time() - start:.2f}s with results: {results}")

if __name__ == "__main__":
    asyncio.run(main())
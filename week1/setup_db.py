import sqlite3


def create_datacenter_db():
    conn = sqlite3.connect("datacenter.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id TEXT PRIMARY KEY,
            hostname TEXT,
            rack_id TEXT,
            gpu_model TEXT,
            gpu_count INTEGER,
            status TEXT,
            temperature_c REAL,
            power_watts REAL
        )
    """)

    # Mock data: a small AI rack
    servers = [
        (
            "srv-001",
            "ai-gpu-node-01",
            "RACK-A1",
            "NVIDIA A100",
            8,
            "active",
            62.5,
            2800,
        ),
        (
            "srv-002",
            "ai-gpu-node-02",
            "RACK-A1",
            "NVIDIA A100",
            8,
            "active",
            65.1,
            2950,
        ),
        (
            "srv-003",
            "ai-gpu-node-03",
            "RACK-A2",
            "NVIDIA H100",
            4,
            "active",
            58.3,
            3200,
        ),
        ("srv-004", "ai-cpu-node-01", "RACK-B1", "None", 0, "active", 41.2, 450),
        (
            "srv-005",
            "ai-gpu-node-04",
            "RACK-A2",
            "NVIDIA H100",
            4,
            "maintenance",
            22.0,
            0,
        ),
        ("srv-006", "ai-storage-01", "RACK-C1", "None", 0, "active", 38.7, 600),
    ]

    cursor.executemany(
        "INSERT OR REPLACE INTO servers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", servers
    )
    conn.commit()
    conn.close()
    print("✅ Data center database created with 6 servers.")


if __name__ == "__main__":
    create_datacenter_db()

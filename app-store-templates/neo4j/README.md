# Neo4j

Neo4j is the world's leading graph database. It stores data as nodes, relationships, and properties, making it ideal for use cases where connections between data points are as important as the data itself – such as social networks, recommendation engines, fraud detection, knowledge graphs, and more.

## Ports

| Port | Purpose |
|---|---|
| 7474 | Neo4j Browser (HTTP web UI) |
| 7687 | Bolt protocol (used by all official drivers and clients) |

## Before You Start

**Change the password** in `docker-compose.yml`:

```yaml
- NEO4J_AUTH=neo4j/changeme_strong_password
```

Replace `changeme_strong_password` with a strong password. The username `neo4j` is the default and cannot be changed via this variable.

Generate a strong password:
```bash
openssl rand -base64 20
```

## Accessing Neo4j Browser

Open your browser and navigate to:

```
http://<your-server-ip>:7474
```

- **Connection URL**: `bolt://<your-server-ip>:7687`
- **Username**: `neo4j`
- **Password**: the value you set in `NEO4J_AUTH`

## Connecting with Drivers

Use the Bolt URL for all official language drivers:

```
bolt://<your-server-ip>:7687
```

Example (Python):
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "changeme_strong_password")
)
```

## APOC Plugin

[APOC](https://neo4j.com/labs/apoc/) (Awesome Procedures on Cypher) is automatically installed and provides 450+ utility procedures for data import/export, graph algorithms, and more.

Example APOC usage in Cypher:
```cypher
CALL apoc.help("apoc") YIELD name, text RETURN name, text LIMIT 10
```

## Memory Tuning

Adjust these variables in `docker-compose.yml` based on available RAM:

| Variable | Default | Description |
|---|---|---|
| `NEO4J_dbms_memory_heap_initial__size` | `512m` | Initial JVM heap |
| `NEO4J_dbms_memory_heap_max__size` | `1G` | Max JVM heap |
| `NEO4J_dbms_memory_pagecache_size` | `512m` | Page cache for graph data |

Rule of thumb: heap + pagecache should not exceed 60–70 % of total RAM.

## Importing Data

Place CSV or other import files in `/opt/upcode-harbor/data/neo4j/import/` – they will be accessible inside the container at `/var/lib/neo4j/import/`.

```cypher
LOAD CSV WITH HEADERS FROM 'file:///mydata.csv' AS row
CREATE (:Person {name: row.name, age: toInteger(row.age)})
```

## More Information

- [Neo4j Website](https://neo4j.com)
- [GitHub](https://github.com/neo4j/neo4j)
- [Docker Hub](https://hub.docker.com/_/neo4j)
- [Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [APOC Documentation](https://neo4j.com/labs/apoc/5/introduction/)

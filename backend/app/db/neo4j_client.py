from neo4j import Driver, GraphDatabase


# DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_URI = "neo4j+s://c6010ae0.databases.neo4j.io"
DEFAULT_NEO4J_USER = "neo4j"
# DEFAULT_NEO4J_PASSWORD = "Keytop@123"
DEFAULT_NEO4J_PASSWORD = "GMaCBUonUoHZCYcqa8mBho_FAjVBnykTlEdgpMKLdZU"
DEFAULT_NEO4J_DATABASE = "neo4j"


def get_neo4j_driver() -> Driver:
    return GraphDatabase.driver(
        DEFAULT_NEO4J_URI,
        auth=(DEFAULT_NEO4J_USER, DEFAULT_NEO4J_PASSWORD),
        max_connection_pool_size=100,        # 降低连接池大小，适配Aura Free tier
        connection_timeout=30 * 1000,            # 连接超时30秒
        max_connection_lifetime=1800 * 1000,       # 连接存活30分钟
        max_transaction_retry_time=30 * 1000,    # 事务重试30秒
    )

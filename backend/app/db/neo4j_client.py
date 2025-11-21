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
    )

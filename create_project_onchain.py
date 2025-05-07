from web3 import Web3
import psycopg2
from dotenv import load_dotenv
import os
import time

load_dotenv(dotenv_path="config.env")
OPENFUND_PRIVATEKEY = os.getenv("OPENFUND_PRIVATEKEY")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_db_connection():
    """Establish and return a database connection"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

def get_pending_projects():
    """Get all accepted projects that haven't been listed on chain yet"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                id, funding_address, token_address, token_to_sell, 
                token_price, investment_end_time, decimal
            FROM project
            WHERE 
               listing_status = 'accepted' AND funding_status = 'not listed'
        """
        cursor.execute(query)
        projects = cursor.fetchall()
        return projects
    except psycopg2.Error as e:
        print(f"Error fetching pending projects: {e}")
        return []
    finally:
        conn.close()

def update_project_status(project_id):
    """Update project status after successful on-chain creation"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        query = """
            UPDATE project 
            SET funding_status = 'created'
            WHERE id = %s
        """
        cursor.execute(query, (project_id,))
        conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Error updating project status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def create_project_onchain(project_data):
    """Create a project on the blockchain"""
    project_id, raiser, token_address, tokens_to_sell, token_price, end_funding_time, token_decimals = project_data
    # Convert values to appropriate formats
    token_price_wei = int(float(token_price) * 10**6)
    tokens_to_sell = int(tokens_to_sell)
    token_decimals = int(token_decimals)
    
    try:
        # Get the current nonce
        nonce = w3.eth.get_transaction_count(deployer_address)
        
        # Build the transaction
        create_txn = open_fund_contract.functions.createProject(
            project_id,
            Web3.to_checksum_address(raiser),
            Web3.to_checksum_address(token_address),
            tokens_to_sell,
            token_price_wei,
            end_funding_time,
            token_decimals
        ).build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
        })
        
        # Sign and send the transaction
        signed_txn = w3.eth.account.sign_transaction(create_txn, private_key=OPENFUND_PRIVATEKEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"Project created with ID: {project_id}")
        print(f"Transaction hash: {tx_hash.hex()}")
        
        # Update project status in database
        if update_project_status(project_id):
            print(f"Project {project_id} status updated to 'created'")
        else:
            print(f"Failed to update project {project_id} status")
            
        return True
    except Exception as error:
        print(f"Error creating project {project_id}: {str(error)}")
        return False

# Setup blockchain connection
provider_url = "https://evm-rpc-arctic-1.sei-apis.com"
w3 = Web3(Web3.HTTPProvider(provider_url))

if not w3.is_connected():
    print("Failed to connect to the provider")
    exit(1)

account = w3.eth.account.from_key(OPENFUND_PRIVATEKEY)
deployer_address = account.address

open_fund_address = Web3.to_checksum_address("0x6b2b43b3b162c2a7aea56c8422fd34a94847f2c0")
open_fund_abi = [
   {
      "inputs": [
            {"name": "_projectId", "type": "uint256"},
            {"name": "_raiser", "type": "address"},
            {"name": "_tokenAddress", "type": "address"},
            {"name": "_tokensToSell", "type": "uint256"},
            {"name": "_tokenPrice", "type": "uint256"},
            {"name": "_endFundingTime", "type": "uint256"},
            {"name": "_decimal", "type": "uint8"}
      ],
      "name": "createProject",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
   }
]

open_fund_contract = w3.eth.contract(address=open_fund_address, abi=open_fund_abi)

try:
    while True:
        pending_projects = get_pending_projects()
        
        if pending_projects:
            print(f"Found {len(pending_projects)} pending projects to process")
            for project in pending_projects:
                create_project_onchain(project)
        else:
            print("No pending projects found")
            
        print("Sleeping for 20 seconds...")
        time.sleep(20)
except KeyboardInterrupt:
    print("Script terminated by user")
except Exception as e:
    print(f"Error in main loop: {e}")
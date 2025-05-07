import os
import time
import psycopg2
from dotenv import load_dotenv
from web3 import Web3
from enum import IntEnum

class ProjectStatus(IntEnum):
    InitialCreated = 0
    RaisingPeriod = 1
    VotingPeriod = 2
    FundingFailed = 3
    FundingCompleted = 4

load_dotenv(dotenv_path="config.env")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

RPC_URL = "https://evm-rpc-arctic-1.sei-apis.com"
CONTRACT_ADDRESS = Web3.to_checksum_address("0x6b2b43b3b162c2a7aea56c8422fd34a94847f2c0")

CONTRACT_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "_projectId", "type": "uint256"}],
        "name": "getProjectDetails",
        "outputs": [
            {"internalType": "address", "name": "raiser", "type": "address"},
            {"internalType": "address", "name": "tokenAddress", "type": "address"},
            {"internalType": "uint256", "name": "tokensToSell", "type": "uint256"},
            {"internalType": "uint256", "name": "tokensSold", "type": "uint256"},
            {"internalType": "uint256", "name": "tokenPrice", "type": "uint256"},
            {"internalType": "uint256", "name": "endFundingTime", "type": "uint256"},
            {"internalType": "uint256", "name": "fundsRaised", "type": "uint256"},
            {"internalType": "enum OpenFund.ProjectStatus", "name": "status", "type": "uint8"},
            {"internalType": "bool", "name": "unsoldTokensClaimed", "type": "bool"},
            {"internalType": "uint256", "name": "voteForRefundAmount", "type": "uint256"},
            {"internalType": "bool", "name": "fundsClaimed", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

UPDATE_INTERVAL = 1


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


def get_active_projects():
    """Get projects with raising or voting status"""
    projects = []
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, funding_status 
            FROM project 
            WHERE funding_status IN ('raising', 'voting', 'created') 
            AND listing_status = 'accepted'
        """)
        
        projects = cur.fetchall()
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.close()
    
    return projects

def get_contract_project_details(web3, contract, project_id):
    """Query the blockchain for project details"""
    try:
        return contract.functions.getProjectDetails(project_id).call()
    except Exception as e:
        print(f"Error fetching project details from contract: {e}")
        return None


def update_project_in_database(project_id, tokens_sold, funds_raised, status, vote_for_refund, funds_claimed):
    """Update project information in the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        db_status = 'raising'
        if status == ProjectStatus.VotingPeriod:
            db_status = 'voting'
        elif status == ProjectStatus.InitialCreated:
            db_status = 'created'
        elif status == ProjectStatus.FundingFailed:
            db_status = 'failed'
        elif status == ProjectStatus.FundingCompleted:
            db_status = 'completed'
        
        cur.execute("""
            UPDATE project 
            SET token_sold = %s, 
                fund_raised = %s, 
                funding_status = %s,
                vote_for_refund = %s,
                fund_claimed = %s
            WHERE id = %s
        """, (tokens_sold, funds_raised, db_status, vote_for_refund, funds_claimed, project_id))
        print(f"Project {project_id} updated successfully")
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Database update error: {e}")
        if conn:
            conn.close()
        return False


def main_loop():
    """Main processing loop"""
    
    try:
        web3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not web3.is_connected():
            return
        
        contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    except Exception as e:
        print(f"Web3 connection error: {e}")
        return
    
    while True:
        try:
            projects = get_active_projects()
            
            for project_id, current_status in projects:
                project_details = get_contract_project_details(web3, contract, project_id)
                
                if project_details:
                    _, _, _, tokens_sold, _, _, funds_raised, status, _, vote_for_refund, funds_claimed = project_details
                    update_project_in_database(
                        project_id=project_id,
                        tokens_sold=tokens_sold,
                        funds_raised=funds_raised / 10**6,
                        status=status,
                        vote_for_refund=vote_for_refund,
                        funds_claimed=funds_claimed
                    )
            
            time.sleep(UPDATE_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
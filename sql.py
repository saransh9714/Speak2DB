import sqlite3
import pandas as pd

# Load the CSV files into DataFrames
customer_table = pd.read_csv("CustomerTable.csv")
sales_table = pd.read_csv("SalesTable.csv")
transaction_log = pd.read_csv("TransactionLog.csv")

# Connect to SQLite database (or create one if it doesn't exist)
conn = sqlite3.connect("sales_database.db", check_same_thread=False)
cursor = conn.cursor()

# Create tables in the database
def create_tables():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CustomerTable (
            Customer_ID TEXT PRIMARY KEY,
            First_Name TEXT,
            Last_Name TEXT,
            Email TEXT,
            Phone TEXT,
            Address TEXT,
            City TEXT,
            State TEXT,
            Registration_Date DATE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SalesTable (
            Sale_ID TEXT PRIMARY KEY,
            Customer_ID TEXT,
            Product_ID TEXT,
            Product_Name TEXT,
            Category TEXT,
            Quantity INTEGER,
            Unit_Price REAL,
            Discount REAL,
            Sale_Date DATE,
            FOREIGN KEY (Customer_ID) REFERENCES CustomerTable(Customer_ID)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TransactionLog (
            Transaction_ID TEXT PRIMARY KEY,
            Customer_ID TEXT,
            Transaction_Date DATE,
            Transaction_Type TEXT,
            Amount REAL,
            Payment_Mode TEXT,
            Status TEXT,
            Channel TEXT,
            Merchant_ID TEXT,
            FOREIGN KEY (Customer_ID) REFERENCES CustomerTable(Customer_ID)
        )
    """)

# Insert data into the tables
def insert_data():
    # Insert data into CustomerTable
    customer_table.to_sql("CustomerTable", conn, if_exists="replace", index=False)
    
    # Insert data into SalesTable
    sales_table.to_sql("SalesTable", conn, if_exists="replace", index=False)
    
    # Insert data into TransactionLog
    transaction_log.to_sql("TransactionLog", conn, if_exists="replace", index=False)

# Example queries
def example_queries():
    # Query 1: Get all customers who purchased a specific product
    product_name = "Smartphone"
    cursor.execute("""
        SELECT c.First_Name, c.Last_Name, c.Email, s.Product_Name, s.Sale_Date
        FROM CustomerTable c
        JOIN SalesTable s ON c.Customer_ID = s.Customer_ID
        WHERE s.Product_Name = ?
    """, (product_name,))
    results = cursor.fetchall()
    print("Customers who purchased a", product_name, ":")
    for row in results:
        print(row)
    

# Main function
def main():
    create_tables()
    insert_data()
    example_queries()

if __name__ == "__main__":
    main()
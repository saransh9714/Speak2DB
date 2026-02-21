from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
# print("DEBUG API KEY:", os.getenv("GOOGLE_API_KEY"))

import os
import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import speech_recognition as sr  # For speech-to-text conversion
# import pyttsx3  # For text-to-speech conversion

# Configure the API key
try:
    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
except Exception as e:
    st.error(f"Error configuring Google Gemini API: {e}")

def fetch_database_schema():
    try:
        conn = sqlite3.connect("sales_database.db")
        cursor = conn.cursor()

        # Fetch all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            st.error("No tables found in the database.")
            return "No schema available."

        schema = "Database Schema (EXACT STRUCTURE):\n"
        for table in tables:
            table_name = table[0]
            schema += f"{table_name}:\n"
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for column in columns:
                column_name = column[1]
                column_type = column[2]
                schema += f"  - {column_name} ({column_type})\n"
            schema += "\n"

        conn.close()
        return schema
    except Exception as e:
        st.error(f"Error fetching database schema: {e}")
        return "Error fetching schema."

def generate_prompt():
    schema = fetch_database_schema()
    if "Error" in schema or "No schema available" in schema:
        st.error("Failed to generate prompt due to schema issues.")
        return None

    prompt = f"""
    You are an expert SQLite query generator that converts natural language to perfect SQL queries for the following exact schema:

    {schema}

    **Strict Generation Rules:**
    1. Use ONLY these exact table and column names - never modify or guess names.
    2. For date operations, use SQLite DATE functions.
    3. For monetary calculations, include discount properly: (Quantity * Unit_Price * (1 - Discount)).
    4. Always use explicit JOINs with ON clauses for relationships.

    **Output Requirements:**
    - ONLY executable SQL code.
    - NO markdown formatting.
    - NO database labels.
    - NO comments or explanations.
    - NO trailing semicolons.

    **Error Prevention:**
    1. Never use table/column names not in the provided schema.
    2. Always verify joins use correct foreign keys.
    3. For date filtering, use: DATE('now') or strftime().
    4. For status checks, use exact values like 'Failed' (with quotes).

    **Validation Steps (MUST DO):**
    1. Verify all table/column names match the exact schema.
    2. Check all JOINs use correct foreign key relationships.
    3. Ensure monetary calculations include discount.
    4. Confirm date operations use SQLite functions.
    5. Remove any non-SQL text.

    **Examples:**

    Natural language: Show all customers who placed an order in the last 30 days  
    SQL:
    SELECT DISTINCT Customers.CustomerID, Customers.CustomerName  
    FROM Orders  
    JOIN Customers ON Orders.CustomerID = Customers.CustomerID  
    WHERE DATE(Orders.OrderDate) >= DATE('now', '-30 days')

    Natural language: Find total revenue per product after discounts  
    SQL:
    SELECT Products.ProductName, SUM(Order_Details.Quantity * Order_Details.Unit_Price * (1 - Order_Details.Discount)) AS TotalRevenue  
    FROM Order_Details  
    JOIN Products ON Order_Details.ProductID = Products.ProductID  
    GROUP BY Products.ProductID

    Natural language: Get list of employees who processed more than 10 orders  
    SQL:
    SELECT Employees.EmployeeID, Employees.EmployeeName, COUNT(Orders.OrderID) AS TotalOrders  
    FROM Orders  
    JOIN Employees ON Orders.EmployeeID = Employees.EmployeeID  
    GROUP BY Employees.EmployeeID  
    HAVING COUNT(Orders.OrderID) > 10

    Natural language: List all orders with status 'Failed'  
    SQL:
    SELECT *  
    FROM Orders  
    WHERE Orders.Status = 'Failed'

    Natural language: Retrieve the average discount given per product  
    SQL:
    SELECT Products.ProductName, AVG(Order_Details.Discount) AS AvgDiscount  
    FROM Order_Details  
    JOIN Products ON Order_Details.ProductID = Products.ProductID  
    GROUP BY Products.ProductID
    """
    return prompt

def get_gemini_response(question, prompt, history):
    try:
        if not prompt:
            st.error("Prompt is empty. Cannot generate response.")
            return None

        # Build the history context
        history_context = ""
        for i, entry in enumerate(history[-3:], 1):  # Include up to the last 3 interactions
            history_context += f"""
            Previous Question {i}:
            {entry['input']}

            SQL Query {i}:
            {entry['sql_query']}

            Result {i}:
            {pd.DataFrame(entry['result']).head(5).to_string(index=False)}  # Show only the first 5 rows
            """

        # Combine the history context with the current question
        full_prompt = f"""
        {prompt}

        Conversation History:
        {history_context}

        Current Question:
        {question}
        """

        # Send the full prompt to Gemini
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([full_prompt])
        return response.text
    except Exception as e:
        st.error(f"Error generating response from Gemini: {e}")
        return None

# Function to convert speech to text
def speech_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎙️ Listening... Please speak your question.")
        try:
            audio = recognizer.listen(source, timeout=12)  # Listen for 12 seconds
            text = recognizer.recognize_google(audio)  # Use Google Speech Recognition
            return text
        except sr.UnknownValueError:
            st.error("❌ Could not understand the audio. Please try again.")
        except sr.RequestError as e:
            st.error(f"❌ Could not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            st.error(f"❌ An error occurred: {e}")
    return ""
# def speech_to_text():
#     recognizer = sr.Recognizer()
#     try:
#         with sr.AudioFile(uploaded_file) as source:
#             audio = recognizer.record(source)
#             text = recognizer.recognize_google(audio)
#             return text
#     except sr.UnknownValueError:
#         st.error("❌ Could not understand the audio. Please try again.")
#     except sr.RequestError as e:
#         st.error(f"❌ Could not request results from Google; {e}")
#     except Exception as e:
#         st.error(f"❌ Error: {e}")
#     return ""


# Function to handle speech input for both questions and visualization types
def handle_speech_input():
    recognized_text = speech_to_text()
    if recognized_text:
        # Map recognized text to visualization types
        visualization_mapping = {
            "bar chart": "Bar Chart",
            "line chart": "Line Chart",
            "pie chart": "Pie Chart",
            "area chart": "Area Chart",
            "histogram": "Histogram",
            "summary": "Summary"
        }

        # Check if the recognized text matches a visualization type
        for key, value in visualization_mapping.items():
            if key in recognized_text.lower():
                st.session_state.visualization_type = value
                st.success(f"✅ Visualization type set to: {value}")
                return

        # If no visualization type is detected, treat it as a question
        st.session_state.user_question = recognized_text
        st.success(f"✅ Your question: {recognized_text}")

# Function to convert text to speech
# def text_to_speech(text):
#     try:
#         engine = pyttsx3.init()  # Initialize the text-to-speech engine
#         engine.say(text)  # Queue the text to be spoken
#         engine.runAndWait()  # Play the speech
#     except Exception as e:
#         st.error(f"Error in text-to-speech conversion: {e}")

from gtts import gTTS
from io import BytesIO
import streamlit as st

def text_to_speech(text):
    try:
        tts = gTTS(text)
        fp = BytesIO()
        tts.write_to_fp(fp)
        st.audio(fp.getvalue(), format='audio/mp3')  # Auto plays
    except Exception as e:
        st.error(f"Error in text-to-speech: {e}")



# Function to generate a summary of the SQL query output using Gemini
def get_gemini_summary(dataframe, user_question):
    try:
        # Convert the DataFrame to a string representation for the prompt
        data_preview = dataframe.head(10).to_string(index=False)  # Show only the first 10 rows
        prompt = f"""
        You are an expert data summarizer. Summarize the following data in a concise and meaningful way.

        User Question:
        {user_question}

        Data Preview:
        {data_preview}

        Provide a summary that highlights key insights, trends, or patterns in the data.
        """
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([prompt])
        return response.text
    except Exception as e:
        st.error(f"Error generating summary from Gemini: {e}")
        return None

def main():
    st.set_page_config(page_title="Gemini SQL Query Generator", layout="wide")

    # Custom CSS
    st.markdown(
        """
        <style>
            header { visibility: hidden; }
            .block-container { padding-top: 1rem; padding-bottom: 1rem; }
            [data-testid="stSidebar"] { padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Welcome Banner
    st.markdown(
        """
        <div style="background-color: #037ffc; padding: 10px; border-radius: 5px;">
            <h2 style="color: white; text-align: center;">Welcome to Speak2DB!</h2>
        </div>
        <div style='padding: 0;'>
        <hr style='border: 1px solid #ccc;'/>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Initialize session state for history and introductory message
    if "history" not in st.session_state:
        st.session_state.history = []  # Initialize history as an empty list
    if "intro_message_spoken" not in st.session_state:
        st.session_state.intro_message_spoken = False  # Track if the intro message has been spoken

    #st.badge("Turn your voice into powerful database queries — no SQL skills needed!")
    st.markdown('''Turn your voice into powerful database queries — no SQL skills needed! :balloon:''')

    # Sidebar content
    with st.sidebar:
        st.title("Dataset Reference")
        # Add a link to reference the dataset
        with st.expander("📂 Click here to reference the dataset"):
            st.subheader("CustomerTable")
            conn = sqlite3.connect("sales_database.db")
            try:
                customer_data = pd.read_sql_query("SELECT * FROM CustomerTable", conn)
                st.dataframe(customer_data)
            except Exception as e:
                st.error("Error loading CustomerTable: " + str(e))

            st.subheader("SalesTable")
            try:
                sales_data = pd.read_sql_query("SELECT * FROM SalesTable", conn)
                st.dataframe(sales_data)
            except Exception as e:
                st.error("Error loading SalesTable: " + str(e))

            st.subheader("TransactionLog")
            try:
                transaction_data = pd.read_sql_query("SELECT * FROM TransactionLog", conn)
                st.dataframe(transaction_data)
            except Exception as e:
                st.error("Error loading TransactionLog: " + str(e))

            conn.close()
        st.markdown("---")
        st.info("Conversation History")
        st.caption("This section shows the last 5 interactions with the app.")

        # Display history of inputs, SQL queries, and outputs with dropdowns
        if st.session_state.history:
            for i, entry in enumerate(reversed(st.session_state.history[-5:]), 1):
                with st.expander(f"Question {i}: {entry['input']}"):
                    # Display the SQL query
                    st.markdown(f"**SQL Query:**\n```sql\n{entry['sql_query']}\n```")

                    # Display the database result as a table
                    st.markdown("**Result:**")
                    result_df = pd.DataFrame(entry["result"])  # Convert the stored dictionary back to a DataFrame
                    st.dataframe(result_df)

                    # Display the summary output
                    if "output" in entry:
                        st.markdown(f"**Summary:** {entry['output']}")
        else:
            st.write("No history available.")

    # Text input for user question
    st.subheader("Enter/Speak Your Question:")

    # Initialize session state for user question
    if "user_question" not in st.session_state:
        st.session_state.user_question = ""  # Initialize with an empty string

    # Add a button for speech-to-text input
    if st.button("🎤 Speak Your Question"):
        handle_speech_input()

    # Editable text input field
    user_question = st.text_input(
        "Enter your question:" if not st.session_state.user_question else "Edit your question here:",
        value=st.session_state.user_question,
        key="user_question_input",  # Assign a unique key to the input box
        on_change=lambda: st.session_state.update({"user_question": st.session_state.user_question_input})
    )
    

    # Update session state with the edited text
    st.session_state.user_question = user_question

    # Speak introductory message
    if "intro_message_spoken" not in st.session_state:
        st.session_state.intro_message_spoken = False

    if not st.session_state.intro_message_spoken:
        intro_message = (
            "Hello! I’m your assistant here to help you communicate with your database. "
            "Click the button and tell me what data you need, along with your query. "
            "I can also help visualize the results if you'd like."
        )
        text_to_speech(intro_message)
    st.session_state.intro_message_spoken = True

    df = pd.DataFrame()  # Initialize df to avoid reference before assignment

    # Generate and Run SQL
    if user_question:
        with st.spinner("Generating SQL query using Gemini..."):
            try:
                # Generate the prompt
                prompt = generate_prompt()
                if not prompt:
                    st.error("Failed to generate prompt. Please check the database schema.")
                    return

                # Pass the history to the Gemini response function
                response = get_gemini_response(user_question, prompt, st.session_state.history)
                if not response:
                    st.error("Failed to generate response from Gemini.")
                    return
                
                # Clean the SQL query
                sql_query1 = response.strip().replace("sqlite", "").strip("```").strip()
                sql_query = sql_query1.replace("sql", "")  # Remove sql from the query

                st.subheader("📝 Generated SQL Query")
                st.code(sql_query, language="sql")
            except Exception as e:
                st.error(f"Error generating SQL: {e}")
                st.stop()

        with st.spinner("📡 Executing query on SQLite..."):
            try:
                conn = sqlite3.connect("sales_database.db")
                df = pd.read_sql_query(sql_query, conn)
                conn.close()
                st.success("✅ Query executed successfully!")

                # Add the SQL query and result to history
                st.session_state.history.append({
                    "input": user_question,
                    "sql_query": sql_query,
                    "result": df.to_dict()  # Convert DataFrame to a dictionary for storage
                })
            except Exception as e:
                st.error(f"SQL Execution Error: {e}")
                st.stop()

    # Display Results
    if not df.empty:
        # Always show the table view
        st.subheader("📋 Table View of the Data")
        st.dataframe(df)

        # Handle single-number or single-cell result
        if df.shape == (1, 1):
            st.subheader("🔢 Single Value Result")
            st.metric(label=df.columns[0], value=df.iloc[0, 0])

        # Initialize session state for visualization type
        if "visualization_type" not in st.session_state:
            st.session_state.visualization_type = "Bar Chart"  # Default visualization type

        # Dropdown for charts and summary only (when there is more than one column)
        if df.shape[1] > 1:
            st.subheader("📊 Choose how to visualize the result")

            # Display the current visualization type
            st.info(f"Current Visualization Type: {st.session_state.visualization_type}")

            # Render the selected visualization
            output_type = st.session_state.visualization_type
            if output_type != "Summary":
                with st.expander("📈 Chart Settings", expanded=True):
                    if df.shape[1] < 2:
                        st.warning("Need at least two columns for charting.")
                    else:
                        x_col = st.selectbox("X-axis", df.columns, index=0)
                        y_col = st.selectbox("Y-axis", df.columns, index=1)
                        theme_color = st.color_picker("🎨 Pick a chart color", "#636EFA")

                        if output_type == "Bar Chart":
                            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=[theme_color])
                        elif output_type == "Line Chart":
                            fig = px.line(df, x=x_col, y=y_col, color_discrete_sequence=[theme_color])
                        elif output_type == "Pie Chart":
                            fig = px.pie(df, names=x_col, values=y_col)
                        elif output_type == "Area Chart":
                            fig = px.area(df, x=x_col, y=y_col, color_discrete_sequence=[theme_color])
                        elif output_type == "Histogram":
                            fig = px.histogram(df, x=y_col, nbins=20, color_discrete_sequence=[theme_color])

                        st.plotly_chart(fig, use_container_width=True)

            else:
                # Summary section
                st.subheader("🧾 Summary")
                if df.shape[1] >= 2:
                    total = df.iloc[:, 1].sum()
                    top_row = df.iloc[df.iloc[:, 1].idxmax()]
                    st.markdown(f"- **Total {df.columns[1]}**: {total}")
                    st.markdown(f"- **Top {df.columns[0]}**: {top_row[0]} with value {top_row[1]}")
                else:
                    st.info("Not enough data to summarize.")

    # Generate and display the summary using Gemini
    if not df.empty:  # Ensure the DataFrame is not empty
        st.subheader("📄 Summary of the Output")
        with st.spinner("Generating summary using Gemini..."):
            summary = get_gemini_summary(df, user_question)  # Generate the summary
            if summary:
                st.write(summary)  # Display the summary
                # Automatically play the summary as audio
                text_to_speech(summary)
                # Update the history with the summary
                st.session_state.history[-1]["output"] = summary  # Add the summary to the last history entry


# Run the main function
if __name__ == "__main__":
    main()
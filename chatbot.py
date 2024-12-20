import os
from typing import List, Tuple
from utils.load_config import LoadConfig
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from sqlalchemy import create_engine
from langchain_community.agent_toolkits import create_sql_agent
import langchain
import openai 
langchain.debug = True

APPCFG = LoadConfig()


class ChatBot:

    def respond(chatbot: List, message: str, chat_type: str, app_functionality: str) -> Tuple:
        """
        Respond to a message based on the given chat types.

        Args:
            chatbot (List): A list representing the chatbot's conversation history.
            message (str): The user's input message to the chatbot.
            chat_type (str): Describes the type of the chat (interaction with SQL DB or RAG).
            app_functionality (str): Identifies the functionality for which the chatbot is being used (e.g., 'Chat').

        """

        if app_functionality == "Chat":
        # chat_type == "Q&A with stored CSV/XLSX SQL-DB"
            if chat_type == "Q&A with stored SQL-DB":
                # directories
                if os.path.exists(APPCFG.sqldb_directory):
                    db = SQLDatabase.from_uri(
                        f"sqlite:///{APPCFG.sqldb_directory}")
                    execute_query = QuerySQLDataBaseTool(db=db)
                    write_query = create_sql_query_chain(
                        APPCFG.langchain_llm, db)
                    answer_prompt = PromptTemplate.from_template(
                        APPCFG.agent_llm_system_role)
                    answer = answer_prompt | APPCFG.langchain_llm | StrOutputParser()
                    chain = (
                        RunnablePassthrough.assign(query=write_query).assign(
                            result=itemgetter("query") | execute_query
                        )
                        | answer
                    )
                    response = chain.invoke({"question": message})

                else:
                    chatbot.append(
                        (message, f"SQL DB does not exist. Please first create the 'sqldb.db'."))
                    return "", chatbot, None
            # chat_type == "Q&A with stored CSV/XLSX SQL-DB"
            elif chat_type == "Q&A with Uploaded CSV/XLSX SQL-DB" or chat_type == "Q&A with stored CSV/XLSX SQL-DB":
                if chat_type == "Q&A with Uploaded CSV/XLSX SQL-DB":
                    if os.path.exists(APPCFG.uploaded_files_sqldb_directory):
                        engine = create_engine(
                            f"sqlite:///{APPCFG.uploaded_files_sqldb_directory}")
                        db = SQLDatabase(engine=engine)
                        print(db.dialect)
                    else:
                        chatbot.append(
                            (message, f"SQL DB from the uploaded csv/xlsx files does not exist. Please first upload the csv files from the chatbot."))
                        return "", chatbot, None
                elif chat_type == "Q&A with stored CSV/XLSX SQL-DB":
                    if os.path.exists(APPCFG.stored_csv_xlsx_sqldb_directory):
                        engine = create_engine(
                            f"sqlite:///{APPCFG.stored_csv_xlsx_sqldb_directory}")
                        db = SQLDatabase(engine=engine)
                    else:
                        chatbot.append(
                            (message, f"SQL DB from the stored csv/xlsx files does not exist. Please first execute `src/prepare_csv_xlsx_sqlitedb.py` module."))
                        return "", chatbot, None
                print(db.dialect)
                print(db.get_usable_table_names())
                agent_executor = create_sql_agent(
                    APPCFG.langchain_llm, db=db, agent_type="openai-tools", verbose=True)
                response = agent_executor.invoke({"input": message})
                response = response["output"]
            ### chat_type == "RAG with stored CSV/XLSX ChromaDB"
            elif chat_type == "RAG with stored CSV/XLSX ChromaDB":
                try:
                    # Use OpenAI client for embeddings
                    response = openai.Embedding.create(
                        input=message,
                        model=APPCFG.embedding_model_name
                    )
                    query_embeddings = response['data'][0]['embedding']
                    
                    # Debugging: Check if embeddings are generated
                    print(f"Generated embeddings: {query_embeddings}")

                    vectordb = APPCFG.chroma_client.get_collection(
                        name=APPCFG.collection_name
                    )
                    
                    # Debugging: Check if collection is retrieved
                    print(f"Retrieved collection: {vectordb}")

                    results = vectordb.query(
                        query_embeddings=query_embeddings,
                        n_results=APPCFG.top_k
                    )
                    
                    # Debugging: Check if results are retrieved
                    print(f"Query results: {results}")

                    prompt = f"User's question: {message} \n\n Search results:\n {results}"

                    messages = [
                        {"role": "system", "content": str(
                            APPCFG.rag_llm_system_role
                        )},
                        {"role": "user", "content": prompt}
                    ]

                    # Debugging: Check if messages and model are set correctly
                    print(f"Messages: {messages}")
                    print(f"Model: {APPCFG.model_name}")

                    # Use OpenAI client for chat completions
                    llm_response = openai.ChatCompletion.create(
                        model=APPCFG.model_name,
                        messages=messages
                    )
                    response = llm_response['choices'][0]['message']['content']
                except Exception as e:
                    print(f"Error with OpenAI API or ChromaDB: {e}")
                    response = "There was an error processing your request."

            # Get the `response` variable from any of the selected scenarios and pass it to the user.
            chatbot.append(
                (message, response))
            return "", chatbot
        else:
            pass

import os

from sklearn.datasets import load_iris, load_wine
import pandas as pd
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
from pyspark.sql import SparkSession

this_dir = os.path.dirname(os.path.abspath(__file__))
metastore_path = os.path.join(this_dir, "metastore_db")
warehouse_path = os.path.join(this_dir, "spark-warehouse")

spark = SparkSession.builder.appName('dataset')\
    .config('spark.sql.catalogImplementation', 'hive') \
    .config("javax.jdo.option.ConnectionURL", f"jdbc:derby:;databaseName={metastore_path};create=true") \
    .config("spark.sql.warehouse.dir", warehouse_path) \
    .enableHiveSupport().getOrCreate()

create_sql_prompt = """\
与えられた指示に適切なSQLクエリをテーブル定義を利用しつつ回答して下さい。

制約:
・出力をそのままSQL文として実行するので、余計な文言を入れずにSQL文のみを出力して下さい。
・インプリシットカラムアンチパターンは止めて出力の列名は必ず明記して下さい。

出力例:
SELECT COLUMN1, COLUMN2 FROM TABLEX WHERE COLUMN3 = "XXX";

指示: {instruction}

テーブル定義: 
{table_definition}

"""
create_sql_template = PromptTemplate.from_template(create_sql_prompt)

llm = ChatOpenAI()

create_sql_chain = create_sql_template | llm | StrOutputParser()

# テーブル定義の取得
def get_table_definition():

    result = spark.sql(f"SHOW CREATE TABLE IRIS")
    create_table_stmt = result.collect()[0].createtab_stmt
    print('create_table_stmt:', create_table_stmt)
    return create_table_stmt

# データの取得
def get_sql_data(instruction):

    # テーブル定義の取得
    table_definition = get_table_definition()

    # SQL生成
    create_sql = create_sql_chain.invoke({'instruction': instruction, 'table_definition': table_definition})
    print('create_sql:', create_sql)

    result = spark.sql(create_sql)

    # この辺りで列順がおかしくなっていないか、要調査
    df = result.toPandas().to_dict(orient="records")

    return df
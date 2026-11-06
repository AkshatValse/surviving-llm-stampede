import sys
import pandas as pd

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 80)
pd.set_option('display.max_colwidth', 40)
pd.set_option('display.max_rows', 200)
df = pd.read_csv(sys.argv[1], dtype=str, keep_default_na=False)
df['run'] = df['run_dir'].str.replace('/', '\\').str.split('\\').str[-1]
print(df.drop(columns=['run_dir']).set_index('run').T.to_string())

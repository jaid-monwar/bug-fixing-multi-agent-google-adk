import json

import pandas as pd

file_path = "SWE-bench_Lite/data/test-00000-of-00001.parquet"

try:
    df = pd.read_parquet(file_path)
    print("File loaded successfully!")
except Exception as e:
    print(f"Error loading file: {e}")
    df = None

if df is not None and not df.empty:
    print("\nDisplaying the first row of the data:")
    print(df.iloc[0].to_string())
elif df is not None and df.empty:
    print("The DataFrame is empty.")
else:
    print("DataFrame could not be loaded, so cannot display any data.")

if df is not None and not df.empty:
    print("\nBasic DataFrame info:")
    df.info()
    print("\nFirst 5 rows:")
    print(df.head())


if df is not None and not df.empty:
    instance_id_to_find = "django__django-15061"
    matching_row = df[df["instance_id"] == instance_id_to_find]

    if not matching_row.empty:
        row_series = matching_row.iloc[0]

        row_dict = row_series.to_dict()

        output_json_path = "bug_fixer_agent/data.json"

        try:
            with open(output_json_path, "w") as json_file:
                json.dump(row_dict, json_file, indent=4)
            print(
                f"\nSuccessfully saved data for instance_id '{instance_id_to_find}' to: {output_json_path}"
            )
        except Exception as e:
            print(f"\nError saving data to JSON: {e}")
    else:
        print(f"\nNo row found with instance_id: {instance_id_to_find}")
elif df is not None and df.empty:
    print("\nDataFrame is empty. Nothing to save to JSON.")
else:
    print("\nDataFrame not loaded. Cannot save to JSON.")

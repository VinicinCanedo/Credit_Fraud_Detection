from datetime import datetime
import os

import fastavro
import numpy as np
import pandas as pd


def inject_nulls(df, columns, ratio=0.05):
    """Sets a portion of values in specified columns to None/NaN."""
    n_rows = len(df)
    n_nulls = int(n_rows * ratio)
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype(object)
            indices = np.random.choice(df.index, n_nulls, replace=False)
            df.loc[indices, col] = None
    return df


def inject_duplicates(df, ratio=0.02):
    """Duplicates a random portion of rows."""
    n_rows = len(df)
    n_dupes = int(n_rows * ratio)
    indices = np.random.choice(df.index, n_dupes, replace=False)
    duplicates = df.loc[indices].copy()
    return pd.concat([df, duplicates], ignore_index=True)


def mess_string(value):
    if pd.isna(value):
        return value
    if np.random.rand() < 0.1:
        return str(value).replace('a', '@').replace('e', '3').replace('i', '1')
    return value


def save_avro(df, folder_name, base_path):
    print(f"   Attempting to save Avro: {folder_name}...")
    try:
        df_export = df.replace({np.nan: None})
        records = df_export.to_dict('records')

        schema = {
            'type': 'record',
            'name': folder_name,
            'fields': []
        }

        for col, dtype in df.dtypes.items():
            avro_type = ['null', 'string']
            if pd.api.types.is_integer_dtype(dtype):
                avro_type = ['null', 'long']
            elif pd.api.types.is_float_dtype(dtype):
                avro_type = ['null', 'double']
            elif pd.api.types.is_bool_dtype(dtype):
                avro_type = ['null', 'boolean']

            schema['fields'].append({'name': col, 'type': avro_type})

        out_dir = f"{base_path}/{folder_name}"
        os.makedirs(out_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        out_file = f"{out_dir}/data_{timestamp}.avro"

        with open(out_file, 'wb') as handle:
            fastavro.writer(handle, schema, records)

        print(f"      Success: {out_file}")
    except Exception as exc:
        print(f"      ERROR saving {folder_name}: {exc}")
        print('      Skipping this file and continuing...')


def save_json(df, folder_name, base_path):
    out_dir = f"{base_path}/{folder_name}"
    os.makedirs(out_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    out_file = f"{out_dir}/data_{timestamp}.json"

    print(f"   Saving JSON: {out_file}")
    df.to_json(out_file, orient='records', lines=True)

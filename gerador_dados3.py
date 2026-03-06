import pandas as pd
import numpy as np
from faker import Faker
import random
import uuid
from datetime import datetime, timedelta
import fastavro
import os
import json

# --- CONFIGURATION ---
NUM_RECORDS = 1000000  # 1 million records
FRAUD_RATIO = 0.05
SEED = 42

print(f"🔄 Starting Data Ingestion Simulation (Streaming Simulation)...")
print("🎯 Objective: Exemplify First-party Fraud, Corporate Fraud and Traditional Fraud.")
print("🚫 Rules: JSON Formats (Cust/Merch) and AVRO (Others).")

np.random.seed(SEED)
random.seed(SEED)
fake = Faker('pt_BR')

# --- 1. ID PREPARATION (REFERENTIAL INTEGRITY) ---
num_customers = 5000
num_merchants = 500

# Indices to link ends
cust_indices = np.random.randint(0, num_customers, NUM_RECORDS)
# merch_indices will be adjusted later for Corporate Fraud

# Key ID Generator
account_ids_pool = [str(uuid.uuid4()) for _ in range(num_customers)]
card_ids_pool = [str(uuid.uuid4()) for _ in range(num_customers)] # Simplification: 1 card per account
merchant_ids_pool = [str(uuid.uuid4()) for _ in range(num_merchants)]
txn_uuids = [str(uuid.uuid4()) for _ in range(NUM_RECORDS)]

# ==============================================================================
# FRAUD SCENARIO DEFINITION
# ==============================================================================
print("🕵️ Defining fraud scenarios...")

# Total fraud
n_total_fraud = int(NUM_RECORDS * FRAUD_RATIO)
indices_fraud = np.random.choice(NUM_RECORDS, size=n_total_fraud, replace=False)

# Split frauds into types
n_auto = int(n_total_fraud * 0.30)  # 30% First-party fraud
n_corp = int(n_total_fraud * 0.30)  # 30% Corporate fraud
n_tradi = n_total_fraud - n_auto - n_corp # 40% Traditional fraud

# Specific indices
idx_auto = indices_fraud[:n_auto]
idx_corp = indices_fraud[n_auto:n_auto+n_corp]
idx_tradi = indices_fraud[n_auto+n_corp:]

# Label (Optional, for internal control only)
labels = np.zeros(NUM_RECORDS, dtype=int)
labels[indices_fraud] = 1

fraud_type = np.array(['LEGIT'] * NUM_RECORDS, dtype='object')
fraud_type[idx_auto] = 'AUTOFRAUD'
fraud_type[idx_corp] = 'CORPORATE'
fraud_type[idx_tradi] = 'TRADITIONAL'

# ==============================================================================
# TOPIC 1: TRANSACTION_EVENTS
# ==============================================================================
print("📡 Generating transaction.events...")
base_date = np.datetime64('today') - np.timedelta64(90, 'D')
time_offsets = np.random.randint(0, 90*24*3600, NUM_RECORDS)
timestamps = pd.to_datetime(base_date + time_offsets.astype('timedelta64[s]'))

df_trans = pd.DataFrame()
df_trans['txn_id'] = txn_uuids
df_trans['txn_timestamp'] = timestamps
df_trans['txn_amount'] = np.random.lognormal(mean=3.5, sigma=1.0, size=NUM_RECORDS).round(2)
df_trans['txn_currency'] = 'BRL'
df_trans['txn_type'] = np.random.choice(['CREDIT', 'DEBIT'], NUM_RECORDS, p=[0.7, 0.3])
df_trans['txn_entry_mode'] = np.random.choice(['CHIP', 'CONTACTLESS', 'MAGSTRIPE', 'MANUAL'], NUM_RECORDS)
df_trans['txn_status'] = 'APPROVED' # Default

# Traditional Fraud Adjustment (Leak/Attack) -> Often status is Approved initially, or Denied
df_trans.loc[idx_tradi, 'txn_amount'] = np.random.choice([1000.0, 4500.0, 9000.0], size=len(idx_tradi))
df_trans.loc[idx_tradi, 'txn_entry_mode'] = 'MANUAL' # CNP (Card Not Present)

# First-party Fraud Adjustment (Legitimate transaction that will be contested)
# High value, made by the user themselves
df_trans.loc[idx_auto, 'txn_amount'] = np.random.uniform(2000, 5000, size=len(idx_auto)).round(2)
df_trans.loc[idx_auto, 'txn_status'] = np.random.choice(['APPROVED', 'CHARGEBACK'], len(idx_auto), p=[0.7, 0.3])
# First-party fraud tends to be installments?
df_trans.loc[idx_auto, 'installments_count'] = np.random.choice([10, 12], size=len(idx_auto))

# Corporate Fraud Adjustment (Collusion/No Backing)
# Round values, credit transfer
df_trans.loc[idx_corp, 'txn_amount'] = np.random.choice([1000.0, 2000.0, 3000.0, 5000.0, 10000.0], size=len(idx_corp))
df_trans.loc[idx_corp, 'installments_count'] = 1
df_trans.loc[idx_corp, 'txn_type'] = 'CREDIT'

# Foreign Keys
df_trans['card_id'] = [card_ids_pool[i] for i in cust_indices]

# Merchant Logic (Corporate Fraud Cluster)
# Select 3 bad merchants
bad_merchants_indices = np.random.choice(range(num_merchants), 3, replace=False)
merch_indices = np.random.randint(0, num_merchants, NUM_RECORDS)
# Force fraudulent merchants in corporate frauds
df_trans['merchant_id'] = [merchant_ids_pool[i] for i in merch_indices]
df_trans.loc[idx_corp, 'merchant_id'] = np.random.choice([merchant_ids_pool[i] for i in bad_merchants_indices], len(idx_corp))

# Additional fields
df_trans['installments_count'] = df_trans.get('installments_count', np.random.choice([1, 2, 3, 6], NUM_RECORDS))
df_trans['is_recurring'] = np.random.choice([True, False], NUM_RECORDS, p=[0.1, 0.9])
df_trans['kafka_topic'] = 'transaction.events'
df_trans['ingestion_timestamp'] = (timestamps + pd.to_timedelta(np.random.randint(100, 5000, NUM_RECORDS), unit='ms')).astype(str)
df_trans['txn_timestamp'] = df_trans['txn_timestamp'].astype(str) # Serialize for Avro/Json

# ==============================================================================
# CUSTOMER PROFILES (JSON - Dict)
# ==============================================================================
print("📡 Generating customer.profiles...")
df_cust = pd.DataFrame()
df_cust['card_id'] = card_ids_pool
df_cust['account_id'] = account_ids_pool
df_cust['customer_id'] = [str(uuid.uuid4()) for _ in range(num_customers)]
df_cust['card_bin'] = np.random.choice(['454545', '550100', '491600'], num_customers)
df_cust['card_type'] = np.random.choice(['Gold', 'Platinum', 'Black'], num_customers)
df_cust['customer_zip_code'] = [fake.postcode() for _ in range(num_customers)]
# Customer -> Default Device Mapping
cust_default_device = [str(uuid.uuid4()) for _ in range(num_customers)]

# All Brazilian States
br_states = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 
    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
]
cust_default_region = np.random.choice(br_states, num_customers)

# --- NEW: Customer Home Coordinates (Brazil Bounding Box approx) ---
# Lat: -33 to 5, Long: -74 to -34
df_cust['billing_latitude'] = np.random.uniform(-33.0, 5.0, num_customers)
df_cust['billing_longitude'] = np.random.uniform(-74.0, -34.0, num_customers)

# ==============================================================================
# MERCHANT REGISTRY (JSON - Dict)
# ==============================================================================
print("📡 Generating merchant.registry...")
df_merch = pd.DataFrame()
df_merch['merchant_id'] = merchant_ids_pool
df_merch['merchant_name'] = [fake.company() for _ in range(num_merchants)]
df_merch['mcc_code'] = np.random.choice(['5411', '5812', '5541', '5732', '7995', '5999'], num_merchants)
df_merch['merchant_city'] = [fake.city() for _ in range(num_merchants)]

# --- NEW: Merchant Coordinates ---
df_merch['merchant_latitude'] = np.random.uniform(-33.0, 5.0, num_merchants)
df_merch['merchant_longitude'] = np.random.uniform(-74.0, -34.0, num_merchants)

# ==============================================================================
# DEVICE SIGNALS
# ==============================================================================
print("📡 Generating device.signals...")
df_device = pd.DataFrame()
df_device['txn_id'] = txn_uuids
df_device['ip_address'] = [fake.ipv4() for _ in range(NUM_RECORDS)]

# Device telemetry fields commonly collected by mobile apps
device_os_choices = np.random.choice(['Android', 'iOS'], NUM_RECORDS, p=[0.65, 0.35])
android_models = np.array(['Samsung Galaxy S23', 'Samsung Galaxy A54', 'Xiaomi 13', 'Motorola Edge 40'])
ios_models = np.array(['iPhone 13', 'iPhone 14', 'iPhone 15', 'iPhone SE'])

df_device['device_os'] = device_os_choices
df_device['device_model'] = np.where(
    device_os_choices == 'Android',
    np.random.choice(android_models, NUM_RECORDS),
    np.random.choice(ios_models, NUM_RECORDS)
)
df_device['device_browser'] = np.random.choice(['Chrome Mobile', 'Safari Mobile', 'Firefox Mobile', 'Edge Mobile'], NUM_RECORDS)
df_device['device_language'] = np.random.choice(['pt-BR', 'en-US', 'es-ES'], NUM_RECORDS, p=[0.85, 0.10, 0.05])
df_device['app_version'] = np.where(
    device_os_choices == 'Android',
    np.random.choice(['6.1.0', '6.1.1', '6.2.0', '6.2.1'], NUM_RECORDS),
    np.random.choice(['5.9.0', '5.9.1', '6.0.0', '6.0.1'], NUM_RECORDS)
)

# --- Geo-Coordinates & Region Logic ---

# 1. Define Coordinates Dictionaries (Approx Centers)
brazil_states_coords = {
    'AC': (-9.0, -70.0), 'AL': (-9.5, -36.5), 'AP': (1.0, -51.0), 'AM': (-3.0, -60.0),
    'BA': (-12.0, -41.0), 'CE': (-5.0, -39.0), 'DF': (-15.8, -47.9), 'ES': (-19.0, -40.0),
    'GO': (-16.0, -50.0), 'MA': (-5.0, -45.0), 'MT': (-13.0, -56.0), 'MS': (-20.0, -54.0),
    'MG': (-18.0, -44.0), 'PA': (-4.0, -53.0), 'PB': (-7.0, -36.0), 'PR': (-24.0, -51.0),
    'PE': (-8.0, -37.0), 'PI': (-7.0, -42.0), 'RJ': (-22.9, -43.2), 'RN': (-5.0, -36.0),
    'RS': (-30.0, -53.0), 'RO': (-11.0, -63.0), 'RR': (2.0, -61.0), 'SC': (-27.0, -50.0),
    'SP': (-23.5, -46.6), 'SE': (-10.5, -37.0), 'TO': (-10.0, -48.0)
}

foreign_regions_coords = {
    # Russia
    'RU-MOW': (55.7, 37.6), 'RU-SPE': (59.9, 30.3), 'RU-NVS': (55.0, 82.9), 'RU-SVE': (56.8, 60.6),
    # China
    'CN-BJ': (39.9, 116.4), 'CN-SH': (31.2, 121.4), 'CN-GD': (23.1, 113.2), 'CN-ZJ': (30.2, 120.1),
    # Nigeria
    'NG-LA': (6.5, 3.3), 'NG-FC': (9.0, 7.5), 'NG-KN': (12.0, 8.5), 'NG-RI': (4.8, 7.0),
    # USA
    'US-CA': (36.7, -119.4), 'US-NY': (40.7, -74.0), 'US-TX': (31.0, -97.5), 'US-FL': (27.6, -81.5)
}

foreign_keys_list = list(foreign_regions_coords.keys())
states_keys_list = list(brazil_states_coords.keys())

# 2. Assign Initial Regions (Default: Customer Home Region)
# Retrieve original customer regions
cust_home_regions = [cust_default_region[i] for i in cust_indices]
assigned_regions = np.array(cust_home_regions, dtype=object)

# 3. Handle Devices
assigned_devices = [cust_default_device[i] for i in cust_indices]
df_device['device_id'] = assigned_devices

# 4. SCENARIO GENERATION (Region & Device Changes)

# A. LEGITIMATE TRAVEL (Legit transactions in other BR states or Foreign)
# 5% of legit transactions happen outside home region
legit_indices = np.setdiff1d(np.arange(NUM_RECORDS), indices_fraud)
n_travel = int(len(legit_indices) * 0.05)
idx_travel = np.random.choice(legit_indices, size=n_travel, replace=False)

# Split travel: 80% Domestic, 20% International
n_travel_int = int(n_travel * 0.2)
idx_travel_int = idx_travel[:n_travel_int]
idx_travel_dom = idx_travel[n_travel_int:]

assigned_regions[idx_travel_int] = np.random.choice(foreign_keys_list, size=len(idx_travel_int))
assigned_regions[idx_travel_dom] = np.random.choice(states_keys_list, size=len(idx_travel_dom))

# B. TRADITIONAL FRAUD (Attacker location)
# New Device ID for Traditional Fraud
new_devices = [str(uuid.uuid4()) for _ in range(len(idx_tradi))]
df_device.loc[idx_tradi, 'device_id'] = new_devices

# Fraud Location: 60% Foreign Attack, 40% Domestic Attack (Different State)
n_tradi_foreign = int(len(idx_tradi) * 0.60)
idx_tradi_foreign = idx_tradi[:n_tradi_foreign]
idx_tradi_domestic = idx_tradi[n_tradi_foreign:]

assigned_regions[idx_tradi_foreign] = np.random.choice(foreign_keys_list, size=len(idx_tradi_foreign))
assigned_regions[idx_tradi_domestic] = np.random.choice(states_keys_list, size=len(idx_tradi_domestic))

# C. FIRST-PARTY FRAUD (User location)
# Mostly home, but simulate some "travel" claims (20% foreign)
idx_auto_location_change = np.random.choice(idx_auto, int(len(idx_auto)*0.2), replace=False)
assigned_regions[idx_auto_location_change] = np.random.choice(foreign_keys_list, size=len(idx_auto_location_change))

# 5. GENERATE COORDINATES BASED ON REGION
print("   - Calculating coordinates based on regions...")

# Vectorized approach or list comprehension? List comprehension is safer for dict lookups
final_lats = np.zeros(NUM_RECORDS)
final_longs = np.zeros(NUM_RECORDS)

# Helper for noise
def get_coords(region_code):
    if region_code in brazil_states_coords:
        base = brazil_states_coords[region_code]
        # Spread within state (approx 2-3 degrees)
        return base[0] + np.random.uniform(-1.5, 1.5), base[1] + np.random.uniform(-1.5, 1.5)
    elif region_code in foreign_regions_coords:
        base = foreign_regions_coords[region_code]
        # Spread within city/region (approx 0.5 degrees)
        return base[0] + np.random.uniform(-0.5, 0.5), base[1] + np.random.uniform(-0.5, 0.5)
    else:
        # Fallback (Sao Paulo)
        return -23.5, -46.6

# Generate all coordinates
# Note: This loop might be slow for 1M records. Optimization:
# Create an array of base lats/longs then add noise.

# Pre-map all region bases
all_regions = list(brazil_states_coords.keys()) + list(foreign_regions_coords.keys())
lat_map = {k: v[0] for k, v in {**brazil_states_coords, **foreign_regions_coords}.items()}
lon_map = {k: v[1] for k, v in {**brazil_states_coords, **foreign_regions_coords}.items()}

# Map to arrays
base_lats = pd.Series(assigned_regions).map(lat_map).fillna(-23.5).values
base_longs = pd.Series(assigned_regions).map(lon_map).fillna(-46.6).values

# Add noise (States get more noise to simulate dispersion, Cities/Foreign get less)
# Let's simplify and give everyone 1.5 degree noise for coverage
final_lats = base_lats + np.random.uniform(-1.0, 1.0, NUM_RECORDS)
final_longs = base_longs + np.random.uniform(-1.0, 1.0, NUM_RECORDS)

df_device['device_latitude'] = final_lats
df_device['device_longitude'] = final_longs

df_device.loc[idx_tradi, 'device_model'] = 'Generic Emulator'

# Build mobile-style location payload in ip_region instead of using only region code
location_accuracy = np.round(np.random.uniform(3.0, 60.0, NUM_RECORDS), 2)
altitude_values = np.round(np.random.normal(loc=760.0, scale=180.0, size=NUM_RECORDS), 2)
altitude_available = np.random.rand(NUM_RECORDS) < 0.8
location_timestamps = df_trans['ingestion_timestamp'].tolist()

location_payloads = [
    json.dumps(
        {
            'latitude': float(lat),
            'longitude': float(lon),
            'accuracy_meters': float(acc),
            'altitude_meters': (float(alt) if has_alt else None),
            'timestamp': ts,
            'region_code': str(region)
        },
        ensure_ascii=True
    )
    for lat, lon, acc, alt, has_alt, ts, region in zip(
        final_lats,
        final_longs,
        location_accuracy,
        altitude_values,
        altitude_available,
        location_timestamps,
        assigned_regions
    )
]

df_device['ip_region'] = location_payloads

# Construct user-agent string from generated telemetry
df_device['user_agent_string'] = [
    f"Mozilla/5.0 ({'Linux; Android 13' if os_name == 'Android' else 'iPhone; CPU iPhone OS 17_0 like Mac OS X'}) "
    f"AppleWebKit/537.36 (KHTML, like Gecko) {browser.replace(' Mobile', '')}/120.0 Mobile AuroraPay/{app_ver}"
    for os_name, browser, app_ver in zip(df_device['device_os'], df_device['device_browser'], df_device['app_version'])
]

# Keep region code explicit for easier filtering/analytics
df_device['ip_region_code'] = assigned_regions

df_device['kafka_topic'] = 'device.signals'
df_device['ingestion_timestamp'] = df_trans['ingestion_timestamp']

# ==============================================================================
# SECURITY LOGS
# ==============================================================================
print("📡 Generating security.logs...")
df_auth = pd.DataFrame()
df_auth['txn_id'] = txn_uuids
df_auth['password_failures_session'] = 0
df_auth['last_pin_change_days'] = np.random.randint(30, 800, NUM_RECORDS)

# Traditional: Brute force attack or stolen credential recently changed
df_auth.loc[idx_tradi, 'password_failures_session'] = np.random.randint(3, 10, len(idx_tradi))
df_auth.loc[idx_tradi, 'last_pin_change_days'] = np.random.randint(0, 2, len(idx_tradi))

df_auth['kafka_topic'] = 'security.logs'
df_auth['ingestion_timestamp'] = df_trans['ingestion_timestamp']

# ==============================================================================
# 5. DATA DIRTYING (Simulating Real World Quality Issues)
# ==============================================================================
print("🌪️ Injecting Data Quality Issues (Dirt)...")

def inject_nulls(df, columns, ratio=0.05):
    """Sets a portion of values in specified columns to None/NaN"""
    n_rows = len(df)
    n_nulls = int(n_rows * ratio)
    for col in columns:
        if col in df.columns:
            # Avoid overwriting existing NaNs if possible, but simple choice is fine
            # We must use iloc or loc carefully. converting to object if needed for None
            df[col] = df[col].astype(object)
            indices = np.random.choice(df.index, n_nulls, replace=False) 
            df.loc[indices, col] = None
    return df

def inject_duplicates(df, ratio=0.02):
    """Duplicates a random portion of rows"""
    n_rows = len(df)
    n_dupes = int(n_rows * ratio)
    indices = np.random.choice(df.index, n_dupes, replace=False)
    duplicates = df.loc[indices].copy()
    return pd.concat([df, duplicates], ignore_index=True)

# 1. Duplicates
print("   - Creating duplicates in Transactions and Customers...")
df_trans = inject_duplicates(df_trans, ratio=0.03) # 3% duplicates
df_cust = inject_duplicates(df_cust, ratio=0.01)   # 1% duplicates

# 2. Missing Values (Nulls)
print("   - Inserting Nulls/NaNs...")
df_trans = inject_nulls(df_trans, ['txn_entry_mode', 'merchant_id'], ratio=0.08)
df_cust = inject_nulls(df_cust, ['customer_zip_code', 'card_type'], ratio=0.10)
df_merch = inject_nulls(df_merch, ['merchant_city', 'mcc_code'], ratio=0.05)

# 3. Inconsistencies & Errors
print("   - Creating inconsistencies...")

# A. Negative Values (Domain Error)
bad_amount_idx = np.random.choice(df_trans.index, size=int(len(df_trans)*0.005), replace=False) # 0.5%
df_trans.loc[bad_amount_idx, 'txn_amount'] = df_trans.loc[bad_amount_idx, 'txn_amount'] * -1

# B. Crazy Dates (Future/Past anomalies) - modifying string timestamp for raw ingestion simulation
bad_date_idx = np.random.choice(df_trans.index, size=15, replace=False)
df_trans.loc[bad_date_idx, 'txn_timestamp'] = "2099-12-31 23:59:59" # Future date

# C. String Noise (Typos / Whitespace)
# " MANUAL" instead of "MANUAL"
manual_idx = df_trans[df_trans['txn_entry_mode'] == 'MANUAL'].index
if len(manual_idx) > 0:
    messy_idx = np.random.choice(manual_idx, size=int(len(manual_idx)*0.1))
    df_trans.loc[messy_idx, 'txn_entry_mode'] = " MANUAL " # Trailing spaces
    
# Typos in Merchant City
city_idx = np.random.choice(df_merch.index, size=int(len(df_merch)*0.1))
df_merch.loc[city_idx, 'merchant_city'] = df_merch.loc[city_idx, 'merchant_city'].astype(str) + "_???"

# ==============================================================================
# 6. CHAOS ENGINEERING (DATA QUALITY ISSUES)
# ==============================================================================
print("💥 Injecting Data Quality Issues (Naming, Formats, Ambiguity)...")

# 1. Naming Conventions (Inconsistent Column Names)
df_cust = df_cust.rename(columns={'card_id': 'card_number'})
df_merch = df_merch.rename(columns={'merchant_id': 'merch_code'})
df_device = df_device.rename(columns={'txn_id': 'transaction_ref'})
df_auth = df_auth.rename(columns={'txn_id': 'trans_id'})

# 2. Data Formats (Typos, Mixed Languages)
# Mix languages in 'txn_type' (Credit vs Crédito)
df_trans['txn_type'] = df_trans['txn_type'].astype(object)
mask_pt = np.random.rand(len(df_trans)) < 0.3
df_trans.loc[mask_pt, 'txn_type'] = df_trans.loc[mask_pt, 'txn_type'].replace({'CREDIT': 'Crédito', 'DEBIT': 'Débito'})

# Typos/Case mismatch in 'txn_status'
mask_typo = np.random.rand(len(df_trans)) < 0.1
df_trans.loc[mask_typo, 'txn_status'] = 'approved' # lowercase
mask_typo2 = np.random.rand(len(df_trans)) < 0.05
df_trans.loc[mask_typo2, 'txn_status'] = 'Aprovado' # Portuguese

# Weird characters in strings (Merchant City)
def mess_string(s):
    if pd.isna(s): return s
    if random.random() < 0.1:
        return str(s).replace('a', '@').replace('e', '3').replace('i', '1')
    return s

df_merch['merchant_city'] = df_merch['merchant_city'].apply(mess_string)

# 3. Ambiguous Attributes (Concatenated fields)
# customer_profiles: Combine 'card_type', 'card_bin' -> 'client_details'
df_cust['client_details'] = df_cust.apply(
    lambda row: f"Type:{row['card_type']}|BIN:{row['card_bin']}", axis=1
)
df_cust.drop(columns=['card_type', 'card_bin'], inplace=True)

# transaction_events: Combine 'txn_entry_mode' -> 'pos_entry_details'
df_trans['pos_entry_details'] = df_trans.apply(
    lambda row: json.dumps({'mode': row['txn_entry_mode'], 'type': row['txn_type']}), axis=1
)
df_trans.drop(columns=['txn_entry_mode'], inplace=True)

# ==============================================================================
# EXPORT
# ==============================================================================
base_path = "aurorapay_transactions/"
os.makedirs(base_path, exist_ok=True)

def save_avro(df, folder_name):
    print(f"   💾 Attempting to save Avro: {folder_name}...")
    try:
        # Convert NaN to None for compatible Avro writing
        # Using replace is safer than where for mixed types
        df_export = df.replace({np.nan: None})
        
        records = df_export.to_dict('records')
        
        schema = {
            "type": "record",
            "name": folder_name,
            "fields": []
        }
        
        for col, dtype in df.dtypes.items():
            # Fallback to string for complex types
            avro_type = ["null", "string"] # Default nullable string
            if pd.api.types.is_integer_dtype(dtype):
                avro_type = ["null", "long"]
            elif pd.api.types.is_float_dtype(dtype):
                 # Ensure we handle the case where integers became floats due to NaNs
                avro_type = ["null", "double"]
            elif pd.api.types.is_bool_dtype(dtype):
                 avro_type = ["null", "boolean"]
                 
            schema["fields"].append({"name": col, "type": avro_type})

        out_dir = f"{base_path}/{folder_name}"
        os.makedirs(out_dir, exist_ok=True)

        # Unique file name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_file = f"{out_dir}/data_{timestamp}.avro"
        
        with open(out_file, 'wb') as f:
            fastavro.writer(f, schema, records)
        print(f"      ✅ Success: {out_file}")

    except Exception as e:
        print(f"      ❌ ERROR saving {folder_name}: {e}")
        print("      ⚠️ Skipping this file and continuing...")

def save_json(df, folder_name):
    out_dir = f"{base_path}/{folder_name}"
    os.makedirs(out_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_file = f"{out_dir}/data_{timestamp}.json"
    
    print(f"   💾 Saving JSON: {out_file}")
    df.to_json(out_file, orient='records', lines=True) # Line-delimited JSON usually best for big data

# 1. JSON Exports
save_json(df_cust, "customer_profiles")
save_json(df_merch, "merchant_registry")

# 2. Avro Exports
save_avro(df_trans, "transaction_events")
save_avro(df_device, "device_signals")
save_avro(df_auth, "security_logs")

print("\n✅ Generation concluded!")

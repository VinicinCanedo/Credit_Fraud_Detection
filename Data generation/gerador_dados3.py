import pandas as pd
import numpy as np
from faker import Faker
import random
import uuid
from datetime import datetime, timedelta
import json

from modules.data_utils import inject_nulls, inject_duplicates, mess_string, save_avro, save_json
from modules.merchant_registry import generate_merchant_registry

# --- CONFIGURATION ---
NUM_RECORDS = 1000000  # 1 million records
FRAUD_RATIO = 0.05
SEED = 42
CARD_TESTING_SHARE = 0.20
LOST_STOLEN_SHARE = 0.35

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

# Traditional fraud subtypes are useful for downstream feature engineering
n_card_testing = int(len(idx_tradi) * CARD_TESTING_SHARE)
n_lost_stolen = int(len(idx_tradi) * LOST_STOLEN_SHARE)

idx_tradi_card_testing = idx_tradi[:n_card_testing]
idx_tradi_lost_stolen = idx_tradi[n_card_testing:n_card_testing + n_lost_stolen]
idx_tradi_behavioral = idx_tradi[n_card_testing + n_lost_stolen:]

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
# Customer-specific spending profile to avoid globally uniform behavior
customer_avg_ticket = np.random.lognormal(mean=3.35, sigma=0.55, size=num_customers)
customer_std_ticket = np.maximum(customer_avg_ticket * np.random.uniform(0.12, 0.55, num_customers), 1.0)
sampled_amounts = np.random.normal(
    loc=customer_avg_ticket[cust_indices],
    scale=customer_std_ticket[cust_indices]
)
df_trans['txn_amount'] = np.round(np.clip(sampled_amounts, 1.20, 12000.0), 2)
df_trans['txn_currency'] = 'BRL'
# Internal-only transaction type used to build pos_entry_details later
df_trans['_txn_type_internal'] = np.random.choice(['CREDIT', 'DEBIT'], NUM_RECORDS, p=[0.7, 0.3])
df_trans['txn_entry_mode'] = np.random.choice(['CHIP', 'CONTACTLESS', 'MAGSTRIPE', 'MANUAL'], NUM_RECORDS)
df_trans['txn_status'] = 'APPROVED' # Default

# Traditional fraud adjustments
# 1) Card testing: many low-value attempts and a subset of larger follow-up charges
df_trans.loc[idx_tradi_card_testing, 'txn_amount'] = np.round(
    np.random.uniform(1.10, 19.90, size=len(idx_tradi_card_testing)),
    2
)
df_trans.loc[idx_tradi_card_testing, '_txn_type_internal'] = 'DEBIT'
df_trans.loc[idx_tradi_card_testing, 'txn_entry_mode'] = np.random.choice(
    ['MANUAL', 'MAGSTRIPE'],
    size=len(idx_tradi_card_testing),
    p=[0.85, 0.15]
)
df_trans.loc[idx_tradi_card_testing, 'txn_status'] = np.random.choice(
    ['APPROVED', 'DECLINED'],
    size=len(idx_tradi_card_testing),
    p=[0.80, 0.20]
)

n_big_after_test = max(1, int(len(idx_tradi_card_testing) * 0.14))
idx_big_after_test = np.random.choice(idx_tradi_card_testing, size=n_big_after_test, replace=False)
df_trans.loc[idx_big_after_test, 'txn_amount'] = np.round(
    np.random.uniform(1200.0, 3800.0, size=n_big_after_test),
    2
)
df_trans.loc[idx_big_after_test, '_txn_type_internal'] = 'CREDIT'
df_trans.loc[idx_big_after_test, 'txn_entry_mode'] = 'MANUAL'
df_trans.loc[idx_big_after_test, 'txn_status'] = np.random.choice(
    ['APPROVED', 'CHARGEBACK'],
    size=n_big_after_test,
    p=[0.65, 0.35]
)

# 2) Lost/stolen card: moderate-to-high spend burst, usually local and with chargeback later
df_trans.loc[idx_tradi_lost_stolen, 'txn_amount'] = np.round(
    np.random.lognormal(mean=5.2, sigma=0.65, size=len(idx_tradi_lost_stolen)),
    2
)
df_trans.loc[idx_tradi_lost_stolen, 'txn_entry_mode'] = np.random.choice(
    ['CHIP', 'CONTACTLESS', 'MAGSTRIPE', 'MANUAL'],
    size=len(idx_tradi_lost_stolen),
    p=[0.30, 0.35, 0.20, 0.15]
)
df_trans.loc[idx_tradi_lost_stolen, 'txn_status'] = np.random.choice(
    ['APPROVED', 'CHARGEBACK'],
    size=len(idx_tradi_lost_stolen),
    p=[0.72, 0.28]
)

# 3) Behavioral/"too perfect" fraud: very rounded values and atypical consistency
rounded_values = np.array([49.90, 79.90, 99.90, 199.90, 299.90, 499.90, 999.90])
df_trans.loc[idx_tradi_behavioral, 'txn_amount'] = np.random.choice(
    rounded_values,
    size=len(idx_tradi_behavioral)
)
df_trans.loc[idx_tradi_behavioral, '_txn_type_internal'] = 'CREDIT'
df_trans.loc[idx_tradi_behavioral, 'txn_entry_mode'] = np.random.choice(
    ['CONTACTLESS', 'MANUAL', 'CHIP'],
    size=len(idx_tradi_behavioral),
    p=[0.45, 0.40, 0.15]
)
df_trans.loc[idx_tradi_behavioral, 'txn_status'] = np.random.choice(
    ['APPROVED', 'CHARGEBACK'],
    size=len(idx_tradi_behavioral),
    p=[0.78, 0.22]
)

# First-party Fraud Adjustment (Legitimate transaction that will be contested)
# High value, made by the user themselves
df_trans.loc[idx_auto, 'txn_amount'] = np.random.uniform(1500, 5200, size=len(idx_auto)).round(2)
df_trans.loc[idx_auto, 'txn_status'] = np.random.choice(['APPROVED', 'CHARGEBACK'], len(idx_auto), p=[0.7, 0.3])
# First-party fraud tends to be installments?
df_trans.loc[idx_auto, 'installments_count'] = np.random.choice([10, 12], size=len(idx_auto))

# Corporate Fraud Adjustment (Collusion/No Backing)
# Round values, credit transfer
df_trans.loc[idx_corp, 'txn_amount'] = np.random.choice([1000.0, 2000.0, 3000.0, 5000.0, 10000.0], size=len(idx_corp))
df_trans.loc[idx_corp, 'installments_count'] = 1
df_trans.loc[idx_corp, '_txn_type_internal'] = 'CREDIT'

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
df_cust['customer_zip_code'] = [fake.postcode() for _ in range(num_customers)]

# Card details payload
card_brands = np.random.choice(['Visa', 'Mastercard', 'Elo'], num_customers, p=[0.45, 0.40, 0.15])
card_categories = np.random.choice(['Gold', 'Platinum', 'Black'], num_customers, p=[0.45, 0.35, 0.20])
card_types = np.random.choice(['Débito', 'Crédito'], num_customers, p=[0.35, 0.65])
is_virtual_cards = np.random.choice([True, False], num_customers, p=[0.28, 0.72])
card_security_codes = [f"{np.random.randint(0, 1000):03d}" for _ in range(num_customers)]

issue_dates = [
    datetime.now() - timedelta(days=int(np.random.randint(120, 3650)))
    for _ in range(num_customers)
]
expiration_dates = [
    issue_date + timedelta(days=int(np.random.randint(3 * 365, 6 * 365)))
    for issue_date in issue_dates
]

card_limits = np.round(np.random.uniform(1200.0, 45000.0, num_customers), 2)
available_factors = np.random.uniform(0.08, 0.95, num_customers)
available_limits = np.round(card_limits * available_factors, 2)

df_cust['card_details'] = [
    json.dumps(
        {
            'card_brand': brand,
            'card_category': category,
            'card_type': ctype,
            'is_card_virtual': bool(is_virtual),
            'security_code': sec_code,
            'issue_date': issue_date.strftime('%Y-%m-%d'),
            'expiration_date': exp_date.strftime('%Y-%m-%d'),
            'card_limit': float(limit),
            'available_limit': float(avail_limit)
        },
        ensure_ascii=True
    )
    for brand, category, ctype, is_virtual, sec_code, issue_date, exp_date, limit, avail_limit in zip(
        card_brands,
        card_categories,
        card_types,
        is_virtual_cards,
        card_security_codes,
        issue_dates,
        expiration_dates,
        card_limits,
        available_limits
    )
]

customer_genders = np.random.choice(['F', 'M', 'Nao informado'], num_customers, p=[0.49, 0.49, 0.02])
customer_ages = np.random.randint(18, 89, num_customers)
df_cust['client_details'] = [
    json.dumps(
        {
            'customer_gender': gender,
            'customer_age': int(age)
        },
        ensure_ascii=True
    )
    for gender, age in zip(customer_genders, customer_ages)
]
# Customer -> Default Device Mapping
cust_default_device = [str(uuid.uuid4()) for _ in range(num_customers)]

# All Brazilian States
br_states = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 
    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
]
cust_default_region = np.random.choice(br_states, num_customers)
# ==============================================================================
# MERCHANT REGISTRY (JSON - Dict)
# ==============================================================================
print("📡 Generating merchant.registry...")
df_merch = generate_merchant_registry(merchant_ids_pool, num_merchants, fake)

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
# 4% of legit transactions happen outside home region
legit_indices = np.setdiff1d(np.arange(NUM_RECORDS), indices_fraud)
n_travel = int(len(legit_indices) * 0.04)
idx_travel = np.random.choice(legit_indices, size=n_travel, replace=False)

# Split travel: mostly domestic, some international
n_travel_int = int(n_travel * 0.05)
idx_travel_int = idx_travel[:n_travel_int]
idx_travel_dom = idx_travel[n_travel_int:]

assigned_regions[idx_travel_int] = np.random.choice(foreign_keys_list, size=len(idx_travel_int))
assigned_regions[idx_travel_dom] = np.random.choice(states_keys_list, size=len(idx_travel_dom))

# B. TRADITIONAL FRAUD (Attacker location)
# Only part of fraud uses a new device, to avoid trivial labeling rules
idx_new_device = np.random.choice(idx_tradi, size=int(len(idx_tradi) * 0.55), replace=False)
new_devices = [str(uuid.uuid4()) for _ in range(len(idx_new_device))]
df_device.loc[idx_new_device, 'device_id'] = new_devices

# Fraud Location: mostly domestic; foreign fraud exists but is not dominant
n_tradi_foreign = int(len(idx_tradi) * 0.08)
idx_tradi_foreign = idx_tradi[:n_tradi_foreign]
idx_tradi_domestic = idx_tradi[n_tradi_foreign:]

assigned_regions[idx_tradi_foreign] = np.random.choice(foreign_keys_list, size=len(idx_tradi_foreign))
assigned_regions[idx_tradi_domestic] = np.random.choice(states_keys_list, size=len(idx_tradi_domestic))

# C. FIRST-PARTY FRAUD (User location)
# Mostly home, but simulate some "travel" claims (20% foreign)
idx_auto_location_change = np.random.choice(idx_auto, int(len(idx_auto)*0.2), replace=False)
assigned_regions[idx_auto_location_change] = np.random.choice(foreign_keys_list, size=len(idx_auto_location_change))

# D. CARD TESTING CLUSTERS (same IP across multiple cards)
forced_ips = np.array([''] * NUM_RECORDS, dtype=object)
forced_regions = np.array([''] * NUM_RECORDS, dtype=object)

n_card_test_groups = max(20, int(len(idx_tradi_card_testing) / 180))
card_test_groups = np.array_split(idx_tradi_card_testing, n_card_test_groups)

for grp in card_test_groups:
    if len(grp) == 0:
        continue
    attacker_ip = fake.ipv4_public()
    attacker_region = np.random.choice(states_keys_list)
    forced_ips[grp] = attacker_ip
    forced_regions[grp] = attacker_region

    # Force multiple cards being tested from the same source
    if len(grp) > 3:
        sampled_customers = np.random.choice(num_customers, size=len(grp), replace=True)
        tested_cards = [card_ids_pool[i] for i in sampled_customers]
        df_trans.loc[grp, 'card_id'] = tested_cards
        df_trans.loc[grp, '_txn_type_internal'] = 'DEBIT'

    grp_big = np.intersect1d(grp, idx_big_after_test)
    grp_small = np.setdiff1d(grp, grp_big)
    if len(grp_small) > 0:
        burst_start = pd.Timestamp.now() - pd.to_timedelta(np.random.randint(2, 85), unit='D')
        small_offsets = np.sort(np.random.randint(0, 20 * 60, size=len(grp_small)))
        burst_ts = burst_start + pd.to_timedelta(small_offsets, unit='s')
        df_trans.loc[grp_small, 'txn_timestamp'] = pd.Series(burst_ts).dt.strftime('%Y-%m-%d %H:%M:%S').to_numpy()

    if len(grp_big) > 0:
        big_offsets = np.sort(np.random.randint(25 * 60, 3 * 3600, size=len(grp_big)))
        reference_ts = pd.Timestamp.now() - pd.to_timedelta(np.random.randint(1, 70), unit='D')
        big_ts = reference_ts + pd.to_timedelta(big_offsets, unit='s')
        df_trans.loc[grp_big, 'txn_timestamp'] = pd.Series(big_ts).dt.strftime('%Y-%m-%d %H:%M:%S').to_numpy()

mask_forced_region = forced_regions != ''
assigned_regions[mask_forced_region] = forced_regions[mask_forced_region]

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

# Fraud can include emulator traces, but not in all cases and not only in fraud
idx_emulator_any = np.random.choice(np.arange(NUM_RECORDS), size=int(NUM_RECORDS * 0.015), replace=False)
df_device.loc[idx_emulator_any, 'device_model'] = np.random.choice(
    ['Android SDK built for x86', 'iPhone Simulator', 'BlueStacks'],
    size=len(idx_emulator_any)
)

# Apply card-testing IP overrides after base generation
mask_forced_ip = forced_ips != ''
df_device.loc[mask_forced_ip, 'ip_address'] = forced_ips[mask_forced_ip]

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
df_auth['security_case_id'] = [str(uuid.uuid4()) for _ in range(NUM_RECORDS)]
df_auth['card_reported_lost_stolen'] = False
df_auth['loss_report_timestamp'] = None
df_auth['loss_report_channel'] = None

# Card testing and takeover: more password failures
df_auth.loc[idx_tradi_card_testing, 'password_failures_session'] = np.random.randint(2, 8, len(idx_tradi_card_testing))
df_auth.loc[idx_tradi_behavioral, 'password_failures_session'] = np.random.randint(1, 5, len(idx_tradi_behavioral))

# Lost/stolen: generally no brute force, but recent PIN change is common in dispute timeline
df_auth.loc[idx_tradi_lost_stolen, 'password_failures_session'] = np.random.randint(0, 3, len(idx_tradi_lost_stolen))
df_auth.loc[idx_tradi_lost_stolen, 'last_pin_change_days'] = np.random.randint(0, 45, len(idx_tradi_lost_stolen))

# Part of lost/stolen cases have formal report before transaction
reported_lost_idx = np.random.choice(
    idx_tradi_lost_stolen,
    size=max(1, int(len(idx_tradi_lost_stolen) * 0.45)),
    replace=False
)

txn_ts_dt = pd.to_datetime(df_trans['txn_timestamp'], errors='coerce')
hours_before = pd.to_timedelta(np.random.randint(1, 96, size=len(reported_lost_idx)), unit='h')
df_auth.loc[reported_lost_idx, 'card_reported_lost_stolen'] = True
df_auth.loc[reported_lost_idx, 'loss_report_timestamp'] = (
    txn_ts_dt.loc[reported_lost_idx] - hours_before
).astype(str)
df_auth.loc[reported_lost_idx, 'loss_report_channel'] = np.random.choice(
    ['APP', 'CALL_CENTER', 'WHATSAPP', 'BRANCH'],
    size=len(reported_lost_idx),
    p=[0.45, 0.30, 0.20, 0.05]
)

# A tiny legitimate background of lost/stolen reports for realism
legit_lost_idx = np.random.choice(legit_indices, size=max(1, int(len(legit_indices) * 0.0008)), replace=False)
df_auth.loc[legit_lost_idx, 'card_reported_lost_stolen'] = True
df_auth.loc[legit_lost_idx, 'loss_report_channel'] = np.random.choice(['APP', 'CALL_CENTER'], size=len(legit_lost_idx))
df_auth.loc[legit_lost_idx, 'loss_report_timestamp'] = (
    txn_ts_dt.loc[legit_lost_idx] - pd.to_timedelta(np.random.randint(1, 72, size=len(legit_lost_idx)), unit='h')
).astype(str)

df_auth['kafka_topic'] = 'security.logs'
df_auth['ingestion_timestamp'] = df_trans['ingestion_timestamp']

# ==============================================================================
# 5. DATA DIRTYING (Simulating Real World Quality Issues)
# ==============================================================================
print("🌪️ Injecting Data Quality Issues (Dirt)...")

# 1. Duplicates
print("   - Creating duplicates in Transactions and Customers...")
df_trans = inject_duplicates(df_trans, ratio=0.03) # 3% duplicates
df_cust = inject_duplicates(df_cust, ratio=0.01)   # 1% duplicates

# 2. Missing Values (Nulls)
print("   - Inserting Nulls/NaNs...")
df_trans = inject_nulls(df_trans, ['txn_entry_mode', 'merchant_id'], ratio=0.08)
df_cust = inject_nulls(df_cust, ['customer_zip_code', 'card_details'], ratio=0.10)
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
df_trans = df_trans.rename(columns={
    'txn_id': 'transaction_ID',
    'merchant_id': 'MERCHANT_ID',
    'card_id': 'cardId'
})

df_cust = df_cust.rename(columns={
    'card_id': 'CardNumber',
    'customer_id': 'customer_id',
    'account_id': 'AccountRef'
})
df_merch = df_merch.rename(columns={
    'merchant_id': 'MERCHANT_ID',
    'merchant_name': 'merchantName',
    'mcc_code': 'MCC'
})
df_device = df_device.rename(columns={
    'txn_id': 'transaction_ID',
    'device_id': 'DeviceID',
    'ip_address': 'IP_ADDRESS'
})
df_auth['SecurityLogsId'] = [str(uuid.uuid4()) for _ in range(len(df_auth))]
df_auth = df_auth.rename(columns={'txn_id': 'transaction_ID'})

# Inconsistent key formatting between systems
trans_key_mess_idx = np.random.choice(df_trans.index, size=int(len(df_trans) * 0.07), replace=False)
df_trans.loc[trans_key_mess_idx, 'transaction_ID'] = df_trans.loc[trans_key_mess_idx, 'transaction_ID'].str.replace('-', '').str.upper()

device_key_mess_idx = np.random.choice(df_device.index, size=int(len(df_device) * 0.09), replace=False)
df_device.loc[device_key_mess_idx, 'transaction_ID'] = df_device.loc[device_key_mess_idx, 'transaction_ID'].str.lower()

merch_key_mess_idx = np.random.choice(df_merch.index, size=int(len(df_merch) * 0.08), replace=False)
df_merch.loc[merch_key_mess_idx, 'MERCHANT_ID'] = '{' + df_merch.loc[merch_key_mess_idx, 'MERCHANT_ID'] + '}'

security_key_mess_idx = np.random.choice(df_auth.index, size=int(len(df_auth) * 0.08), replace=False)
df_auth.loc[security_key_mess_idx, 'transaction_ID'] = df_auth.loc[security_key_mess_idx, 'transaction_ID'].str.replace('-', '')

# 2. Data Formats (Typos, Mixed Languages)
# Mix languages in internal txn type (Credit vs Crédito)
df_trans['_txn_type_internal'] = df_trans['_txn_type_internal'].astype(object)
mask_pt = np.random.rand(len(df_trans)) < 0.3
df_trans.loc[mask_pt, '_txn_type_internal'] = df_trans.loc[mask_pt, '_txn_type_internal'].replace({'CREDIT': 'Crédito', 'DEBIT': 'Débito'})

# Typos/Case mismatch in 'txn_status'
mask_typo = np.random.rand(len(df_trans)) < 0.1
df_trans.loc[mask_typo, 'txn_status'] = 'approved' # lowercase
mask_typo2 = np.random.rand(len(df_trans)) < 0.05
df_trans.loc[mask_typo2, 'txn_status'] = 'Aprovado' # Portuguese

# Mixed date formats in ingestion fields
trans_ts_mess_idx = np.random.choice(df_trans.index, size=int(len(df_trans) * 0.03), replace=False)
df_trans.loc[trans_ts_mess_idx, 'ingestion_timestamp'] = pd.to_datetime(
    df_trans.loc[trans_ts_mess_idx, 'ingestion_timestamp'],
    errors='coerce'
).dt.strftime('%d/%m/%Y %H:%M:%S')

device_ts_mess_idx = np.random.choice(df_device.index, size=int(len(df_device) * 0.03), replace=False)
df_device.loc[device_ts_mess_idx, 'ingestion_timestamp'] = pd.to_datetime(
    df_device.loc[device_ts_mess_idx, 'ingestion_timestamp'],
    errors='coerce'
).dt.strftime('%Y/%m/%d %H:%M:%S')

# Noisy ZIP/postal code formats
zip_mess_idx = np.random.choice(df_cust.index, size=int(len(df_cust) * 0.12), replace=False)
df_cust.loc[zip_mess_idx, 'customer_zip_code'] = df_cust.loc[zip_mess_idx, 'customer_zip_code'].astype(str).str.replace('-', '').str.zfill(8)

# Weird characters in strings (Merchant City)
df_merch['merchant_city'] = df_merch['merchant_city'].apply(mess_string)

# 3. Ambiguous Attributes (Concatenated fields)
# transaction_events: Combine 'txn_entry_mode' -> 'pos_entry_details'
df_trans['pos_entry_details'] = df_trans.apply(
    lambda row: json.dumps({'mode': row['txn_entry_mode'], 'type': row['_txn_type_internal']}), axis=1
)
df_trans.drop(columns=['txn_entry_mode', '_txn_type_internal'], inplace=True)

# ==============================================================================
# EXPORT
# ==============================================================================
base_path = "aurorapay_transactions/"

# 1. JSON Exports
save_json(df_cust, "customer_profiles", base_path)
save_json(df_merch, "merchant_registry", base_path)

# 2. Avro Exports
save_avro(df_trans, "transaction_events", base_path)
save_avro(df_device, "device_signals", base_path)
save_avro(df_auth, "security_logs", base_path)

print("\n✅ Generation concluded!")

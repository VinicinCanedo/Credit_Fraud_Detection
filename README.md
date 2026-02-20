🛡️ Fraud Forensic Analytics Platform
📌 Overview

This project implements a forensic fraud detection analytics platform for a fictional financial institution (AuroraPay).

The main objective is to enable:

Full historical transaction storage

Periodic fraud inference execution

Retroactive data reprocessing

Behavioral pattern analysis over long time windows

Unlike real-time fraud systems, this solution focuses on forensic analysis, regulatory investigations, and historical model evaluation.

🏗 Architecture

The solution follows the Medallion Architecture pattern:

Bronze Layer

Raw data ingestion from multiple operational sources

Schema normalization

Storage as Delta Lake tables

Silver Layer

Data cleansing and standardization

Deduplication

Enrichment across domains

Feature engineering (behavioral, velocity, temporal features)

Gold Layer

Dimensional Data Mart (Star Schema)

Fact table with transactions and fraud scores

Analytical-ready datasets

🔄 Processing Strategy

Batch and micro-batch ingestion

Periodic automated model inference (every 3 weeks)

Configurable historical window (6 months, 2 years, etc.)

Full reprocessing capability with new model versions

🧠 Machine Learning Integration

Fraud risk scoring

Historical inference re-execution

Model version comparison

Behavioral pattern analysis

🛠 Technologies Used
Layer	Technology	Purpose
Storage	Amazon S3	Historical raw data storage
Processing	Databricks	Distributed data processing
Engine	Apache Spark	Transformations and feature engineering
Table Format	Delta Lake	ACID tables and versioning
Language	Python	Data processing and ML logic
Modeling	Dimensional (Star Schema)	Analytical consumption
ML Pipeline	Databricks ML / Custom	Fraud inference execution
🎯 Project Goals

Provide forensic fraud analytics

Enable full historical reprocessing

Support regulatory investigations

Ensure data governance and reproducibility

Maintain scalable and modular architecture

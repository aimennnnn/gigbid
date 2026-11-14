"""Catalogue of freelance project types used to generate ALL synthetic data.

Everything built from this file is synthetic (see docs/DATA_CARD.md). Each line is:
slug | project title | named skills | how a client would say it (no tool names) |
measured result | base price in USD | libraries that only show up in code
"""
from __future__ import annotations

from dataclasses import dataclass

RAW = {
    "ml": """
churn|customer churn prediction model|Python, scikit-learn, XGBoost, pandas|figure out which customers are about to leave|lifted recall on churning accounts from 41% to 73% at the same precision|900|xgboost, shap
rag-chatbot|retrieval-augmented support chatbot|LangChain, RAG, Pinecone, FastAPI|a bot that answers customer questions from our help articles|deflected 38% of tier-1 support tickets in the first month|1800|langchain, pinecone
forecasting|demand forecasting pipeline|Python, Prophet, LightGBM, Airflow|predict how much stock we need each week|cut weekly forecast error (MAPE) from 24% to 13%|1200|prophet, lightgbm
doc-classify|document classification service|PyTorch, Hugging Face Transformers, BERT, FastAPI|sort incoming documents into the right queue automatically|reached 94% macro-F1 across 11 document classes|1100|transformers, torch
object-detection|object detection model|PyTorch, YOLO, OpenCV, computer vision|spot defects in photos from the production line|detected 96% of defects at 30 frames per second on an edge device|1500|ultralytics, cv2
recsys|product recommendation engine|Python, collaborative filtering, Redis, FastAPI|show shoppers things they are likely to buy next|raised click-through on recommended items by 22%|1400|implicit, redis
fraud|fraud detection model|Python, XGBoost, anomaly detection, SQL|catch suspicious transactions before they go through|caught 81% of fraudulent transactions with a 0.4% false-positive rate|1600|xgboost, imblearn
sentiment|review sentiment analysis|Python, spaCy, Transformers, NLP|understand what customers feel in their reviews|classified 120,000 reviews with 91% accuracy against hand labels|700|spacy, transformers
llm-finetune|LLM fine-tuning on domain text|LoRA, PEFT, Hugging Face, PyTorch|make an AI model write in our house style|improved blind human preference over the base model from 31% to 68%|2000|peft, bitsandbytes
ocr|invoice OCR and extraction pipeline|Tesseract, LayoutLM, Python, OpenCV|read scanned invoices and pull out the numbers|extracted line items with 97% field accuracy on 5,000 invoices|1300|pytesseract, cv2
speech|call transcription and summarisation|Whisper, Python, LLM prompting, FastAPI|turn recorded sales calls into short notes|cut manual note-taking by about 6 hours per rep per week|1000|whisper, pydub
anomaly|sensor anomaly detection|Python, Isolation Forest, time series, Kafka|warn us when a machine starts behaving oddly|flagged 9 of 10 real failures a median of 14 hours early|1300|sklearn, kafka
mlops|model deployment and MLOps pipeline|Docker, MLflow, Kubernetes, CI/CD|get our model out of the notebook and running reliably|took release time from two weeks to under one hour|1700|mlflow, bentoml
lead-scoring|lead scoring model|Python, scikit-learn, logistic regression, CRM data|rank sales leads by how likely they are to buy|top-decile leads converted at 4.2 times the average rate|800|sklearn, pandas
pricing-opt|price optimisation model|Python, regression, elasticity modelling, pandas|work out the best price for each product|added 6% gross margin in a four-week holdout test|1500|statsmodels, pandas
segmentation|image segmentation model|PyTorch, U-Net, computer vision, albumentations|outline the important regions in medical scans|reached a Dice score of 0.89 on a held-out hospital site|1800|segmentation_models_pytorch, albumentations
ner|entity extraction from contracts|spaCy, NER, Transformers, Python|pull names, dates and amounts out of contracts|extracted 14 entity types at 92% F1 and halved review time|1100|spacy, seqeval
semantic-search|semantic search over a product catalogue|sentence-transformers, FAISS, Elasticsearch, Python|let people search by meaning instead of exact words|reduced zero-result searches from 18% to 5%|1200|sentence_transformers, faiss
agent|multi-agent workflow automation|LangGraph, LLM agents, MCP, Python|have AI agents handle a multi-step back-office task|automated 70% of refund cases with human approval on the rest|2200|langgraph, mcp
monitoring|model monitoring and drift alerts|Evidently, Prometheus, Grafana, Python|tell us when the model starts getting worse|caught a data drift incident 11 days before it hit revenue|1000|evidently, prometheus_client
""",
    "web": """
storefront|e-commerce storefront|Next.js, React, Stripe, Tailwind CSS|an online shop where people can pay by card|raised checkout conversion from 1.9% to 2.8%|2000|next, stripe
saas-dashboard|SaaS analytics dashboard|React, TypeScript, FastAPI, PostgreSQL|a dashboard our customers log into to see their numbers|served 3,000 daily users with a 400 ms median load|1800|recharts, sqlalchemy
booking|appointment booking system|Node.js, Express, PostgreSQL, React|let clients book and reschedule appointments online|cut phone bookings by 60% in two months|1500|express, luxon
api-migration|REST API migration|Node.js, NestJS, REST API, PostgreSQL|move our old backend to something we can maintain|migrated 84 endpoints with zero downtime|1700|nestjs, typeorm
realtime-chat|real-time chat feature|WebSockets, Socket.IO, Redis, React|let users message each other live inside the app|held 5,000 concurrent connections on one small server|1200|socket.io, ioredis
cms|headless CMS migration|WordPress, Next.js, GraphQL, Contentful|move our blog off the old site builder without losing rankings|kept 100% of indexed URLs and halved page weight|1400|contentful, wpgraphql
payments|payment and subscription integration|Stripe, webhooks, Node.js, TypeScript|take monthly payments and handle failed cards|recovered 23% of failed renewals with retry logic|1000|stripe, zod
auth|authentication and single sign-on|OAuth 2.0, JWT, Auth0, Node.js|let staff sign in with their company account|removed 300 password-reset tickets a month|1100|passport, jose
redesign|mobile-responsive redesign|React, Tailwind CSS, Figma, accessibility|make the site work properly on phones|raised mobile session time by 35% and passed WCAG AA|1300|tailwindcss, radix-ui
admin|internal admin panel|React, TypeScript, Django, PostgreSQL|a back-office screen for our operations team|replaced 12 spreadsheets used by a 40-person team|1400|django, react-admin
graphql|GraphQL API layer|GraphQL, Apollo, Node.js, TypeScript|one API our web and mobile apps can both use|cut mobile payload size by 58%|1300|apollo-server, dataloader
perf|web performance optimisation|Core Web Vitals, Next.js, Lighthouse, caching|make the site load faster|took Largest Contentful Paint from 4.1 s to 1.6 s|900|next/image, workbox
cicd|CI/CD and containerised deployment|Docker, GitHub Actions, AWS, Nginx|deploy without someone copying files by hand|went from monthly to daily releases with one-click rollback|1000|docker, actions
multitenant|multi-tenant SaaS backend|Django, PostgreSQL, Celery, Redis|one system that keeps each customer's data separate|onboarded 120 tenants with row-level isolation|2400|django-tenants, celery
landing|marketing landing pages|Next.js, Tailwind CSS, SEO, Framer Motion|a few good-looking pages for a product launch|scored 98 on Lighthouse and doubled sign-up rate|600|framer-motion, next-seo
pwa|progressive web app|React, service workers, IndexedDB, TypeScript|an app that still works when the signal drops|let field staff complete 100% of forms offline|1500|workbox, idb
inventory|inventory management system|Laravel, MySQL, Vue.js, REST API|track stock across our warehouses|reduced stock-count discrepancies by 72%|1900|laravel, vuex
lms|learning management platform|Next.js, Prisma, PostgreSQL, video streaming|sell and deliver online courses|supported 8,000 learners with 99.9% uptime|2300|prisma, mux
marketplace|two-sided marketplace|React, Node.js, Stripe Connect, PostgreSQL|a site where sellers list and buyers pay, and we take a cut|processed $410k in payouts in the first quarter|2800|stripe, bull
extension|Chrome extension|JavaScript, Chrome APIs, React, Manifest V3|a browser add-on that saves our team clicks|saved each recruiter about 45 minutes a day|800|webextension-polyfill, vite
""",
    "data": """
sales-dash|sales performance dashboard|Power BI, DAX, SQL, data modelling|one screen that shows how sales are going|replaced a weekly 6-hour manual report|800|dax, pbix
etl|ELT pipeline and warehouse models|dbt, Airflow, Snowflake, SQL|get data from our tools into one place every night|loaded 14 sources nightly with tested models|1600|dbt, airflow
abtest|A/B test analysis|Python, statistics, hypothesis testing, pandas|tell us whether the new checkout actually works better|found the variant won by 3.1% with 95% confidence|700|scipy, statsmodels
cohort|cohort retention analysis|SQL, Python, pandas, Looker|see how long customers stick around|showed month-3 retention differed by 19 points between channels|800|pandas, seaborn
warehouse|data warehouse modelling|BigQuery, SQL, dimensional modelling, dbt|organise our data so reports agree with each other|cut dashboard query cost by 64%|1500|bigquery, dbt
excel|Excel reporting automation|Excel, VBA, Power Query, pivot tables|stop us rebuilding the same spreadsheet every month|turned a two-day month-end task into ten minutes|500|openpyxl, vba
survey|survey analysis and reporting|R, statistics, ggplot2, survey weighting|make sense of our customer survey|weighted 4,200 responses and found three drivers of satisfaction|600|survey, ggplot2
finance|financial reporting model|Excel, financial modelling, Power BI, SQL|a model that shows cash flow under different scenarios|was used by the board for a funding decision|1100|xlsxwriter, pbix
attribution|marketing attribution analysis|SQL, Python, GA4, attribution modelling|work out which ads actually bring sales|moved 30% of spend and lowered cost per acquisition by 17%|1200|google-analytics-data, pandas
api-collect|API data collection pipeline|Python, REST APIs, pandas, PostgreSQL|pull data from our providers' official APIs into a database|collected 2 million rows daily with retry and audit logs|700|requests, psycopg
forecast|sales forecasting workbook|Python, Prophet, Excel, time series|estimate next quarter's sales|landed within 4% of actual revenue for two quarters|900|prophet, openpyxl
tableau|executive Tableau dashboards|Tableau, SQL, LOD expressions, data visualisation|a clear weekly view for the leadership team|adopted by 5 executives as the Monday review|900|tableau, hyper
kpi|KPI framework and metric definitions|SQL, metric design, Looker, stakeholder interviews|agree what we measure and how|aligned 4 teams on 12 shared metric definitions|1000|lookml, sql
cleaning|data cleaning and deduplication|Python, pandas, fuzzy matching, SQL|tidy up our messy customer list|merged 38,000 duplicate customer records|500|rapidfuzz, pandas
segmentation|customer segmentation|Python, k-means, RFM analysis, pandas|group our customers so we can market to them differently|identified 5 segments; the top one drove 46% of revenue|800|sklearn, pandas
ga4|GA4 and web analytics reporting|GA4, BigQuery, Looker Studio, SQL|understand what visitors do on our site|found a checkout step losing 41% of mobile users|700|bigquery, ga4
pricing|pricing and margin analysis|SQL, Excel, Python, regression|see where we are losing margin|identified 60 SKUs sold below cost|900|statsmodels, openpyxl
supply|supply-chain reporting|Power BI, SQL Server, DAX, SSIS|track deliveries and stock in one report|reduced late-shipment reporting lag from 5 days to 1|1100|ssis, dax
looker|Looker Studio reporting suite|Looker Studio, Google Sheets, SQL, BigQuery|simple shareable reports for our clients|rolled out to 25 client accounts from one template|600|looker-studio, gspread
churn-analysis|churn driver analysis|SQL, Python, survival analysis, pandas|explain why customers cancel|showed onboarding delay explained most early churn|900|lifelines, pandas
""",
}

INDUSTRIES = ["fintech", "e-commerce", "healthcare", "logistics", "edtech",
              "real estate", "SaaS", "telecom", "retail", "insurance"]
INDUSTRY_PRICE = {"fintech": 1.25, "healthcare": 1.2, "insurance": 1.15, "SaaS": 1.1, "telecom": 1.05}


@dataclass(frozen=True)
class Task:
    domain: str
    slug: str
    title: str
    skills: tuple[str, ...]
    lay: str
    metric: str
    base_price: int
    libs: tuple[str, ...]


def load() -> dict[str, list[Task]]:
    out: dict[str, list[Task]] = {}
    for domain, block in RAW.items():
        out[domain] = []
        for line in block.strip().splitlines():
            slug, title, skills, lay, metric, price, libs = [p.strip() for p in line.split("|")]
            out[domain].append(Task(domain, slug, title, tuple(s.strip() for s in skills.split(",")),
                                    lay, metric, int(price), tuple(s.strip() for s in libs.split(","))))
    return out


PERSONAS = {
    "ml": {"name": "Sana Mirza (synthetic)", "headline": "AI/ML Engineer",
           "hourly_rate": 45, "min_budget": 400, "years": 5},
    "web": {"name": "Daniyal Raza (synthetic)", "headline": "Full-Stack Web Developer",
            "hourly_rate": 38, "min_budget": 350, "years": 6},
    "data": {"name": "Hira Qureshi (synthetic)", "headline": "Data Analyst",
             "hourly_rate": 30, "min_budget": 250, "years": 4},
}

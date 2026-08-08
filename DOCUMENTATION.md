# Affluence-AI: Autonomous Affiliate Marketing System — Complete Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Backend — Database Models (models.py)](#4-backend--database-models)
5. [Backend — Configuration (config.py)](#5-backend--configuration)
6. [Backend — Data Transfer Objects (schemas.py)](#6-backend--data-transfer-objects)
7. [Backend — Security & Auth (security.py)](#7-backend--security--auth)
8. [Backend — Rate Limiting (ratelimit.py)](#8-backend--rate-limiting)
9. [Backend — API Entry Point (main.py)](#9-backend--api-entry-point)
10. [Backend — Services](#10-backend--services)
    - [10.1 Audit Logger](101-audit-logger-audit_loggerpy)
    - [10.2 Click Tracker](102-click-tracker-click_trackerpy)
    - [10.3 Compliance Engine](103-compliance-engine-compliancepy)
    - [10.4 Content Distribution](104-content-distribution-content_distributionpy)
    - [10.5 Link Validator](105-link-validator-link_validatorpy)
    - [10.6 Market Scanner](106-market-scanner-market_scannerpy)
    - [10.7 Notification Service](107-notification-service-notification_servicepy)
    - [10.8 Reporting](108-reporting-reportingpy)
    - [10.9 Withdrawal Handler / Payout](109-withdrawal-handler-withdrawal_handlerpy)
    - [10.10 Purchase Tracker](1010-purchase-tracker-purchase_trackerpy)
    - [10.11 Link Generator](1011-link-generator-link_generatorpy)
    - [10.12 Commission Validator](1012-commission-validator-commission_validatorpy)
    - [10.13 Payout Monitor](1013-payout-monitor-payout_monitorpy)
    - [10.14 Alerts](1014-alerts-alertspy)
    - [10.15 Retry & Fallback Utilities](1015-retry--fallback-utilities-retrypy)
    - [10.16 Commission Forecasting](1016-commission-forecasting-forecastingpy)
    - [10.17 Social Account Manager](1017-social-account-manager-social_account_managerpy)
    - [10.18 Posting Controller](1018-posting-controller-posting_controllerpy)
11. [Backend — Integrations](#11-backend--integrations)
    - [11.1 Network Adapters (networks.py)](111-network-adapters)
    - [11.2 Payout Adapters (payouts.py)](112-payout-adapters)
12. [Backend — Database Setup (database.py)](#12-backend--database-setup)
13. [Backend — Scheduled Jobs](#13-backend--scheduled-jobs)
14. [Frontend — Dashboard (App.jsx)](#14-frontend--dashboard)
15. [Frontend — Styling (index.css)](#15-frontend--styling)
16. [Frontend — Entry Point (main.jsx)](#16-frontend--entry-point)
17. [Test Suite](#17-test-suite)
18. [Deployment](#18-deployment)
19. [API Endpoint Reference](#19-api-endpoint-reference)
20. [Scheduled Background Jobs Summary](#20-scheduled-background-jobs-summary)
21. [Configuration Reference](#21-configuration-reference)

---

## 1. System Overview

**Affluence-AI** is a full-stack, autonomous affiliate marketing system that automates the entire lifecycle of affiliate marketing:

- **Market Scanning**: Automatically scans affiliate networks (Amazon, ClickBank, ShareASale, CJ Affiliate, Jumia) for products and price updates
- **Content Generation**: Generates promotional content including blog posts, social media posts, and newsletter content using templated engines
- **Compliance Enforcement**: Enforces FTC disclosure requirements, platform-specific rules (Amazon Associates, ClickBank, Twitter, Facebook, LinkedIn policies), content moderation (spam detection, misleading claims), and cookie stuffing prevention
- **Content Distribution**: Publishes content to multiple platforms (Twitter/X, LinkedIn, WordPress, Medium) with both automatic and manual approval workflows
- Forecasting future earnings
- Managing social media accounts with encrypted credentials
- Providing a comprehensive real-time dashboard with 11 tabs

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Autonomous Workflow** | `/auto/execute` endpoint runs scan → content generation → compliance → publish → summary in one call |
| **Posting Modes** | `auto` (publishes directly after compliance) or `manual` (queues for admin approval) |
| **Compliance Strict Mode** | When enabled, content that fails compliance checks cannot be published |
| **Operator-Only Mode** | Viewer role can only read data; admin role can execute all operations |
| **SSE Real-Time Logs** | Server-Sent Events endpoint streams live audit log entries to the frontend |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Tailwind CSS)               │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  App.jsx — Single-page Dashboard with 11 Tabs                │  │

# 📦 Stock Count Management for ERPNext v15

> An enterprise-grade, mobile-first physical stock counting and audit management app for ERPNext v15. Supports Full, Cycle, and Blind inventory counts, camera barcode scanning, multi-UOM conversions, and seamless reconciliation of standard, batch-tracked, and serial-tracked items.

---

## 📑 Table of Contents

1. [Overview](https://www.google.com/search?q=%23-overview)
2. [Key Features](https://www.google.com/search?q=%23-key-features)
3. [Supported Count Types](https://www.google.com/search?q=%23-supported-count-types)
4. [Architecture & Technical Highlights](https://www.google.com/search?q=%23-architecture--technical-highlights)
5. [App Workflow](https://www.google.com/search?q=%23-app-workflow)
6. [Reports & Analytics](https://www.google.com/search?q=%23-reports--analytics)
7. [Installation & Setup](https://www.google.com/search?q=%23-installation--setup)
8. [Multi-Language Support](https://www.google.com/search?q=%23-multi-language-support)
9. [License](https://www.google.com/search?q=%23-license)

---

## 🔭 Overview

Standard ERPNext stock reconciliations can be manual, prone to human error during data entry, and difficult to execute directly on the warehouse floor.

**Stock Count Management** bridges this gap by offering a custom operational layer:

* **Backend:** Automated task generation, multi-UOM decomposition, and automated reconciliation generation.
* **Frontend / Desk:** Session tracking dashboard with real-time statistics and variance auditing.
* **Mobile UI:** A fast, responsive web interface tailored for handheld mobile devices with built-in camera barcode scanning.

---

## ✨ Key Features

* 📱 **Mobile Stock Counter (`/mobile-scanner`):** Optimized web app interface for warehouse staff to scan items, enter quantities, select UOMs, and track batches/serials on the go.
* 📷 **Native Camera Barcode Scanning:** Integrated browser camera scanner capable of parsing Item Barcodes directly into task entries.
* 📦 **Multi-UOM & Pack Decomposition:** Automatically converts counted base quantities into hierarchical packaging breakdowns (e.g., converts `120 Nos` to `1 Carton, 1 Bag, 0 Nos`).
* 🏷️ **ERPNext v15 Serial & Batch Bundle Support:** Native integration with ERPNext 15's `Serial and Batch Bundle` DocType, cleanly handling inward/outward inventory adjustments without zero-change errors.
* 🔒 **Blind Counting Security:** Prevents counter bias by hiding system stock balances from warehouse operators during audits.
* 🌐 **Full Arabic Localization:** Complete `ar.csv` translation and RTL-ready mobile views.

---

## 🎯 Supported Count Types

| Count Type | Description | System Qty Visible to Counter? | Default Finalize Action |
| --- | --- | --- | --- |
| **Full Count** | Complete warehouse audit covering all registered active inventory. | ✅ Yes | **Zero-out uncounted items** (Assumes missing items = 0 qty) |
| **Cycle Count** | Target audit filtered dynamically by **Item Group** (with nested child groups) or **Brand**. | ✅ Yes | **Retain uncounted items** (Only updates scanned items) |
| **Blind Count** | Security audit mode designed to force strict physical validation. | ❌ Hidden (`--`) | Flexible based on scope |

---

## 🛠️ Architecture & Technical Highlights

### 1. ERPNext 15 Bundle Reconciliation Pipeline

Unlike ERPNext 14, ERPNext 15 requires all batch/serial adjustments inside a `Stock Reconciliation` to pass through a `Serial and Batch Bundle`.

To prevent submission blocks (`Voucher No is mandatory`) or empty reconciliation errors (`None of the items have any change in quantity or value`), the app uses the following lifecycle:

1. Filters for items where $\text{Counted Quantity} \neq \text{Current ERP Quantity}$.
2. Generates draft `Serial and Batch Bundle` documents with appropriate transaction types (`Inward` for surplus, `Outward` for deficit).
3. Attaches draft bundle IDs directly into the `items` payload array during `frappe.get_doc()` instantiation.
4. Executes a single unified document insertion and save pass.

```
[Physical Scan] ➔ [Count Entry] ➔ [Variance Check] ➔ [Draft Bundle (SABB)] ➔ [Stock Reconciliation]

```

---

## 🔄 App Workflow

```
┌─────────────────────────┐
│  Stock Count Session   │ ➔ Create Session (Draft) & Select Warehouse / Count Type
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Generate Tasks       │ ➔ Pulls actual Bin stock (Optionally filtered by Item Group / Brand)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Mobile Stock Counter    │ ➔ Warehouse staff scan barcodes & submit counts on mobile
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Variance Audit Review   │ ➔ Supervisors review counted values vs. system stock
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Stock Reconciliation    │ ➔ Auto-creates & submits native Stock Reconciliation document
└─────────────────────────┘

```

---

## 📊 Reports & Analytics

The app comes bundled with 3 custom Frappe Script Reports out of the box:

1. **Variance Audit Report**
* Detailed line-by-line financial audit comparing Expected ERP Qty vs. Physical Counted Qty.
* Includes calculated **ERP Value**, **Counted Value**, **Variance Value**, and **Formatted Pack Breakdowns** (Cartons, Bags, Base Units).


2. **Stock Count Session Progress Summary**
* Executive overview dashboard tracking progress %, total items, counted items, and uncounted items per session.


3. **Uncounted Items Exception Report**
* Operational exception list flagging missed or skipped items during an active audit session.



---

## 🚀 Installation & Setup

### Prerequisites

* Frappe Framework `v15.x`
* ERPNext `v15.x`

### Step-by-Step Installation

1. **Fetch the App:**
```bash
cd ~/frappe-bench
bench get-app https://github.com/mohammedlutf/stock_count_management.git

```


2. **Install on Site:**
```bash
bench --site [your-site-name] install-app stock_count_management

```


3. **Migrate & Clear Cache:**
```bash
bench --site [your-site-name] migrate
bench --site [your-site-name] clear-cache
bench restart

```


4. **Access the App:**
* **Desk Workspace:** Search for **Stock Count Management** in the ERPNext search bar.
* **Mobile Interface:** Navigate to `https://[your-site-name]/mobile-scanner` on any mobile device.



---

## 🌐 Multi-Language Support

The app includes full English (`en`) and Arabic (`ar`) translations.

To view the mobile scanner in Arabic:

* Set the logged-in User's language preference to **Arabic (العربية)** in **My Settings**.
* Or append the language flag in the URL: `https://[your-site-name]/mobile-scanner?_lang=ar`

---

## 📜 License

This project is licensed under the **MIT License** - feel free to modify and adapt it for personal or commercial ERPNext deployments.

---
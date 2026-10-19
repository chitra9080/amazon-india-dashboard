# Amazon India Sales & Profit Dashboard

An interactive management dashboard built with Python, Pandas, Streamlit and Plotly. It was built for the
**Sapphire IQ Amazon India Dashboard** project: a simple, one-page view of sales, profit, products, orders,
order status, payments, fulfillment and states for a manager from a non-technical background.

## Project overview

The dashboard reads the Excel file `data/Amazon_Sales_Data_India.xlsx`, validates and cleans it, calculates
the KPIs described below, and shows them as KPI cards and interactive charts. A sidebar lets the viewer filter
by date, category, product, state, order status, payment method and fulfillment method.

## Problem statement

The manager needs to understand overall business performance quickly, without technical knowledge:
how sales and profit are changing, which categories and products drive the business, how many orders are
lost to returns and cancellations, and which payment methods, fulfillment methods and states generate business.

## Project objectives

1. Show overall sales and profit performance with a monthly trend.
2. Show which categories and products perform best and which may need attention.
3. Show delivered, shipped, returned and cancelled orders, return/cancellation rates and the revenue affected.
4. Show performance by payment method, fulfillment method and state.
5. Keep every number traceable to the dataset, with clearly documented formulas.

## Business requirements (from the project PDF)

| Section | Required content |
|---|---|
| 1. Overall Sales & Profit | Total Sales, Total Profit, Total Orders, Total Units Sold, Average Order Value, Profit Margin %, Monthly Sales & Profit Trend |
| 2. Category & Product | Category-wise Sales, Profit and Units Sold; Top 10 Products by Sales |
| 3. Order Status & Revenue Loss | Delivered, Shipped, Returned, Cancelled orders; Return Rate %; Cancellation Rate %; Category-wise Returns & Cancellations |
| 4. Payment, Fulfillment & Geography | Sales and Profit by Payment Method and by Fulfillment Method; State-wise Sales, Profit and Orders |

## Dataset description

* File: `data/Amazon_Sales_Data_India.xlsx`, one worksheet (`Sheet1`), 10,000 rows, 13 columns, one row per order.
* Currency: Indian rupees (the column names end in `_INR`).
* Dates run from 2024-01-01 to 2026-08-30 (2026 is a partial year).

### Actual dataset columns

| Column | Meaning |
|---|---|
| `Order_ID` | Unique order identifier (e.g. IN-AMD-100000) |
| `Order_Date` | Order date, stored as text `YYYY-MM-DD` |
| `Category` | Product category (5 values) |
| `Product` | Product name (25 values, 5 per category) |
| `Quantity` | Units in the order (1 to 4) |
| `Unit_Price_INR` | Price per unit before discount |
| `Discount_Pct` | Discount as a fraction (0 to 0.25) |
| `Total_Sales_INR` | Order sales after discount (= Quantity × Unit price × (1 − Discount)) |
| `Profit_INR` | Order profit |
| `Payment_Method` | UPI, Credit/Debit Card, Cash on Delivery (COD), Net Banking, Amazon Pay Later |
| `Fulfillment` | Amazon (FBA), Seller Flex, Merchant (FBM) |
| `Order_Status` | Delivered, Shipped, Returned, Cancelled |
| `Ship_State` | Shipping state (10 states) |

### Dataset sharing note

The dataset was provided for the Sapphire IQ internship project. Before making a **public** repository,
confirm that sharing it is allowed. If it is not, uncomment the last line of `.gitignore` (`data/*.xlsx`) so the
file is not uploaded; the dashboard then offers an **upload box** so a reviewer can supply the Excel file themselves.

## Data cleaning process

Implemented in `src/data_cleaning.py`. The original Excel file is never modified.

1. Column names and text values are trimmed; blank text becomes missing.
2. Status labels are made consistent (`delivered ` → `Delivered`, `Canceled` → `Cancelled`).
3. Rows with no `Order_ID` are removed (they cannot be counted safely) and counted in the report.
4. `Order_Date` is converted to a real date; rows with an unreadable date are removed and counted.
5. Missing category/product/payment/fulfillment/state/status labels become `Unknown`.
6. Numbers are converted safely. Non-numeric values become missing; negative quantity, price or sales become
   missing. **Missing numbers are never estimated or filled in.** Negative profit is kept (a real loss).
7. Only rows identical in **every** column are removed as duplicates. Rows that share an `Order_ID` but differ in
   content are kept, and orders are always counted by **distinct** `Order_ID`.

A summary of what was changed is shown in the dashboard's **About the data** tab.

## KPI definitions and formulas

**Rule:** money and unit metrics count **Delivered + Shipped** orders. Order counts and return/cancellation
rates count **all distinct orders**. "Recorded" figures include every order.

| KPI | Formula |
|---|---|
| Total Sales | Σ `Total_Sales_INR` where status is Delivered or Shipped |
| Total Profit | Σ `Profit_INR` where status is Delivered or Shipped |
| Average Order Value | Total Sales ÷ distinct Delivered + Shipped orders |
| Profit Margin % | Total Profit ÷ Total Sales × 100 (weighted; not an average of row margins) |
| Total Orders | Distinct `Order_ID` (all statuses) |
| Total Units Sold | Σ `Quantity` where status is Delivered or Shipped |
| Total Recorded Sales | Σ `Total_Sales_INR` for all orders |
| Sales in Cancelled / Returned Orders | Σ `Total_Sales_INR` for that status |
| Share of Recorded Sales Lost | (Cancelled + Returned sales) ÷ Recorded sales × 100 |
| Return Rate % | Distinct Returned orders ÷ distinct all orders × 100 |
| Cancellation Rate % | Distinct Cancelled orders ÷ distinct all orders × 100 |
| Monthly Sales & Profit | Delivered + Shipped totals per calendar month, in date order (empty months show 0) |
| Category / payment / fulfillment / state sales, profit, units | Delivered + Shipped totals per group |
| Category-wise and state-wise orders | Distinct `Order_ID` per group (all statuses) |
| Top 10 Products | Highest Delivered + Shipped sales per product |

Consistency check built into the tests: **Total Recorded Sales = Total Sales + Cancelled Sales + Returned Sales**.
Whenever a ratio would divide by zero, the dashboard shows **N/A**.

## Dashboard features

* Header with title, description, selected date range and number of orders shown.
* Sidebar filters: date range, category, product, state, order status, payment method, fulfillment method,
  and a **Reset all filters** button. Only columns that exist in the dataset are used.
* KPI cards with compact rupee formatting (₹ Cr / ₹ Lakh) and the full amount underneath.
* Five tabs: Overall performance, Category & product, Order status & loss, Payment/fulfillment/states, About the data.
* Interactive Plotly charts with tooltips: line chart (monthly trend), horizontal bars (categories, top
  products, payments, fulfillment, states), donut (order status), grouped bars (returns vs cancellations).
* Plain-language takeaways calculated from the filtered data, and "products that may need attention" tables.
* Helpful messages when a filter returns no rows, and clear errors if the dataset is missing or has missing columns.
* Not included: a map. Only the state name is available and no state boundary file is bundled, so state
  performance is shown as bar charts.

## Technology stack

Python, Pandas, NumPy, Streamlit, Plotly (Express and Graph Objects), OpenPyXL (reads Excel), Pytest.

## Project folder structure

```
amazon-india-dashboard/
├── app.py                  # Streamlit dashboard
├── requirements.txt
├── pytest.ini
├── README.md
├── .gitignore
├── .streamlit/config.toml  # light theme, usage statistics off
├── data/
│   └── Amazon_Sales_Data_India.xlsx
├── src/
│   ├── __init__.py
│   ├── data_loader.py      # finds and reads the Excel file
│   ├── data_cleaning.py    # validation and cleaning
│   ├── metrics.py          # all KPI calculations and filters
│   ├── formatting.py       # ₹ lakh/crore and percentage formatting
│   └── charts.py           # Plotly charts
└── tests/
    ├── test_metrics.py
    ├── test_data_validation.py
    └── test_formatting.py
```

## Installation (Windows, PowerShell)

1. Install Python 3.10 or newer from python.org (tick **Add python.exe to PATH**) and check:
   ```powershell
   python --version
   ```
2. Open the project folder in PowerShell (or in VS Code: **File → Open Folder**, then **Terminal → New Terminal**).
3. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, and try again.
4. Install the dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. Make sure `Amazon_Sales_Data_India.xlsx` is inside the `data` folder.

## Run the dashboard

```powershell
streamlit run app.py
```

Streamlit prints a local address (normally http://localhost:8501) and opens your browser. If it asks for an
email address in the terminal, just press Enter. Press `Ctrl + C` in the terminal to stop the app, and run
`deactivate` to leave the virtual environment.

## Testing

```powershell
python -m pytest
```

The tests use small hand-made datasets with known answers (sales, profit, orders, units, average order value,
margin, return and cancellation rates, category/monthly/state aggregations, duplicate order IDs, missing values,
division by zero, empty data, missing columns, filters with no rows). Other tests recalculate the key KPIs from the real Excel file with plain
Python (OpenPyXL, without Pandas) and compare them with the dashboard's numbers. If you replace the dataset,
the real-data tests still run; they compare against the new file.

### Manual verification checklist

- [ ] `streamlit run app.py` starts and the page opens without a red error box.
- [ ] The header shows the date range 01 Jan 2024 to 30 Aug 2026 and 10,000 orders.
- [ ] All four sections plus "About the data" appear as tabs.
- [ ] Total Recorded Sales = Total Sales + Sales in Cancelled + Sales in Returned (use the full rupee amounts).
- [ ] Recalculate Total Sales in Excel: filter `Order_Status` to Delivered and Shipped, then sum `Total_Sales_INR`.
- [ ] Recalculate Total Orders: count rows (each row is one order); status counts add up to the total.
- [ ] Change a filter (for example one category) and confirm the KPI cards, charts and tables all change.
- [ ] The monthly chart runs from Jan 2024 to Aug 2026 in order.
- [ ] Choose filters that match nothing and confirm a friendly message appears instead of an error.
- [ ] Click **Reset all filters** and confirm everything returns to the full dataset.

## Known limitations

* One row per order and one product per order; there are no multi-item orders in this file.
* Profit is exactly zero for every Cancelled and Returned order in the data.
* Shipped orders are still in transit and may later be returned.
* 2026 is a partial year (to August); compare months rather than calendar years.
* Unit prices overlap heavily within categories, so the data looks synthetic; treat rankings as a demonstration.
* Only the shipping state is available (10 states); there is no map or city-level view.
* Visual layout was not checked in a real browser by the author of this code; verify it on your machine (see Screenshots).

## Future improvements

* State map using a licensed or open India state boundary file.
* Year-over-year and month-over-month comparison once full years are available.
* Export of the filtered data and charts, and a printable summary page.
* Profit analysis by discount level and a cost view if cost data becomes available.
* Deployment of a live version for reviewers.

## Screenshots

No screenshots are included yet. After running the dashboard on your own machine:

1. Create a folder named `screenshots` in the project.
2. Take a screenshot of each tab (Windows: `Win + Shift + S`) and save them as, for example,
   `screenshots/01-overall.png`, `02-category-product.png`, `03-order-status.png`, `04-payment-fulfillment-states.png`.
3. Add them below, replacing this note:

```markdown
![Overall performance](screenshots/01-overall.png)
![Category and product](screenshots/02-category-product.png)
![Order status and loss](screenshots/03-order-status.png)
![Payment, fulfillment and states](screenshots/04-payment-fulfillment-states.png)
```

Only add screenshots that you captured from your own running dashboard.

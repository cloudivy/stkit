import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ----------------- CONFIG -----------------
st.set_page_config(page_title="Stationery Inventory", layout="wide")

DATA_FILE = "stationery_inventory.csv"

# ----------------- DATA LAYER -----------------
def init_data_file():
    """Create CSV with basic columns if not present."""
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(
            columns=[
                "item_id",
                "item_name",
                "category",
                "unit",
                "quantity",
                "reorder_level",
                "location",
                "last_updated",
                "remarks",
            ]
        )
        df.to_csv(DATA_FILE, index=False)


def load_data():
    init_data_file()
    df = pd.read_csv(DATA_FILE)
    # Ensure types
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    if "reorder_level" in df.columns:
        df["reorder_level"] = pd.to_numeric(df["reorder_level"], errors="coerce").fillna(0).astype(int)
    return df


def save_data(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


def generate_item_id(df: pd.DataFrame) -> str:
    """Simple incremental ID: STN-0001, STN-0002, ..."""
    if df.empty:
        return "STN-0001"
    existing_ids = df["item_id"].dropna().tolist()
    nums = []
    for x in existing_ids:
        try:
            nums.append(int(str(x).split("-")[-1]))
        except ValueError:
            continue
    next_num = max(nums) + 1 if nums else 1
    return f"STN-{next_num:04d}"


# ----------------- UI HELPERS -----------------
def sidebar_filters(df: pd.DataFrame):
    st.sidebar.subheader("Filters")
    category_filter = st.sidebar.multiselect(
        "Category",
        options=sorted(df["category"].dropna().unique().tolist()),
        default=None,
    )
    location_filter = st.sidebar.multiselect(
        "Location",
        options=sorted(df["location"].dropna().unique().tolist()),
        default=None,
    )
    low_stock_only = st.sidebar.checkbox("Show only low stock items (qty ≤ reorder level)", value=False)

    return category_filter, location_filter, low_stock_only


def apply_filters(df, category_filter, location_filter, low_stock_only):
    if category_filter:
        df = df[df["category"].isin(category_filter)]
    if location_filter:
        df = df[df["location"].isin(location_filter)]
    if low_stock_only:
        df = df[df["quantity"] <= df["reorder_level"]]
    return df


# ----------------- PAGES -----------------
def page_dashboard(df: pd.DataFrame):
    st.header("Stationery Inventory Dashboard")

    total_items = len(df)
    total_qty = int(df["quantity"].sum()) if not df.empty else 0
    low_stock_count = int((df["quantity"] <= df["reorder_level"]).sum()) if not df.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Distinct items", total_items)
    col2.metric("Total quantity", total_qty)
    col3.metric("Low-stock items", low_stock_count)

    st.markdown("---")
    st.subheader("Current inventory list")

    category_filter, location_filter, low_stock_only = sidebar_filters(df)
    filtered_df = apply_filters(df.copy(), category_filter, location_filter, low_stock_only)

    if filtered_df.empty:
        st.info("No items match current filters.")
    else:
        st.dataframe(
            filtered_df.sort_values("item_name"),
            use_container_width=True,
        )


def page_add_edit(df: pd.DataFrame):
    st.header("Add or Update Item")

    mode = st.radio("Mode", ["Add new item", "Update existing item"], horizontal=True)

    if mode == "Add new item":
        with st.form("add_item_form"):
            col1, col2 = st.columns(2)

            with col1:
                item_name = st.text_input("Item name", placeholder="e.g., A4 Paper Rim")
                category = st.text_input("Category", placeholder="e.g., Paper, Pen, File")
                unit = st.text_input("Unit of measure", value="Nos", placeholder="Nos / Pack / Box")
                location = st.text_input("Location", placeholder="e.g., Main Store")

            with col2:
                quantity = st.number_input("Quantity", min_value=0, step=1, value=0)
                reorder_level = st.number_input("Reorder level", min_value=0, step=1, value=10)
                remarks = st.text_area("Remarks", placeholder="Any notes...")

            submitted = st.form_submit_button("Add item")

            if submitted:
                if not item_name.strip():
                    st.error("Item name is required.")
                    return

                new_id = generate_item_id(df)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                new_row = {
                    "item_id": new_id,
                    "item_name": item_name.strip(),
                    "category": category.strip() or "Uncategorized",
                    "unit": unit.strip() or "Nos",
                    "quantity": int(quantity),
                    "reorder_level": int(reorder_level),
                    "location": location.strip() or "Not specified",
                    "last_updated": now,
                    "remarks": remarks.strip(),
                }

                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(df)
                st.success(f"Item added with ID {new_id}.")
    else:
        if df.empty:
            st.info("No items to update. Add items first.")
            return

        item_map = {f"{row.item_id} - {row.item_name}": row.item_id for _, row in df.iterrows()}
        selected = st.selectbox("Select item to update", options=list(item_map.keys()))
        selected_id = item_map[selected]

        row = df[df["item_id"] == selected_id].iloc[0]

        with st.form("update_item_form"):
            col1, col2 = st.columns(2)

            with col1:
                item_name = st.text_input("Item name", value=row["item_name"])
                category = st.text_input("Category", value=row.get("category", ""))
                unit = st.text_input("Unit of measure", value=row.get("unit", "Nos"))
                location = st.text_input("Location", value=row.get("location", ""))

            with col2:
                quantity = st.number_input("Quantity", min_value=0, step=1, value=int(row.get("quantity", 0)))
                reorder_level = st.number_input(
                    "Reorder level",
                    min_value=0,
                    step=1,
                    value=int(row.get("reorder_level", 0)),
                )
                remarks = st.text_area("Remarks", value=row.get("remarks", ""))

            submitted = st.form_submit_button("Update item")

            if submitted:
                if not item_name.strip():
                    st.error("Item name is required.")
                    return

                idx = df.index[df["item_id"] == selected_id][0]
                df.at[idx, "item_name"] = item_name.strip()
                df.at[idx, "category"] = category.strip() or "Uncategorized"
                df.at[idx, "unit"] = unit.strip() or "Nos"
                df.at[idx, "location"] = location.strip() or "Not specified"
                df.at[idx, "quantity"] = int(quantity)
                df.at[idx, "reorder_level"] = int(reorder_level)
                df.at[idx, "remarks"] = remarks.strip()
                df.at[idx, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                save_data(df)
                st.success(f"Item {selected_id} updated.")


def page_issue_receive(df: pd.DataFrame):
    st.header("Issue / Receive Stock")

    if df.empty:
        st.info("No items in inventory. Add items first.")
        return

    item_map = {f"{row.item_id} - {row.item_name}": row.item_id for _, row in df.iterrows()}
    selected = st.selectbox("Select item", options=list(item_map.keys()))
    selected_id = item_map[selected]

    row = df[df["item_id"] == selected_id].iloc[0]

    st.write(f"Current quantity: **{int(row['quantity'])} {row.get('unit', 'Nos')}**")
    st.write(f"Reorder level: **{int(row['reorder_level'])}**")

    mode = st.radio("Transaction type", ["Issue (decrease stock)", "Receive (increase stock)"], horizontal=True)

    with st.form("txn_form"):
        qty = st.number_input("Quantity", min_value=1, step=1, value=1)
        reason = st.text_input("Reason / reference", placeholder="e.g., Issued to office X, PO no., etc.")
        submitted = st.form_submit_button("Post transaction")

        if submitted:
            idx = df.index[df["item_id"] == selected_id][0]
            current_qty = int(df.at[idx, "quantity"])

            if mode.startswith("Issue"):
                if qty > current_qty:
                    st.error(f"Cannot issue {qty}; only {current_qty} available.")
                    return
                new_qty = current_qty - qty
            else:
                new_qty = current_qty + qty

            df.at[idx, "quantity"] = int(new_qty)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df.at[idx, "last_updated"] = now

            # Append transaction info to remarks (simple audit trail)
            old_remarks = str(df.at[idx, "remarks"]) if not pd.isna(df.at[idx, "remarks"]) else ""
            line = f"[{now}] {mode.split()[0]} {int(qty)} ({reason})"
            df.at[idx, "remarks"] = (old_remarks + " | " + line).strip(" |")

            save_data(df)
            st.success(f"{mode.split()[0]}d {int(qty)} units. New quantity: {new_qty}.")


def page_admin(df: pd.DataFrame):
    st.header("Admin / Delete Items")

    if df.empty:
        st.info("No items to delete.")
        return

    st.warning("Deleting items is permanent. Export data first if needed.")

    st.download_button(
        "Download full inventory as CSV",
        data=df.to_csv(index=False),
        file_name=f"stationery_inventory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

    item_map = {f"{row.item_id} - {row.item_name}": row.item_id for _, row in df.iterrows()}
    selected = st.selectbox("Select item to delete", options=list(item_map.keys()))
    selected_id = item_map[selected]

    if st.button("Delete selected item"):
        df_new = df[df["item_id"] != selected_id].reset_index(drop=True)
        save_data(df_new)
        st.success(f"Item {selected_id} deleted. Reload page to see updated list.")


# ----------------- MAIN APP -----------------
def main():
    st.title("Stationery Inventory Management")

    df = load_data()

    menu = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Add / Update Item", "Issue / Receive", "Admin"],
    )

    if menu == "Dashboard":
        page_dashboard(df)
    elif menu == "Add / Update Item":
        page_add_edit(df)
    elif menu == "Issue / Receive":
        page_issue_receive(df)
    elif menu == "Admin":
        page_admin(df)


if __name__ == "__main__":
    main()


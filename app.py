import streamlit as st
import pandas as pd
from io import BytesIO


def load_sales_file(uploaded_file) -> tuple[pd.DataFrame | None, str]:
    """Placeholder: load and validate the Sale CSV file. Returns (df, filename)."""
    if uploaded_file is None:
        return None, ""
    
    df = pd.read_csv(uploaded_file)
    df = df[['SKU Code', 'Total Qty']]
    return df, getattr(uploaded_file, "name", str(uploaded_file))

def load_master_file(uploaded_file):
    column_mapping = {
        "Nykaa Code": "SKU Code",
        "EAN": "EAN Code",
    }

    frames = []
    files = uploaded_file if isinstance(uploaded_file, list) else [uploaded_file]

    for f in files:
        try:
            df = pd.read_excel(f)
            df = df.rename(columns=column_mapping)

            frames.append(df)
        except Exception as e:
            print(e)

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined[["SKU Code", "EAN Code", "MRP"]]

def load_sp_file(uploaded_file):
    """Load one or many SP CSV files. Returns (df, filenames).

    - If `uploaded_file` is a list (multiple uploads), concatenate them.
    - Returns (None, []) when nothing uploaded.
    """
    if not uploaded_file:
        return None, []

    frames = []
    names = []
    # support single UploadedFile or list
    files = uploaded_file if isinstance(uploaded_file, list) else [uploaded_file]
    for f in files:
        try:
            df = pd.read_csv(f)
            df = df.rename(columns={"SKU": "SKU Code", "Discount %": "Disc"})
            frames.append(df)
            # UploadedFile has .name attribute when coming from Streamlit
            names.append(getattr(f, "name", str(f)))
        except Exception:
            # skip files that fail to read
            continue

    if not frames:
        return None, names

    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined, names


def extract_month_label(filename: str, default_label: str) -> str:
    """Extract a short month label from a filename, e.g. Aug26 or Jul26."""
    import re

    if not filename:
        return default_label

    match = re.search(r"([A-Za-z]{3}\d{2,4})", filename)
    return match.group(1) if match else default_label


def extract_sales_month_label(filename: str, default_label: str) -> str:
    """Extract month-year from a filename like July-2026."""
    import re

    if not filename:
        return default_label

    match = re.search(r"([A-Za-z]+-\d{4})", filename)
    return match.group(1) if match else default_label


def process_debit_note_calculation(
    sale_data: pd.DataFrame,
    previous_sp: pd.DataFrame,
    current_sp: pd.DataFrame,
    previous_filenames: list,
    current_filenames: list,
    sales_month: str,
    master_data: pd.DataFrame
):
    """Process files and return the downloadable Excel output bytes."""
    if sale_data is None or previous_sp is None or current_sp is None or master_data is None:
        return None

    def normalize_sku(df, col_name="SKU Code"):
        if col_name in df.columns:
            # Convert to string, strip whitespace, and remove Excel's trailing '.0' for floats
            df[col_name] = df[col_name].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        return df

    previous_sp = previous_sp.rename(columns={"Disc": "Disc_prev"})
    current_sp = current_sp.rename(columns={"Disc": "Disc_curr"})

    sale_data = normalize_sku(sale_data)
    previous_sp = normalize_sku(previous_sp)
    current_sp = normalize_sku(current_sp)
    master_data = normalize_sku(master_data)

    joined = sale_data.merge(previous_sp, on="SKU Code", how="left")
    joined = joined.merge(current_sp, on="SKU Code", how="left")
    joined = joined.merge(master_data, on="SKU Code", how="left")

    joined["Prev SP"] = joined["MRP"] * (1 - joined["Disc_prev"].fillna(0) / 100)
    joined["Curr SP"] = joined["MRP"] * (1 - joined["Disc_curr"].fillna(0) / 100)
    joined["Difference in Price"] = joined["Prev SP"] - joined["Curr SP"]
    joined["Total SP Difference"] = joined["Difference in Price"] * joined["Total Qty"]
    joined.loc[joined["Disc_prev"].isna(), "Total SP Difference"] = 0
    joined.loc[joined["Disc_curr"].isna(), "Total SP Difference"] = 0
    joined["Total Margin Difference"] = joined["Total SP Difference"] * [0.43 if diff > 0 else 1-0.43 for diff in joined['Total SP Difference']]

    final_df = joined.copy()
    final_df = final_df.drop(columns=["Difference in Price"], errors="ignore")

    agg_dict = {
        "Total Qty": "sum",
        "Total SP Difference": "sum",
        "Total Margin Difference": "sum"
    }

    for col in final_df.columns:
        if col not in agg_dict and col != "SKU Code":
            agg_dict[col] = "first"

    final_df = final_df.groupby("SKU Code", as_index=False, dropna=False).agg(agg_dict)
    final_df = final_df[['EAN Code', 'SKU Code', 'MRP', 'Disc_prev', 'Disc_curr', 'Prev SP', 'Curr SP', 'Total Qty', 'Total SP Difference', 'Total Margin Difference']]

    prev_month = extract_month_label(previous_filenames[0] if previous_filenames else "", "Prev month")
    curr_month = extract_month_label(current_filenames[0] if current_filenames else "", "Curr month")
    prev_label = f"{prev_month}"
    curr_label = f"{curr_month}"

    total_row = {
        "EAN Code": "TOTAL",
        "Total Qty": final_df["Total Qty"].sum(skipna=True),
        "Total SP Difference": final_df["Total SP Difference"].sum(skipna=True),
        "Total Margin Difference": final_df["Total Margin Difference"].sum(skipna=True),
    }

    skipped_rows = joined[["Disc_prev", "Disc_curr"]].isna().any(axis=1).sum()
    skipped_row = {"EAN Code": "SKIPPED ROWS", "SKU Code": skipped_rows}
    empty_row = dict.fromkeys(final_df.columns, None)

    # order: total, two empty rows, then skipped
    summary_df = pd.DataFrame([total_row, empty_row, empty_row, skipped_row])

    output_df = pd.concat([final_df, summary_df], ignore_index=True, sort=False)

    rename_map = {
        "Disc_prev": f"{prev_label} Customer discount %",
        "Disc_curr": f"{curr_label} Customer discount %",
        "Prev SP": f"{prev_label} SP",
        "Curr SP": f"{curr_label} SP",
        "Total Qty": f"Sold Qty {sales_month}"
    }
        
    output_df = output_df.rename(columns=rename_map).round(2)

    if "EAN Code" in output_df.columns:
        output_df["EAN Code"] = (
            output_df["EAN Code"]
            .astype(str)
            .str.replace(r'\.0$', '', regex=True)
            # Replace 'nan' strings with empty strings for clean output
            .replace('nan', '') 
        )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        output_df.to_excel(writer, index=False, sheet_name="Debit Note")
        workbook = writer.book
        worksheet = writer.sheets["Debit Note"]
        for idx, column in enumerate(output_df.columns, 1):
            column_name = str(column)
            values = output_df[column].fillna("")
            max_value_length = max((len(str(v)) for v in values), default=0)
            column_width = max(
                max_value_length,
                len(column_name)
            ) + 2
            worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = column_width

    return output.getvalue()


def main():
    st.set_page_config(page_title="Debit Note Calculator", page_icon="📄")
    st.title("Debit Note Calculator")
    st.write(
        "Use the steps below to upload your Sales and SP files, then download the debit note calculation."
    )

    st.markdown("## Step 1: Upload the Sales file")
    sale_file = st.file_uploader(
        "Upload the Sale file (.csv)", type=["csv"], key="sale_upload"
    )
    sale_data, sale_filename = load_sales_file(sale_file)
    sale_month_label = extract_sales_month_label(sale_filename, "Sale month")

    # if sale_filename:
    #     st.write(f"Sales file month label: **{sale_month_label}**")

    st.markdown("## Step 2: Upload previous month SP (discount) file")
    previous_sp_file = st.file_uploader(
        "Upload previous month SP file(s) (.csv)", type=["csv"], key="prev_sp_upload", accept_multiple_files=True
    )
    previous_sp_data, previous_sp_names = load_sp_file(previous_sp_file)

    st.markdown("## Step 3: Upload current month SP file")
    current_sp_file = st.file_uploader(
        "Upload current month SP file(s) (.csv)", type=["csv"], key="curr_sp_upload", accept_multiple_files=True
    )
    current_sp_data, current_sp_names = load_sp_file(current_sp_file)

    st.markdown("## Step 4: Upload Master files")
    master_file = st.file_uploader(
        "Upload master file(s) (.xls/.xlsx)", type=["xls","xlsx"], key="master_upload", accept_multiple_files=True
    )
    master_data = load_master_file(master_file)

    st.markdown("## Step 5: Download debit note calculation")
    if sale_data is not None and previous_sp_data is not None and current_sp_data is not None and master_data is not None:
        if st.button("Prepare download"):
            output_bytes = process_debit_note_calculation(
                sale_data,
                previous_sp_data,
                current_sp_data,
                previous_sp_names,
                current_sp_names,
                sale_month_label,
                master_data
            )
            if output_bytes:
                st.download_button(
                    label="Download debit note calculation",
                    data=output_bytes,
                    file_name=f"debit_note_calculation_{sale_month_label}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.warning("Processing logic is not implemented yet.")
    else:
        st.info("Upload all four files to enable the download step.")


if __name__ == "__main__":
    main()


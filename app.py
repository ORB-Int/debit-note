import streamlit as st


def load_soh_file(uploaded_file):
    """Placeholder: load and validate the SOH Excel file."""
    if uploaded_file is None:
        return None
    return uploaded_file


def load_sp_file(uploaded_file):
    """Placeholder: load and validate a SP CSV file."""
    if uploaded_file is None:
        return None
    return uploaded_file


def process_debit_note_calculation(soh_file, previous_sp_file, current_sp_file):
    """Placeholder: process files and return the downloadable output bytes."""
    if not soh_file or not previous_sp_file or not current_sp_file:
        return None

    # Replace this stub with the real debit note calculation logic.
    placeholder_content = "Debit note calculation placeholder. Replace with actual logic."
    return placeholder_content.encode("utf-8")


def main():
    st.set_page_config(page_title="Debit Note Calculator", page_icon="📄")
    st.title("Debit Note Calculator")
    st.write(
        "Use the steps below to upload your SOH and SP files, then download the debit note calculation."
    )

    st.markdown("## Step 1: Upload the SOH file")
    soh_file = st.file_uploader(
        "Upload the SOH file (.xlsx)", type=["xlsx"], key="soh_upload"
    )
    soh_data = load_soh_file(soh_file)

    st.markdown("## Step 2: Upload previous month SP (discount) file")
    previous_sp_file = st.file_uploader(
        "Upload previous month SP file (.csv)", type=["csv"], key="prev_sp_upload"
    )
    previous_sp_data = load_sp_file(previous_sp_file)

    st.markdown("## Step 3: Upload current month SP file")
    current_sp_file = st.file_uploader(
        "Upload current month SP file (.csv)", type=["csv"], key="curr_sp_upload"
    )
    current_sp_data = load_sp_file(current_sp_file)

    st.markdown("## Step 4: Download debit note calculation")
    if soh_data and previous_sp_data and current_sp_data:
        if st.button("Prepare download"):
            output_bytes = process_debit_note_calculation(
                soh_data, previous_sp_data, current_sp_data
            )
            if output_bytes:
                st.download_button(
                    label="Download debit note calculation",
                    data=output_bytes,
                    file_name="debit_note_calculation.txt",
                    mime="text/plain",
                )
            else:
                st.warning("Processing logic is not implemented yet.")
    else:
        st.info("Upload all three files to enable the download step.")


if __name__ == "__main__":
    main()


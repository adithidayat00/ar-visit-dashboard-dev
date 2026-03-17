import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="AR Visit Optimization", layout="wide")

st.title("AR Visit Route Optimization Dashboard")

# =========================
# FILE UPLOAD
# =========================
file = st.file_uploader("Upload File Excel", type=["xlsx"])

if file is not None:

    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
    except Exception as e:
        st.error(f"Gagal baca file: {e}")
        st.stop()

    required_cols = ["Over", "ARHO", "ARRO", "Kd_Pos", "Saldo"]
    if any(col not in df.columns for col in required_cols):
        st.error("Kolom wajib tidak lengkap")
        st.stop()

    st.success("File berhasil diupload")

    # =========================
    # CLEANING
    # =========================
    df = df[df["Over"].notna()]
    df = df[df["Over"] >= 0]

    # =========================
    # CACHE PROCESSING
    # =========================
    @st.cache_data
    def process_data(df):

        df["Priority"] = df["Saldo"] * df["Over"]

        df_full = df.sort_values(
            by=["Kd_Pos", "Priority"],
            ascending=[True, False]
        ).reset_index(drop=True)

        df_route = df[(df["Over"] >= 8) & (df["Over"] <= 30)]

        df_route = df_route.sort_values(
            by=["Kd_Pos", "Priority"],
            ascending=[True, False]
        ).reset_index(drop=True)

        df_route["Kode_Pos_Cluster"] = df_route["Kd_Pos"]
        df_route["Kode_Pos_Cluster"] = df_route["Kode_Pos_Cluster"].where(
            df_route["Kode_Pos_Cluster"] != df_route["Kode_Pos_Cluster"].shift()
        )

        cols = ["Kode_Pos_Cluster"] + [c for c in df_route.columns if c != "Kode_Pos_Cluster"]
        df_route = df_route[cols]

        return df_full, df_route

    df_full, df_route = process_data(df)

    # =========================
    # SIDEBAR FILTER
    # =========================
    st.sidebar.header("Filter")

    # AUTO SCALE OVER
    min_val = int(df_full["Over"].min())
    max_val = int(df_full["Over"].max())

    min_over, max_over = st.sidebar.slider(
        "Range Over",
        min_val,
        max_val,
        (min_val, min(max_val, 60))
    )

    # MULTI SELECT FILTERS
    arho_list = st.sidebar.multiselect(
        "Filter ARHO",
        options=sorted(df_full["ARHO"].dropna().unique())
    )

    arro_list = st.sidebar.multiselect(
        "Filter ARRO",
        options=sorted(df_full["ARRO"].dropna().unique())
    )

    kdpos_list = st.sidebar.multiselect(
        "Filter Kode Pos",
        options=sorted(df_full["Kd_Pos"].dropna().unique())
    )

    # APPLY FILTER
    df_full = df_full[
        (df_full["Over"] >= min_over) & (df_full["Over"] <= max_over)
    ]

    if arho_list:
        df_full = df_full[df_full["ARHO"].isin(arho_list)]

    if arro_list:
        df_full = df_full[df_full["ARRO"].isin(arro_list)]

    if kdpos_list:
        df_full = df_full[df_full["Kd_Pos"].isin(kdpos_list)]

    # =========================
    # SEARCH
    # =========================
    search = st.text_input("🔍 Search (All Columns)")

    if search:
        mask = df_full.apply(
            lambda col: col.astype(str).str.contains(search, case=False, na=False)
        )
        df_full = df_full[mask.any(axis=1)]

    # =========================
    # KPI
    # =========================
    st.subheader("📊 Summary Dashboard")

    col1, col2 = st.columns(2)
    col1.metric("Total Account", len(df_full))
    col2.metric("Total Saldo", f"{df_full['Saldo'].sum():,.0f}")

    # =========================
    # CHART
    # =========================
    st.subheader("📊 Saldo per Kode Pos")

    chart_data = df_full.groupby("Kd_Pos")["Saldo"].sum().sort_values(ascending=False)
    st.bar_chart(chart_data)

    # =========================
    # EXPORT FUNCTION
    # =========================
    def convert_to_excel(df_full, df_route):

        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book

        df_full.to_excel(writer, index=False, sheet_name='Full_Data')
        ws1 = writer.sheets['Full_Data']

        cluster_col = df_full.columns.get_loc("Kd_Pos")
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})

        start_row = 0
        while start_row < len(df_full):
            kode = df_full.iloc[start_row]["Kd_Pos"]
            end_row = start_row

            while end_row + 1 < len(df_full) and df_full.iloc[end_row+1]["Kd_Pos"] == kode:
                end_row += 1

            ws1.merge_range(start_row+1, cluster_col, end_row+1, cluster_col, kode, bold_center)
            start_row = end_row + 1

        df_route.to_excel(writer, index=False, sheet_name='Rute_Kunjungan')
        ws2 = writer.sheets['Rute_Kunjungan']

        yellow = workbook.add_format({'bg_color': '#FFF59D'})
        orange = workbook.add_format({'bg_color': '#FFCC80'})
        red = workbook.add_format({'bg_color': '#FF8A80'})

        over_col = df_route.columns.get_loc("Over")
        cluster_col = df_route.columns.get_loc("Kode_Pos_Cluster")

        for row in range(len(df_route)):
            val = df_route.iloc[row]["Over"]

            if 8 <= val <= 15:
                ws2.write(row+1, over_col, val, yellow)
            elif 16 <= val <= 22:
                ws2.write(row+1, over_col, val, orange)
            elif 23 <= val <= 30:
                ws2.write(row+1, over_col, val, red)

        start_row = 0
        while start_row < len(df_route):
            kode = df_route.iloc[start_row]["Kd_Pos"]
            end_row = start_row

            while end_row + 1 < len(df_route) and df_route.iloc[end_row+1]["Kd_Pos"] == kode:
                end_row += 1

            ws2.merge_range(start_row+1, cluster_col, end_row+1, cluster_col, kode, bold_center)
            start_row = end_row + 1

        writer.close()
        return output.getvalue()

    excel_file = convert_to_excel(df_full, df_route)

    st.download_button(
        label="⬇️ Download Excel Report",
        data=excel_file,
        file_name=f"AR_Report_{pd.Timestamp.today().date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # =========================
    # EXPANDABLE CLUSTER
    # =========================
    st.subheader("📊 Full Data per Kode Pos")

    grouped = df_full.groupby("Kd_Pos")
    sorted_groups = sorted(grouped, key=lambda x: x[1]["Saldo"].sum(), reverse=True)

    for kode_pos, group in sorted_groups:

        total_account = len(group)
        total_saldo = group["Saldo"].sum()

        with st.expander(f"📍 {kode_pos} | {total_account} Account | Saldo {total_saldo:,.0f}"):

            col1, col2 = st.columns(2)
            col1.metric("Account", total_account)
            col2.metric("Saldo", f"{total_saldo:,.0f}")

            st.markdown("🔥 Top Priority")
            top_group = group.sort_values(by="Priority", ascending=False).head(5)
            st.dataframe(top_group, use_container_width=True)

            st.markdown("📋 All Data")
            st.dataframe(group, use_container_width=True)

    # =========================
    # ROUTE TABLE
    # =========================
    st.subheader("🚗 Rute Kunjungan")

    def highlight_over(val):
        if 8 <= val <= 15:
            return 'background-color: #FFF59D'
        elif 16 <= val <= 22:
            return 'background-color: #FFCC80'
        elif 23 <= val <= 30:
            return 'background-color: #FF8A80'
        return ''

    styled_route = df_route.style.map(highlight_over, subset=["Over"])

    st.dataframe(styled_route, use_container_width=True)
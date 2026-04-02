import streamlit as st
import pandas as pd
import plotly.express as px

# 1. ตั้งค่าหน้าจอเว็บไซต์
st.set_page_config(page_title="Student Data Dashboard", layout="wide")
st.title("📊 ระบบวิเคราะห์ข้อมูลนักศึกษา")

# --- ฟังก์ชันโหลดข้อมูลพร้อม Caching (ช่วยให้เว็บไม่หน่วงเวลาเปลี่ยนกราฟ) ---
@st.cache_data(show_spinner="กำลังโหลดข้อมูล...")
def load_data(source_type, file_upload, url_link):
    if source_type == "อัปโหลดไฟล์จากเครื่อง" and file_upload is not None:
        if file_upload.name.endswith('.csv'):
            return pd.read_csv(file_upload)
        else:
            return pd.read_excel(file_upload)
            
    elif source_type == "ระบุ URL" and url_link:
        if "docs.google.com/spreadsheets" in url_link and "/edit" in url_link:
            clean_url = url_link.split("/edit")[0] + "/export?format=csv"
        else:
            clean_url = url_link
        return pd.read_csv(clean_url)
        
    return None
# --------------------------------------------------------------------------

# 2. เมนูด้านซ้าย Sidebar สำหรับรับข้อมูล
st.sidebar.header("📥 นำเข้าข้อมูลดิบ")
data_source = st.sidebar.radio("เลือกวิธีนำเข้าข้อมูล:", ("อัปโหลดไฟล์จากเครื่อง", "ระบุ URL"))

uploaded_file = None
url_input = ""

if data_source == "อัปโหลดไฟล์จากเครื่อง":
    uploaded_file = st.sidebar.file_uploader("เลือกไฟล์ CSV หรือ Excel", type=["csv", "xlsx"])
elif data_source == "ระบุ URL":
    url_input = st.sidebar.text_input("วางลิงก์จาก Google Sheets หรือไฟล์ CSV ที่นี่")

# โหลดข้อมูลผ่านฟังก์ชัน
df = None
try:
    if uploaded_file or url_input:
        df = load_data(data_source, uploaded_file, url_input)
except Exception as e:
    st.sidebar.error(f"❌ ไม่สามารถดึงข้อมูลได้: ({e})")

# 3. ส่วนแสดงผลหลักและการตั้งค่ากราฟ
if df is not None:
    st.success("✅ โหลดข้อมูลเข้าสู่ระบบสำเร็จ!")
    
    with st.expander("👀 คลิกเพื่อดูตารางข้อมูลดิบ (Data Table)"):
        st.dataframe(df.head(50)) # โชว์แค่ 50 บรรทัดแรกกันเว็บค้าง

    st.markdown("---")
    st.subheader("⚙️ ปรับแต่งกราฟ")
    
    chart_list = ["Bar Chart", "Pie Chart", "Histogram", "Line Chart", "Scatter Plot", "Box Plot", "Stacked Bar Chart"]
    chart_type = st.selectbox("เลือกประเภทกราฟ", chart_list)

    st.markdown("---")
    
    # 4. ส่วนการสร้างกราฟด้วย Plotly
    try:
        # กราฟตัวแปรเดียว
        if chart_type in ["Bar Chart", "Pie Chart", "Histogram"]:
            selected_col = st.selectbox("เลือกข้อมูลที่ต้องการวิเคราะห์", df.columns)
            st.write(f"**กราฟแสดง: {chart_type} ของ {selected_col}**")
            
            if chart_type == "Bar Chart":
                val_counts = df[selected_col].value_counts().reset_index()
                val_counts.columns = [selected_col, 'จำนวน']
                fig = px.bar(val_counts, x=selected_col, y='จำนวน', color=selected_col)
            elif chart_type == "Pie Chart":
                val_counts = df[selected_col].value_counts().reset_index()
                val_counts.columns = [selected_col, 'จำนวน']
                fig = px.pie(val_counts, names=selected_col, values='จำนวน', hole=0.3)
            elif chart_type == "Histogram":
                fig = px.histogram(df, x=selected_col, color=selected_col)
                
            st.plotly_chart(fig, use_container_width=True)

        # กราฟสองตัวแปร
        elif chart_type in ["Scatter Plot", "Line Chart", "Box Plot"]:
            col1, col2 = st.columns(2)
            with col1:
                x_col = st.selectbox("เลือกข้อมูลแกน X (แนวนอน)", df.columns)
            with col2:
                y_col = st.selectbox("เลือกข้อมูลแกน Y (แนวตั้ง - ควรเป็นตัวเลข)", df.columns)
                
            st.write(f"**กราฟแสดง: ความสัมพันธ์ระหว่าง {x_col} และ {y_col}**")
            
            if chart_type == "Scatter Plot":
                fig = px.scatter(df, x=x_col, y=y_col, color=x_col)
            elif chart_type == "Line Chart":
                fig = px.line(df, x=x_col, y=y_col)
            elif chart_type == "Box Plot":
                fig = px.box(df, x=x_col, y=y_col, color=x_col)
                
            st.plotly_chart(fig, use_container_width=True)

        # กราฟแท่งซ้อน
        elif chart_type == "Stacked Bar Chart":
            col1, col2 = st.columns(2)
            with col1:
                main_group = st.selectbox("เลือกข้อมูลกลุ่มหลัก (แกน X)", df.columns)
            with col2:
                sub_group = st.selectbox("เลือกข้อมูลกลุ่มย่อย (แบ่งสี)", df.columns)
                
            st.write(f"**กราฟแสดง: {main_group} แบ่งสัดส่วนตาม {sub_group}**")
            
            grouped_df = df.groupby([main_group, sub_group]).size().reset_index(name='จำนวน')
            fig = px.bar(grouped_df, x=main_group, y='จำนวน', color=sub_group, barmode='stack')
            
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"⚠️ ไม่สามารถสร้างกราฟได้: โปรดตรวจสอบชนิดข้อมูลให้ตรงกับประเภทกราฟ")

else:
    st.info("👈 กรุณานำเข้าข้อมูลจากเมนูด้านซ้ายเพื่อเริ่มต้นการทำงาน")
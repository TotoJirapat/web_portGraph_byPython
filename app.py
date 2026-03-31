import streamlit as st
import pandas as pd
import plotly.express as px

# 1 ตั้งค่าหน้าจอเว็บไซต์
st.set_page_config(page_title="Student Data Dashboard", layout="wide")
st.title("📊 ระบบวิเคราะห์ข้อมูลนักศึกษา")

# 2 เมนูด้านซ้าย Sidebar สำหรับรับข้อมูล
st.sidebar.header("📥 นำเข้าข้อมูล")
data_source = st.sidebar.radio("เลือกวิธีนำเข้าข้อมูล:", ("อัปโหลดไฟล์จากเครื่อง", "ระบุ URL"))

df = None 

try:
        if data_source == "อัปโหลดไฟล์จากเครื่อง":
            uploaded_file = st.sidebar.file_uploader("เลือกไฟล์ CSV หรือ Excel", type=["csv", "xlsx"])
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                    
        elif data_source == "ระบุ URL":
            url = st.sidebar.text_input("วางลิงก์จาก Google Sheets หรือไฟล์ CSV ที่นี่")
            if url:
                # แปลงลิงก์ Google Sheets อัตโนมัติ
                if "docs.google.com/spreadsheets" in url and "/edit" in url:
                    clean_url = url.split("/edit")[0] + "/export?format=csv"
                    st.sidebar.success("✌️ ระบบแปลงลิงก์ Google Sheets อัตโนมัติทำงานแล้ว!")
                else:
                    clean_url = url 
                
                # Pandas อ่านจากลิงก์ที่แปลงเสร็จแล้ว
                df = pd.read_csv(clean_url)
                
    # คำสั่ง except จะจับ Error ทั้งจากการอัปโหลดไฟล์และ URL
except Exception as e:
    st.sidebar.error(f"❌ ไม่สามารถดึงข้อมูลได้: โปรดตรวจสอบลิงก์หรือไฟล์อีกครั้ง ({e})")

# 3 ส่วนแสดงผลหลักและการตั้งค่ากราฟ
if df is not None:
    st.success("✅ โหลดข้อมูลสำเร็จ!")
    
    with st.expander("👀 คลิกเพื่อดูตารางข้อมูลดิบ"):
        st.dataframe(df.head(10)) 

    st.markdown("---")
    st.subheader("⚙️ ปรับแต่งกราฟ")
    
    # เพิ่มตัวเลือกกราฟใหม่ๆ เข้าไป
    chart_list = [
        "Bar Chart", "Pie Chart", "Histogram", 
        "Line Chart", "Scatter Plot", "Box Plot", "Stacked Bar Chart"
    ]
    chart_type = st.selectbox("เลือกประเภทกราฟ", chart_list)

    st.markdown("---")
    
    # 4 ส่วนตรรกะการสร้างกราฟ (แยกตามจำนวนคอลัมน์ที่กราฟต้องการ)
    try:
        # กราฟที่ใช้ข้อมูล 1 คอลัมน์ (นับจำนวน/กระจายตัว)
        if chart_type in ["Bar Chart", "Pie Chart", "Histogram"]:
            selected_col = st.selectbox("เลือกข้อมูลที่ต้องการวิเคราะห์", df.columns)
            st.subheader(f"📈 กราฟแสดง: {chart_type} ของ {selected_col}")
            
            if chart_type == "Bar Chart":
                val_counts = df[selected_col].value_counts().reset_index()
                val_counts.columns = [selected_col, 'จำนวน']
                fig = px.bar(val_counts, x=selected_col, y='จำนวน', color=selected_col)
            elif chart_type == "Pie Chart":
                val_counts = df[selected_col].value_counts().reset_index()
                val_counts.columns = [selected_col, 'จำนวน']
                fig = px.pie(val_counts, names=selected_col, values='จำนวน', hole=0.3)
            elif chart_type == "Histogram":
                fig = px.histogram(df, x=selected_col, nbins=20, color=selected_col)
                
            st.plotly_chart(fig, use_container_width=True)

        # กราฟที่ต้องการข้อมูล 2 คอลัมน์ (แกน X และ Y)
        elif chart_type in ["Scatter Plot", "Line Chart", "Box Plot"]:
            col1, col2 = st.columns(2)
            with col1:
                x_col = st.selectbox("เลือกข้อมูลแกน X (แนวนอน)", df.columns)
            with col2:
                y_col = st.selectbox("เลือกข้อมูลแกน Y (แนวตั้ง - ควรเป็นตัวเลข)", df.columns)
                
            st.subheader(f"📈 กราฟแสดง: ความสัมพันธ์ระหว่าง {x_col} และ {y_col}")
            
            if chart_type == "Scatter Plot":
                # เหมาะสำหรับดูความสัมพันธ์ เช่น น้ำหนัก vs ส่วนสูง
                fig = px.scatter(df, x=x_col, y=y_col, color=x_col)
            elif chart_type == "Line Chart":
                # เหมาะสำหรับดูแนวโน้ม
                fig = px.line(df, x=x_col, y=y_col)
            elif chart_type == "Box Plot":
                # เหมาะสำหรับดูการกระจายตัว เช่น เกรดแยกตามชั้นปี
                fig = px.box(df, x=x_col, y=y_col, color=x_col)
                
            st.plotly_chart(fig, use_container_width=True)

        # กราฟแท่งแบบซ้อนทับ (ต้องการแกน X และตัวแบ่งสี)
        elif chart_type == "Stacked Bar Chart":
            col1, col2 = st.columns(2)
            with col1:
                main_group = st.selectbox("เลือกข้อมูลกลุ่มหลัก (แกน X)", df.columns)
            with col2:
                sub_group = st.selectbox("เลือกข้อมูลกลุ่มย่อย (เพื่อแบ่งสี)", df.columns)
                
            st.subheader(f"📈 กราฟแสดง: {main_group} แบ่งสัดส่วนตาม {sub_group}")
            
            # ต้องจับกลุ่มนับจำนวนก่อนสร้าง Stacked Bar
            grouped_df = df.groupby([main_group, sub_group]).size().reset_index(name='จำนวน')
            fig = px.bar(grouped_df, x=main_group, y='จำนวน', color=sub_group, barmode='stack')
            
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"⚠️ ไม่สามารถสร้างกราฟได้: โปรดตรวจสอบว่าชนิดของข้อมูลเหมาะสมกับกราฟหรือไม่ (เช่น Scatter Plot ต้องการข้อมูลที่เป็นตัวเลข)")

else:
    st.info("👈 กรุณานำเข้าข้อมูลจากเมนูด้านซ้ายเพื่อเริ่มต้นการทำงาน")

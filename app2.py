# -*- coding: utf-8 -*-

import os
import uuid
from io import BytesIO

import pandas as pd
import plotly.express as px
import requests
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"csv", "xlsx"}

# cache in memory for faster loading / chart rendering
DATA_CACHE = {}
CHART_CACHE = {}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_storage):
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(save_path)
    return save_path


def normalize_google_sheets_url(url_link: str) -> str:
    url_link = (url_link or "").strip()

    if "docs.google.com/spreadsheets" in url_link:
        if "/export?format=csv" in url_link:
            return url_link
        if "/edit" in url_link:
            return url_link.split("/edit")[0] + "/export?format=csv"
        if "/spreadsheets/d/" in url_link:
            base = url_link.split("?")[0].rstrip("/")
            return base + "/export?format=csv"

    return url_link


def load_data_from_path(file_path):
    if file_path.lower().endswith(".csv"):
        return pd.read_csv(file_path, encoding="utf-8-sig")
    if file_path.lower().endswith(".xlsx"):
        return pd.read_excel(file_path)
    return None


def load_data_from_url(url_link):
    clean_url = normalize_google_sheets_url(url_link)

    response = requests.get(clean_url, timeout=30)
    response.raise_for_status()

    # Try XLSX first if URL/content looks like Excel
    content_type = response.headers.get("Content-Type", "").lower()
    if clean_url.lower().endswith(".xlsx") or "spreadsheetml" in content_type:
        return pd.read_excel(BytesIO(response.content))

    # CSV: read bytes directly to avoid Thai encoding issues
    try:
        return pd.read_csv(BytesIO(response.content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return pd.read_csv(BytesIO(response.content), encoding="cp874")
        except Exception:
            return pd.read_csv(BytesIO(response.content))


def get_data_cache_key():
    file_path = session.get("data_file_path")
    data_url = session.get("data_url")

    if file_path:
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            mtime = 0
        return f"file:{file_path}:{mtime}"

    if data_url:
        return f"url:{normalize_google_sheets_url(data_url)}"

    return None


def get_current_df():
    cache_key = get_data_cache_key()
    if not cache_key:
        return None, None

    if cache_key in DATA_CACHE:
        return DATA_CACHE[cache_key], cache_key

    try:
        if cache_key.startswith("file:"):
            file_path = session.get("data_file_path")
            df = load_data_from_path(file_path)
        else:
            data_url = session.get("data_url")
            df = load_data_from_url(data_url)

        if df is not None:
            DATA_CACHE[cache_key] = df
        return df, cache_key
    except Exception as e:
        flash(f"❌ ไม่สามารถอ่านข้อมูลได้: {e}")
        return None, None


def data_preview_html(df, rows=20):
    preview = df.head(rows).copy()
    return preview.to_html(
        classes="table table-striped table-hover table-bordered table-sm align-middle mb-0",
        index=False,
        border=0
    )


def summarize_dataframe(df):
    total_rows = len(df)
    total_cols = len(df.columns)
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    return total_rows, total_cols, missing_cells, duplicate_rows


def sample_for_speed(df, max_rows=5000):
    if len(df) > max_rows:
        return df.sample(n=max_rows, random_state=42)
    return df


def build_chart(df, chart_type, selected_col=None, x_col=None, y_col=None, main_group=None, sub_group=None):
    # fast mode is always on
    cache_key = (
        id(df),
        len(df),
        chart_type,
        selected_col,
        x_col,
        y_col,
        main_group,
        sub_group
    )

    if cache_key in CHART_CACHE:
        return CHART_CACHE[cache_key]

    chart_df = df

    # speed mode for large data
    if chart_type in {"Scatter Plot", "Line Chart", "Box Plot"}:
        chart_df = sample_for_speed(df, max_rows=5000)
    elif chart_type == "Histogram":
        chart_df = sample_for_speed(df, max_rows=8000)
    elif chart_type == "Stacked Bar Chart":
        chart_df = sample_for_speed(df, max_rows=10000)

    fig = None

    if chart_type == "Bar Chart":
        s = chart_df[selected_col].astype(str).fillna("NaN")
        counts = s.value_counts(dropna=False).reset_index()
        counts.columns = [selected_col, "จำนวน"]
        fig = px.bar(counts, x=selected_col, y="จำนวน", color=selected_col, title=f"Bar Chart: {selected_col}")

    elif chart_type == "Pie Chart":
        s = chart_df[selected_col].astype(str).fillna("NaN")
        counts = s.value_counts(dropna=False).reset_index()
        counts.columns = [selected_col, "จำนวน"]
        fig = px.pie(counts, names=selected_col, values="จำนวน", hole=0.35, title=f"Pie Chart: {selected_col}")

    elif chart_type == "Histogram":
        fig = px.histogram(chart_df, x=selected_col, nbins=30, title=f"Histogram: {selected_col}")

    elif chart_type == "Scatter Plot":
        tmp = chart_df[[x_col, y_col]].dropna()
        fig = px.scatter(tmp, x=x_col, y=y_col, title=f"Scatter Plot: {x_col} vs {y_col}")

    elif chart_type == "Line Chart":
        tmp = chart_df[[x_col, y_col]].dropna()
        fig = px.line(tmp, x=x_col, y=y_col, title=f"Line Chart: {x_col} vs {y_col}")

    elif chart_type == "Box Plot":
        tmp = chart_df[[x_col, y_col]].dropna()
        fig = px.box(tmp, x=x_col, y=y_col, title=f"Box Plot: {x_col} vs {y_col}")

    elif chart_type == "Stacked Bar Chart":
        tmp = chart_df[[main_group, sub_group]].dropna()
        grouped_df = tmp.groupby([main_group, sub_group], observed=True).size().reset_index(name="จำนวน")
        fig = px.bar(
            grouped_df,
            x=main_group,
            y="จำนวน",
            color=sub_group,
            barmode="stack",
            title=f"Stacked Bar Chart: {main_group} by {sub_group}"
        )

    if fig is not None:
        fig.update_layout(
            template="plotly_white",
            height=560,
            margin=dict(l=20, r=20, t=60, b=20),
            legend_title_text=""
        )
        chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    else:
        chart_html = None

    CHART_CACHE[cache_key] = chart_html
    return chart_html


TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Data Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {
            --sidebar-bg: #ffffff;
            --sidebar-border: #e5e7eb;
            --sidebar-soft: #f8fafc;
            --main-bg: #f5f7fb;
            --card-bg: #ffffff;
            --card-border: #e7ecf4;
            --accent: #4f8cff;
            --accent-2: #7c5cff;
            --text-dark: #1f2a44;
            --text-muted: #6b7280;
        }

        body {
            background: var(--main-bg);
            font-family: Inter, Segoe UI, Arial, sans-serif;
            color: #111827;
        }

        .sidebar-panel {
            position: sticky;
            top: 16px;
            background: var(--sidebar-bg);
            color: #111827;
            border: 1px solid var(--sidebar-border);
            border-radius: 22px;
            padding: 22px;
            min-height: calc(100vh - 32px);
            box-shadow: 0 10px 30px rgba(31, 42, 68, 0.06);
        }

        .sidebar-title {
            font-weight: 800;
            font-size: 1.2rem;
            margin-bottom: 0.4rem;
            color: var(--text-dark);
        }

        .sidebar-subtitle {
            color: var(--text-muted);
            font-size: 0.95rem;
        }

        .sidebar-label {
            font-weight: 700;
            margin-bottom: 0.4rem;
            color: var(--text-dark);
        }

        .sidebar-panel .form-control,
        .sidebar-panel .form-select {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d8dee9;
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
        }

        .sidebar-panel .form-control::placeholder {
            color: #9ca3af;
        }

        .sidebar-panel .form-control:focus,
        .sidebar-panel .form-select:focus {
            box-shadow: 0 0 0 0.2rem rgba(79, 140, 255, 0.12);
            border-color: rgba(79, 140, 255, 0.9);
        }

        .main-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: 0 10px 30px rgba(31, 42, 68, 0.06);
        }

        .hero-card {
            background: linear-gradient(135deg, #ffffff, #f6f9ff);
            border: 1px solid var(--card-border);
            border-radius: 22px;
            box-shadow: 0 10px 30px rgba(31, 42, 68, 0.06);
        }

        .section-title {
            color: var(--text-dark);
            font-weight: 800;
            letter-spacing: -0.02em;
        }

        .metric-box {
            border-radius: 18px;
            border: 1px solid var(--card-border);
            background: #fff;
            padding: 16px 18px;
            height: 100%;
        }

        .metric-label {
            font-size: 0.9rem;
            color: #6b7280;
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 1.35rem;
            font-weight: 800;
            color: var(--text-dark);
        }

        details.streamlit-like {
            border: 1px solid var(--card-border);
            border-radius: 18px;
            background: #fff;
            overflow: hidden;
        }

        details.streamlit-like > summary {
            cursor: pointer;
            list-style: none;
            padding: 16px 18px;
            font-weight: 800;
            color: var(--text-dark);
            background: linear-gradient(180deg, #ffffff, #f8fbff);
            border-bottom: 1px solid var(--card-border);
        }

        details.streamlit-like[open] > summary {
            border-bottom: 1px solid var(--card-border);
        }

        details.streamlit-like .details-body {
            padding: 18px;
        }

        .table-responsive {
            max-height: 520px;
            overflow: auto;
            border-radius: 14px;
        }

        .table {
            margin-bottom: 0;
            font-size: 0.93rem;
        }

        .table thead th {
            position: sticky;
            top: 0;
            background: #f7faff;
            z-index: 1;
        }

        .muted-small {
            color: #6b7280;
            font-size: 0.93rem;
        }

        .pill {
            display: inline-block;
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
            background: rgba(79, 140, 255, 0.12);
            color: #2563eb;
            font-weight: 700;
            font-size: 0.85rem;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            border: none;
        }

        .btn-primary:hover {
            opacity: 0.95;
        }

        .chart-panel {
            overflow-x: auto;
        }

        .light-text {
            color: #111827;
        }

        .sidebar-card {
            background: var(--sidebar-soft);
            border: 1px solid #e5e7eb;
            border-radius: 18px;
        }

        .small-note {
            color: #6b7280;
            font-size: 0.85rem;
        }

        @media (max-width: 991px) {
            .sidebar-panel {
                position: static;
                min-height: auto;
            }
        }
    </style>
</head>
<body>
<div class="container-fluid py-3 px-3 px-lg-4">
    <div class="row g-4">
        <!-- Sidebar -->
        <div class="col-12 col-lg-3">
            <div class="sidebar-panel">
                <div class="sidebar-title">📊 Student Dashboard</div>

                {% with messages = get_flashed_messages() %}
                  {% if messages %}
                    {% for message in messages %}
                      <div class="alert alert-warning py-2">{{ message }}</div>
                    {% endfor %}
                  {% endif %}
                {% endwith %}

                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="load_data">

                    <div class="mb-3">
                        <label class="sidebar-label">เลือกวิธีนำเข้าข้อมูล</label>
                        <select name="data_source" class="form-select" id="data_source" onchange="toggleSourceInput()">
                            <option value="upload" {% if data_source == 'upload' %}selected{% endif %}>อัปโหลดไฟล์จากเครื่อง</option>
                            <option value="url" {% if data_source == 'url' %}selected{% endif %}>ระบุ URL</option>
                        </select>
                    </div>

                    <div class="mb-3" id="upload_box">
                        <label class="sidebar-label">เลือกไฟล์ CSV หรือ Excel</label>
                        <input type="file" name="file_upload" class="form-control" accept=".csv,.xlsx">
                    </div>

                    <div class="mb-3" id="url_box" style="display:none;">
                        <label class="sidebar-label">วางลิงก์ Google Sheets หรือไฟล์ CSV</label>
                        <input type="text" name="url_input" class="form-control" placeholder="https://...">
                    </div>

                    <button type="submit" class="btn btn-primary w-100 fw-bold">Load Data</button>
                </form>

                <div class="mt-3 d-grid">
                    <form method="POST">
                        <input type="hidden" name="action" value="clear_data">
                        <button type="submit" class="btn btn-outline-secondary w-100 fw-bold">Clear Data</button>
                    </form>
                </div>

                <hr>

                {% if df_loaded %}
                    <div class="sidebar-card mb-3 p-3">
                        <div class="pill mb-2">Dataset Ready</div>
                        <div class="fw-bold light-text">✅ โหลดข้อมูลสำเร็จ</div>
                        <div class="small-note mt-1">แถว: {{ row_count }} | คอลัมน์: {{ col_count }}</div>
                    </div>

                    <div class="sidebar-card mb-3 p-3">
                        <div class="fw-bold light-text mb-2">สถิติข้อมูลเบื้องต้น</div>
                        <div class="small-note">Missing cells: {{ missing_cells }}</div>
                        <div class="small-note">Duplicate rows: {{ duplicate_rows }}</div>
                    </div>

                    <div class="small-note">
                        หมายเหตุ: ตารางด้านล่างจะแสดงแค่ตัวอย่างข้อมูลเพื่อให้เว็บทำงานเร็วขึ้น
                    </div>
                {% else %}
                    <div class="alert alert-info mb-0">
                        กรุณานำเข้าข้อมูลเพื่อเริ่มต้น
                    </div>
                {% endif %}
            </div>
        </div>

        <!-- Main -->
        <div class="col-12 col-lg-9">
            <div class="hero-card p-4 mb-4">
                <h2 class="section-title mb-1">📊 ระบบวิเคราะห์ข้อมูลนักศึกษา</h2>
            </div>

            {% if df_loaded %}
                <div class="row g-3 mb-4">
                    <div class="col-6 col-xl-3">
                        <div class="metric-box">
                            <div class="metric-label">จำนวนแถว</div>
                            <div class="metric-value">{{ row_count }}</div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="metric-box">
                            <div class="metric-label">จำนวนคอลัมน์</div>
                            <div class="metric-value">{{ col_count }}</div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="metric-box">
                            <div class="metric-label">Missing Cells</div>
                            <div class="metric-value">{{ missing_cells }}</div>
                        </div>
                    </div>
                    <div class="col-6 col-xl-3">
                        <div class="metric-box">
                            <div class="metric-label">Duplicate Rows</div>
                            <div class="metric-value">{{ duplicate_rows }}</div>
                        </div>
                    </div>
                </div>

                <div class="main-card mb-4">
                    <details class="streamlit-like">
                        <summary>👀 คลิกเพื่อดูตารางข้อมูลตัวอย่าง (Preview)</summary>
                        <div class="details-body">
                            <div class="muted-small mb-3">
                                แสดงเพียง {{ preview_rows }} แถวแรกเท่านั้น เพื่อให้หน้าเว็บไม่หน่วง
                            </div>
                            <div class="table-responsive">
                                {{ table_html | safe }}
                            </div>
                        </div>
                    </details>
                </div>

                <div class="main-card p-4 mb-4">
                    <h5 class="section-title mb-3">⚙️ ปรับแต่งกราฟ</h5>

                    <form method="POST">
                        <input type="hidden" name="action" value="create_chart">

                        <div class="row g-3 mb-3">
                            <div class="col-md-4">
                                <label class="form-label fw-bold">เลือกประเภทกราฟ</label>
                                <select class="form-select" name="chart_type" id="chart_type" onchange="toggleChartInputs()">
                                    {% for item in chart_list %}
                                        <option value="{{ item }}" {% if chart_type == item %}selected{% endif %}>{{ item }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>

                        <div id="single_col_box" class="row g-3 mb-3" style="display:none;">
                            <div class="col-md-6">
                                <label class="form-label fw-bold">เลือกข้อมูลที่ต้องการวิเคราะห์</label>
                                <select class="form-select" name="selected_col">
                                    {% for col in columns %}
                                        <option value="{{ col }}" {% if selected_col == col %}selected{% endif %}>{{ col }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>

                        <div id="two_col_box" class="row g-3 mb-3" style="display:none;">
                            <div class="col-md-6">
                                <label class="form-label fw-bold">เลือกข้อมูลแกน X</label>
                                <select class="form-select" name="x_col">
                                    {% for col in columns %}
                                        <option value="{{ col }}" {% if x_col == col %}selected{% endif %}>{{ col }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold">เลือกข้อมูลแกน Y</label>
                                <select class="form-select" name="y_col">
                                    {% for col in columns %}
                                        <option value="{{ col }}" {% if y_col == col %}selected{% endif %}>{{ col }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>

                        <div id="stacked_box" class="row g-3 mb-3" style="display:none;">
                            <div class="col-md-6">
                                <label class="form-label fw-bold">เลือกข้อมูลกลุ่มหลัก</label>
                                <select class="form-select" name="main_group">
                                    {% for col in columns %}
                                        <option value="{{ col }}" {% if main_group == col %}selected{% endif %}>{{ col }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold">เลือกข้อมูลกลุ่มย่อย</label>
                                <select class="form-select" name="sub_group">
                                    {% for col in columns %}
                                        <option value="{{ col }}" {% if sub_group == col %}selected{% endif %}>{{ col }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>

                        <button type="submit" class="btn btn-primary fw-bold">สร้างกราฟ</button>
                    </form>
                </div>

                <div class="main-card p-4">
                    <h5 class="section-title mb-3">📈 ผลลัพธ์กราฟ</h5>
                    {% if chart_html %}
                        <div class="chart-panel">
                            {{ chart_html | safe }}
                        </div>
                    {% else %}
                        <div class="alert alert-secondary mb-0">ยังไม่มีกกราฟแสดง</div>
                    {% endif %}
                </div>
            {% else %}
                <div class="main-card p-4">
                    <div class="alert alert-info mb-0">
                        👈 กรุณานำเข้าข้อมูลจากเมนูด้านซ้ายเพื่อเริ่มต้นการทำงาน
                    </div>
                </div>
            {% endif %}
        </div>
    </div>
</div>

<script>
function toggleSourceInput() {
    const source = document.getElementById("data_source").value;
    document.getElementById("upload_box").style.display = source === "upload" ? "block" : "none";
    document.getElementById("url_box").style.display = source === "url" ? "block" : "none";
}

function toggleChartInputs() {
    const chartType = document.getElementById("chart_type").value;

    const single = ["Bar Chart", "Pie Chart", "Histogram"];
    const two = ["Scatter Plot", "Line Chart", "Box Plot"];
    const stacked = ["Stacked Bar Chart"];

    document.getElementById("single_col_box").style.display = single.includes(chartType) ? "flex" : "none";
    document.getElementById("two_col_box").style.display = two.includes(chartType) ? "flex" : "none";
    document.getElementById("stacked_box").style.display = stacked.includes(chartType) ? "flex" : "none";
}

window.addEventListener("load", function() {
    toggleSourceInput();
    toggleChartInputs();
});
</script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    chart_list = ["Bar Chart", "Pie Chart", "Histogram", "Line Chart", "Scatter Plot", "Box Plot", "Stacked Bar Chart"]

    df = None
    chart_html = None
    table_html = None
    columns = []
    df_loaded = False
    row_count = 0
    col_count = 0
    missing_cells = 0
    duplicate_rows = 0
    preview_rows = 20

    data_source = session.get("data_source", "upload")
    chart_type = request.form.get("chart_type", "Bar Chart")
    selected_col = request.form.get("selected_col", "")
    x_col = request.form.get("x_col", "")
    y_col = request.form.get("y_col", "")
    main_group = request.form.get("main_group", "")
    sub_group = request.form.get("sub_group", "")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "load_data":
            source = request.form.get("data_source", "upload")
            session["data_source"] = source

            try:
                # clear old chart cache whenever new data loads
                CHART_CACHE.clear()

                if source == "upload":
                    file_upload = request.files.get("file_upload")
                    if file_upload and file_upload.filename:
                        if not allowed_file(file_upload.filename):
                            flash("รองรับเฉพาะไฟล์ CSV หรือ XLSX")
                            return redirect(url_for("index"))

                        saved_path = save_uploaded_file(file_upload)
                        session["data_file_path"] = saved_path
                        session.pop("data_url", None)
                    else:
                        flash("กรุณาเลือกไฟล์ก่อน")
                        return redirect(url_for("index"))

                elif source == "url":
                    url_input = request.form.get("url_input", "").strip()
                    if not url_input:
                        flash("กรุณาใส่ URL ก่อน")
                        return redirect(url_for("index"))

                    session["data_url"] = url_input
                    session.pop("data_file_path", None)

                return redirect(url_for("index"))

            except Exception as e:
                flash(f"ไม่สามารถโหลดข้อมูลได้: {e}")
                return redirect(url_for("index"))

        elif action == "clear_data":
            session.clear()
            DATA_CACHE.clear()
            CHART_CACHE.clear()
            return redirect(url_for("index"))

    # load current dataset
    df, cache_key = get_current_df()

    try:
        if df is not None:
            df_loaded = True
            columns = list(df.columns)
            row_count, col_count, missing_cells, duplicate_rows = summarize_dataframe(df)
            table_html = data_preview_html(df, rows=preview_rows)

            # default selection
            if not selected_col and columns:
                selected_col = columns[0]
            if not x_col and columns:
                x_col = columns[0]
            if not y_col and len(columns) > 1:
                y_col = columns[1]
            if not main_group and columns:
                main_group = columns[0]
            if not sub_group and len(columns) > 1:
                sub_group = columns[1]

            if request.method == "POST" and request.form.get("action") == "create_chart":
                try:
                    chart_html = build_chart(
                        df=df,
                        chart_type=chart_type,
                        x_col=x_col,
                        y_col=y_col,
                        main_group=main_group,
                        sub_group=sub_group,
                        selected_col=selected_col
                    )
                    if chart_html is None:
                        flash("ไม่สามารถสร้างกราฟได้")
                except Exception as e:
                    flash(f"⚠️ ไม่สามารถสร้างกราฟได้: {e}")

    except Exception as e:
        flash(f"❌ ไม่สามารถประมวลผลข้อมูลได้: {e}")

    return render_template_string(
        TEMPLATE,
        df_loaded=df_loaded,
        table_html=table_html,
        chart_html=chart_html,
        columns=columns,
        chart_list=chart_list,
        chart_type=chart_type,
        selected_col=selected_col,
        x_col=x_col,
        y_col=y_col,
        main_group=main_group,
        sub_group=sub_group,
        row_count=row_count,
        col_count=col_count,
        missing_cells=missing_cells,
        duplicate_rows=duplicate_rows,
        preview_rows=preview_rows,
        data_source=data_source
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

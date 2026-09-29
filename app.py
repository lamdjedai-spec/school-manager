from flask import Flask, render_template_string, request, redirect, url_for, flash, session, send_file, jsonify
import pandas as pd
import numpy as np
import io
import json
import os
import re

app = Flask(__name__)
app.secret_key = "teacher_secret_key_2026"

DATA_FILE = "data.json"

WILAYAS = [
    "01 - أدرار", "02 - الشلف", "03 - الأغواط", "04 - أم البواقي", "05 - باتنة", 
    "06 - بجاية", "07 - بسكرة", "08 - بشار", "09 - البليدة", "10 - البويرة",
    "11 - تمنراست", "12 - تبسة", "13 - تلمسان", "14 - تيارت", "15 - تيزي وزو",
    "16 - الجزائر", "17 - الجلفة", "18 - جيجل", "19 - سطيف", "20 - سعيدة",
    "21 - سكيكدة", "22 - سيدي بلعباس", "23 - عنابة", "24 - قالمة", "25 - قسنطينة",
    "26 - المدية", "27 - مستغانم", "28 - المسيلة", "29 - معسكر", "30 - ورقلة",
    "31 - وهران", "32 - البيض", "33 - إليزي", "34 - برج بوعريريج", "35 - بومرداس",
    "36 - الطارف", "37 - تندوف", "38 - تسمسيلت", "39 - الوادي", "40 - خنشلة",
    "41 - سوق أهراس", "42 - تيبازة", "43 - ميلة", "44 - عين الدفلى", "45 - النعامة",
    "46 - عين تموشنت", "47 - غرداية", "48 - غليزان", "49 - المغير", "50 - المنيعة",
    "51 - أولاد جلال", "52 - برج باجي مختار", "53 - بني عباس", "54 - تيميمون",
    "55 - تقرت", "56 - جانت", "57 - عين صالح", "58 - عين قزام"
]

CRITERIA_INFO = {
    "behavior": {"label": "السلوك (3ن)", "weight": 3.0},
    "absences": {"label": "الغيابات والتأخرات (3ن)", "weight": 3.0},
    "tools": {"label": "إحضار الأدوات (3ن)", "weight": 3.0},
    "notebook": {"label": "تنظيم الكراس (3ن)", "weight": 3.0},
    "participation": {"label": "المشاركة (3ن)", "weight": 3.0},
    "work_indiv": {"label": "العمل الفردي (3ن)", "weight": 3.0},
    "work_group": {"label": "العمل الجماعي (1ن)", "weight": 1.0},
    "initiative": {"label": "المبادرة والإبداع (1ن)", "weight": 1.0}
}

DEVOIR_MAP = {"A": 1.0, "B": 0.75, "C": 0.45, "D": 0.25}

auth_credentials = {
    "username": "admin",
    "password": "123"
}

teacher_info = {
    "wilaya": "16 - الجزائر",
    "school": "",
    "season": "2025/2026",
    "teacher_name": "",
    "term": "الفصل الأول",
    "sessions_count": 4,
    "classes": []
}

students_db = {}

def load_data():
    global auth_credentials, teacher_info, students_db
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                auth_credentials = saved.get("auth", auth_credentials)
                teacher_info = saved.get("teacher_info", teacher_info)
                students_db = saved.get("students_db", {})
        except Exception:
            pass

def save_data():
    data = {
        "auth": auth_credentials,
        "teacher_info": teacher_info,
        "students_db": students_db
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

load_data()

def process_student_grid(data, n_sessions):
    if not data:
        return [], {}
    
    df = pd.DataFrame(data)
    df.sort_values(by=["surname", "name"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    total_students = len(df)
    group1_limit = int(np.ceil(total_students / 2.0))
    df["group"] = [1 if i < group1_limit else 2 for i in range(total_students)]
    
    continuous_eval_list, devoir_total_list, final_avg_list = [], [], []
    
    for _, row in df.iterrows():
        deductions_total = sum(row["deductions"].get(crit, 0) * (info["weight"] / n_sessions) for crit, info in CRITERIA_INFO.items())
        eval_score = round(max(0.0, 20.0 - deductions_total), 2)
        continuous_eval_list.append(eval_score)
        
        devoir_marks = row.get("devoir", [])
        if len(devoir_marks) == n_sessions and all(m in DEVOIR_MAP for m in devoir_marks):
            max_per_session = 20.0 / n_sessions
            dev_score = round(sum(DEVOIR_MAP[m] * max_per_session for m in devoir_marks), 2)
        else:
            dev_score = 0.0  
            
        devoir_total_list.append(dev_score)
        
        exam_score = row.get("exam")
        if exam_score is not None:
            avg = round((((eval_score + dev_score) / 2.0) + (exam_score * 2.0)) / 3.0, 2)
            final_avg_list.append(avg)
        else:
            final_avg_list.append(None)
            
    df["continuous_eval"] = continuous_eval_list
    df["devoir_total"] = devoir_total_list
    df["final_avg"] = final_avg_list
    
    valid_avgs = df["final_avg"].dropna()
    analytics = {}
    if not valid_avgs.empty:
        analytics = {
            "total_students": total_students,
            "success_count": int((valid_avgs >= 10.0).sum()),
            "success_rate": round(((valid_avgs >= 10.0).sum() / len(valid_avgs)) * 100, 1),
            "max_avg": valid_avgs.max(),
            "min_avg": valid_avgs.min(),
            "class_avg": round(valid_avgs.mean(), 2)
        }
        
    return df.to_dict(orient="records"), analytics

COMMON_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
    * { font-family: 'Cairo', sans-serif; box-sizing: border-box; }
    body { background: #f1f5f9; padding: 20px; margin: 0; direction: rtl; }
    .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    h1, h2, h3 { color: #0f172a; margin-top: 0; font-weight: 700; }
    .btn { background: #059669; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
    .btn:hover { background: #047857; }
    .btn-blue { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; text-decoration: none; display: inline-block; }
    .btn-blue:hover { background: #1d4ed8; }
    .btn-print { background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
    .btn-back { background: #64748b; color: white; padding: 8px 14px; text-decoration: none; border-radius: 6px; font-weight: 600; }
    .alert-error { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #f87171; }
    .alert-success { background: #d1fae5; color: #065f46; padding: 10px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #34d399; }
    
    .table-container { max-height: 70vh; overflow-y: auto; overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 8px; position: relative; }
    table { width: 100%; border-collapse: separate; border-spacing: 0; background: white; font-size: 11px; }
    th, td { border-bottom: 1px solid #cbd5e1; border-left: 1px solid #cbd5e1; padding: 5px; text-align: center; vertical-align: middle; }
    
    thead { position: sticky; top: 0; z-index: 20; background: #1e293b; }
    thead th { position: sticky; background: #1e293b; color: white; }
    thead tr:nth-child(1) th { top: 0; z-index: 20; }
    thead tr:nth-child(2) th { top: 31px; z-index: 19; background: #334155; }
    
    tr:nth-child(even) { background: #f8fafc; }
    .badge-grp { background: #3b82f6; color: white; padding: 2px 5px; border-radius: 4px; font-weight: bold; }
    .input-sm { width: 40px; text-align: center; padding: 2px; border: 1px solid #cbd5e1; border-radius: 4px; }
    .input-txt { width: 85px; padding: 2px; font-size: 11px; border: 1px solid #cbd5e1; border-radius: 4px; }
    .crit-btn-deduct { font-size: 11px; padding: 1px 6px; background: #ef4444; color: white; border-radius: 3px; border: none; cursor: pointer; font-weight: bold; }
    .crit-btn-restore { font-size: 11px; padding: 1px 6px; background: #10b981; color: white; border-radius: 3px; border: none; cursor: pointer; font-weight: bold; }
    .action-del { color: #dc2626; text-decoration: none; font-weight: bold; font-size: 15px; margin-right: 4px; }
    .action-save { background: #2563eb; color: white; border: none; border-radius: 3px; padding: 2px 5px; cursor: pointer; font-size: 10px; }
    .highlight-col { background: #fef3c7; }

    @media print {
        @page { size: A4 landscape; margin: 5mm; }
        body { background: white; padding: 0; margin: 0; font-size: 9px; }
        .no-print, .btn-back, .btn-print, .btn, .btn-blue, details, form, .action-del, .action-save, .crit-btn-deduct, .crit-btn-restore { display: none !important; }
        .card { box-shadow: none; border: 1px solid #ccc; margin-bottom: 5px; padding: 5px; }
        .table-container { max-height: none; overflow: visible; border: none; }
        table { font-size: 9px; width: 100% !important; }
        th, td { padding: 2px !important; }
        thead tr:nth-child(1) th, thead tr:nth-child(2) th { position: static; background: #e2e8f0 !important; color: black !important; }
        input, select { border: none !important; background: transparent !important; appearance: none; -webkit-appearance: none; text-align: center; font-size: 9px; }
    }
</style>
"""

LOGIN_HTML = COMMON_CSS + """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>تسجيل الدخول</title></head>
<body style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f172a;">
    <div class="card" style="width: 360px; padding: 30px;">
        <h2 style="text-align: center; color: #1e293b; margin-bottom: 25px;">تسجيل الدخول</h2>
        {% if error %}<div class="alert-error">{{ error }}</div>{% endif %}
        <form method="POST" autocomplete="off">
            <div style="margin-bottom: 15px;">
                <label style="font-weight:600; display:block; margin-bottom:5px;">اسم المستخدم:</label>
                <input type="text" name="username" style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="off">
            </div>
            <div style="margin-bottom: 20px;">
                <label style="font-weight:600; display:block; margin-bottom:5px;">كلمة المرور:</label>
                <input type="password" name="password" style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="new-password">
            </div>
            <button type="submit" class="btn-blue" style="width: 100%; padding: 12px;">دخول</button>
        </form>
    </div>
</body>
</html>
"""

TEACHER_DASHBOARD_HTML = COMMON_CSS + """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>لوحة التحكم</title></head>
<body>
    <div style="max-width: 900px; margin: 0 auto;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h1>لوحة تحكم الأستاذ</h1>
            <div>
                <a href="/export_all_excel" class="btn-blue" style="background:#16a34a; margin-left: 10px;">📊 تصدير كل الأقسام إلى Excel</a>
                <a href="/logout" style="color: #dc2626; font-weight: bold; text-decoration: none;">تسجيل الخروج</a>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <div class="card">
            <h2>🔑 تعديل اسم المستخدم وكلمة المرور</h2>
            <form action="/update_credentials" method="POST" autocomplete="off" style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 10px; align-items: end;">
                <div>
                    <label style="font-weight:600;">اسم المستخدم الجديد:</label>
                    <input type="text" name="new_username" value="{{ credentials.username }}" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="off">
                </div>
                <div>
                    <label style="font-weight:600;">كلمة المرور الجديدة:</label>
                    <input type="password" name="new_password" placeholder="أدخل كلمة مرور جديدة" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="new-password">
                </div>
                <button type="submit" class="btn-blue">حفظ الحساب</button>
            </form>
        </div>

        <div class="card">
            <h2>المعلومات العامة والتربوية</h2>
            <form action="/save_teacher_info" method="POST" autocomplete="off">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <label style="font-weight:600;">مديرية التربية لولاية:</label>
                        <select name="wilaya" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;">
                            {% for w in wilayas %}
                                <option value="{{ w }}" {% if info.wilaya == w %}selected{% endif %}>{{ w }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label style="font-weight:600;">مؤسسة العمل:</label>
                        <input type="text" name="school" value="{{ info.school }}" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="off">
                    </div>
                    <div>
                        <label style="font-weight:600;">الموسم الدراسي:</label>
                        <input type="text" name="season" value="{{ info.season }}" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="off">
                    </div>
                    <div>
                        <label style="font-weight:600;">اسم ولقب الأستاذ:</label>
                        <input type="text" name="teacher_name" value="{{ info.teacher_name }}" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required autocomplete="off">
                    </div>
                    <div>
                        <label style="font-weight:600;">الفصل الدراسي:</label>
                        <select name="term" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;">
                            <option value="الفصل الأول" {% if info.term == "الفصل الأول" %}selected{% endif %}>الفصل الأول</option>
                            <option value="الفصل الثاني" {% if info.term == "الفصل الثاني" %}selected{% endif %}>الفصل الثاني</option>
                            <option value="الفصل الثالث" {% if info.term == "الفصل الثالث" %}selected{% endif %}>الفصل الثالث</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-weight:600;">عدد الحصص في الفصل (N):</label>
                        <input type="number" name="sessions_count" value="{{ info.sessions_count }}" min="1" max="10" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px;" required>
                    </div>
                </div>
                <br>
                <button type="submit" class="btn">حفظ المعلومات</button>
            </form>
        </div>

        <div class="card">
            <h2>الأقسام المسندة</h2>
            <form action="/add_class" method="POST" autocomplete="off" style="display: flex; gap: 10px; margin-bottom: 20px;">
                <input type="text" name="class_name" required style="flex: 1; padding: 8px; border:1px solid #cbd5e1; border-radius:6px;" autocomplete="off" placeholder="أدخل اسم القسم (مثال: 1 متوسط 1)">
                <button type="submit" class="btn-blue">+ إضافة قسم جديد</button>
            </form>

            <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                {% if info.classes %}
                    {% for c in info.classes %}
                        <div style="display: flex; align-items: center; background: #e2e8f0; border-radius: 8px; padding: 5px 12px;">
                            <a href="/class/{{ c }}" style="background: #3b82f6; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold;">📊 {{ c }}</a>
                            <a href="/delete_class/{{ c }}" style="color: #dc2626; text-decoration: none; margin-right: 10px; font-weight: bold; font-size: 18px;" onclick="return confirm('هل أنت متأكد من حذف هذا القسم؟')">✕</a>
                        </div>
                    {% endfor %}
                {% else %}
                    <p style="color: #64748b;">لا توجد أقسام مسندة حالياً. أضف قسماً من الأعلى للبدء.</p>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

CLASS_GRID_HTML = COMMON_CSS + """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>شبكة تقويم - {{ class_name }}</title></head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <a href="/dashboard" class="btn-back no-print">⬅ العودة للوحة التحكم</a>
        <h1>شبكة تقويم قسم: <span style="color: #2563eb;">{{ class_name }}</span></h1>
        <button onclick="window.print()" class="btn-print no-print">🖨️ طباعة الصفحة</button>
    </div>

    <div class="card">
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; background: #e2e8f0; padding: 12px; border-radius: 6px;">
            <div><strong>مديرية التربية:</strong> {{ info.wilaya }}</div>
            <div><strong>المؤسسة:</strong> {{ info.school }}</div>
            <div><strong>الموسم الدراسي:</strong> {{ info.season }}</div>
            <div><strong>الأستاذ:</strong> {{ info.teacher_name }}</div>
            <div><strong>الفصل:</strong> {{ info.term }}</div>
            <div><strong>عدد الحصص (N):</strong> {{ info.sessions_count }} حصص</div>
        </div>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert-{{ category }} no-print">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="card no-print">
        <h3>➕ إضافة التلاميذ</h3>
        <details style="margin-bottom: 15px;" open>
            <summary style="font-weight: bold; cursor: pointer; color: #2563eb;">📋 اللصق المباشر من Excel</summary>
            <form action="/batch_add_students/{{ class_name }}" method="POST" style="margin-top: 10px;">
                <p style="font-size: 12px; color: #475569; margin-bottom: 5px;">قم بتحديد الخلايا في إكسل (العمود الأول اللقب والعمود الثاني الاسم)، ثم انسخها والصقها مباشرة أدناه:</p>
                <textarea name="batch_data" rows="4" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px;" required autocomplete="off"></textarea>
                <button type="submit" class="btn-blue" style="margin-top: 8px;">استيراد وإضافة التلاميذ</button>
            </form>
        </details>

        <form action="/add_student/{{ class_name }}" method="POST" autocomplete="off" style="display:flex; gap: 8px; align-items: center; border-top: 1px solid #e2e8f0; padding-top: 10px;">
            <strong>إضافة فردية:</strong>
            <input type="text" name="surname" placeholder="اللقب الكامل" required style="padding: 5px;" autocomplete="off">
            <input type="text" name="name" placeholder="الاسم الكامل" required style="padding: 5px;" autocomplete="off">
            <select name="gender" required style="padding: 5px;">
                <option value="ذكر">ذكر</option>
                <option value="أنثى">أنثى</option>
            </select>
            <input type="number" name="pc" min="1" placeholder="رقم الجهاز" required style="padding: 5px; width: 80px;">
            <button type="submit" class="btn">إضافة</button>
        </form>
    </div>

    <div class="card">
        {% if students %}
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th rowspan="2">#</th>
                        <th rowspan="2">اللقب</th>
                        <th rowspan="2">الاسم</th>
                        <th rowspan="2">الجنس</th>
                        <th rowspan="2">رقم الجهاز</th>
                        <th rowspan="2" class="no-print">حفظ/حذف</th>
                        <th rowspan="2">الفوج</th>
                        {% for key, c_info in criteria.items() %}
                            <th>{{ c_info.label }}</th>
                        {% endfor %}
                        <th colspan="{{ info.sessions_count }}">تقييمات الفرض (اختيار الحرف)</th>
                        <th rowspan="2" class="highlight-col" style="color:#000;">مجموع التقويم<br>(20 ن)</th>
                        <th rowspan="2" class="highlight-col" style="color:#000;">مجموع الفرض<br>(20 ن)</th>
                        <th rowspan="2">الاختبار<br>(20 ن)</th>
                        <th rowspan="2">المعدل النهائي</th>
                    </tr>
                    <tr>
                        {% for key in criteria %}
                            <th>خصم/استرجاع</th>
                        {% endfor %}
                        {% for s in range(1, info.sessions_count + 1) %}
                            <th>ح{{ s }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for st in students %}
                    <tr id="row-{{ st.id }}">
                        <form action="/edit_student/{{ class_name }}/{{ st.id }}" method="POST" autocomplete="off">
                            <td>{{ loop.index }}</td>
                            <td><input type="text" name="surname" class="input-txt" value="{{ st.surname }}" required autocomplete="off"></td>
                            <td><input type="text" name="name" class="input-txt" value="{{ st.name }}" required autocomplete="off"></td>
                            <td>
                                <select name="gender" style="font-size: 10px;">
                                    <option value="ذكر" {% if st.gender == "ذكر" %}selected{% endif %}>ذكر</option>
                                    <option value="أنثى" {% if st.gender == "أنثى" %}selected{% endif %}>أنثى</option>
                                </select>
                            </td>
                            <td><input type="number" name="pc" class="input-sm" value="{{ st.pc }}" required></td>
                            <td class="no-print">
                                <button type="submit" class="action-save">حفظ</button>
                                <a href="/delete_student/{{ class_name }}/{{ st.id }}" class="action-del" onclick="return confirm('حذف هذا التلميذ؟')">✕</a>
                            </td>
                        </form>

                        <td><span class="badge-grp">فوج {{ st.group }}</span></td>

                        {% for crit in criteria %}
                        <td>
                            <button onclick="updateDeduction('{{ class_name }}', {{ st.id }}, '{{ crit }}', 'deduct')" class="crit-btn-deduct no-print">-</button>
                            <span id="ded-{{ st.id }}-{{ crit }}" style="font-weight: bold; margin: 0 2px;">{{ st.deductions[crit] }}</span>
                            <button onclick="updateDeduction('{{ class_name }}', {{ st.id }}, '{{ crit }}', 'restore')" class="crit-btn-restore no-print">+</button>
                        </td>
                        {% endfor %}

                        {% for s in range(info.sessions_count) %}
                        <td>
                            <select onchange="updateDevoir('{{ class_name }}', {{ st.id }}, {{ s }}, this.value)">
                                <option value="" {% if not st.devoir or st.devoir[s] == "" %}selected{% endif %}>--</option>
                                {% for opt in ['A', 'B', 'C', 'D'] %}
                                    <option value="{{ opt }}" {% if st.devoir and st.devoir|length > s and st.devoir[s] == opt %}selected{% endif %}>{{ opt }}</option>
                                {% endfor %}
                            </select>
                        </td>
                        {% endfor %}

                        <td class="highlight-col"><strong id="eval-{{ st.id }}" style="color: green; font-size: 13px;">{{ st.continuous_eval }}</strong></td>

                        <td class="highlight-col">
                            <strong id="devtotal-{{ st.id }}" style="font-size: 13px;">
                                {{ st.devoir_total }}
                            </strong>
                        </td>

                        <td>
                            <input type="number" step="0.25" id="exam-{{ st.id }}" class="input-sm" value="{{ st.exam }}" onchange="updateExam('{{ class_name }}', {{ st.id }}, this.value)">
                        </td>

                        <td>
                            <strong id="avg-{{ st.id }}" style="font-size:14px; color: #2563eb;">
                                {% if st.final_avg is not none %}{{ st.final_avg }}{% else %}--{% endif %}
                            </strong>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
            <p style="text-align: center; color: #64748b; font-style: italic; padding: 15px;">لا يوجد تلاميذ في هذا القسم حتى الآن.</p>
        {% endif %}
    </div>

    {% if analytics %}
    <div class="card">
        <h2>📊 تحليل نتائج القسم</h2>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;"><div>عدد التلاميذ</div><div style="font-size:18px; font-weight:bold; color:#2563eb;">{{ analytics.total_students }}</div></div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;"><div>نسبة النجاح</div><div style="font-size:18px; font-weight:bold; color:green;">{{ analytics.success_rate }} %</div></div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;"><div>معدل القسم العام</div><div style="font-size:18px; font-weight:bold; color:#2563eb;">{{ analytics.class_avg }}</div></div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;"><div>أعلى / أدنى معدل</div><div style="font-size:18px; font-weight:bold; color:#2563eb;">{{ analytics.max_avg }} / {{ analytics.min_avg }}</div></div>
        </div>
    </div>
    {% endif %}

    <script>
        function updateDeduction(className, studentId, crit, action) {
            fetch(`/api/${action}/${className}/${studentId}/${crit}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById(`ded-${studentId}-${crit}`).innerText = data.deductions[crit];
                    document.getElementById(`eval-${studentId}`).innerText = data.continuous_eval;
                    document.getElementById(`avg-${studentId}`).innerText = data.final_avg !== null ? data.final_avg : '--';
                });
        }

        function updateDevoir(className, studentId, sessionIdx, val) {
            fetch(`/api/devoir/${className}/${studentId}/${sessionIdx}/${val}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById(`devtotal-${studentId}`).innerText = data.devoir_total;
                    document.getElementById(`avg-${studentId}`).innerText = data.final_avg !== null ? data.final_avg : '--';
                });
        }

        function updateExam(className, studentId, val) {
            fetch(`/api/exam/${className}/${studentId}/${val}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById(`avg-${studentId}`).innerText = data.final_avg !== null ? data.final_avg : '--';
                });
        }
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == auth_credentials["username"] and request.form.get("password") == auth_credentials["password"]:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "اسم المستخدم أو كلمة المرور غير صحيحة!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template_string(TEACHER_DASHBOARD_HTML, info=teacher_info, wilayas=WILAYAS, credentials=auth_credentials)

@app.route("/update_credentials", methods=["POST"])
def update_credentials():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    new_user = request.form.get("new_username", "").strip()
    new_pass = request.form.get("new_password", "").strip()
    if new_user and new_pass:
        auth_credentials["username"] = new_user
        auth_credentials["password"] = new_pass
        save_data()
        flash("تم تحديث معلومات الحساب بنجاح!", "success")
    else:
        flash("يرجى ملء جميع الحقول!", "error")
    return redirect(url_for("dashboard"))

@app.route("/save_teacher_info", methods=["POST"])
def save_teacher_info():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    teacher_info["wilaya"] = request.form.get("wilaya")
    teacher_info["school"] = request.form.get("school")
    teacher_info["season"] = request.form.get("season")
    teacher_info["teacher_name"] = request.form.get("teacher_name")
    teacher_info["term"] = request.form.get("term")
    try:
        teacher_info["sessions_count"] = int(request.form.get("sessions_count", 4))
    except ValueError:
        teacher_info["sessions_count"] = 4
    save_data()
    flash("تم حفظ المعلومات العامة بنجاح!", "success")
    return redirect(url_for("dashboard"))

@app.route("/add_class", methods=["POST"])
def add_class():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    c_name = request.form.get("class_name", "").strip()
    
    if "classes" not in teacher_info:
        teacher_info["classes"] = []

    if c_name and c_name not in teacher_info["classes"]:
        teacher_info["classes"].append(c_name)
        if c_name not in students_db:
            students_db[c_name] = []
        save_data()
        flash(f"تم إضافة القسم '{c_name}' بنجاح!", "success")
    else:
        flash("اسم القسم فارغ أو موجود مسبقاً!", "error")
        
    return redirect(url_for("dashboard"))

@app.route("/delete_class/<class_name>")
def delete_class(class_name):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if class_name in teacher_info["classes"]:
        teacher_info["classes"].remove(class_name)
    if class_name in students_db:
        del students_db[class_name]
    save_data()
    flash(f"تم حذف القسم '{class_name}' بنجاح!", "success")
    return redirect(url_for("dashboard"))

@app.route("/class/<class_name>")
def class_view(class_name):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    data = students_db.get(class_name, [])
    processed_students, analytics = process_student_grid(data, teacher_info["sessions_count"])
    return render_template_string(
        CLASS_GRID_HTML,
        class_name=class_name,
        info=teacher_info,
        criteria=CRITERIA_INFO,
        students=processed_students,
        analytics=analytics
    )

@app.route("/add_student/<class_name>", methods=["POST"])
def add_student(class_name):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    surname = request.form.get("surname", "").strip()
    name = request.form.get("name", "").strip()
    gender = request.form.get("gender", "ذكر")
    try:
        pc = int(request.form.get("pc", 1))
    except ValueError:
        pc = 1
    if surname and name:
        new_id = int(np.random.randint(100000, 999999))
        student = {
            "id": new_id,
            "surname": surname,
            "name": name,
            "gender": gender,
            "pc": pc,
            "deductions": {crit: 0 for crit in CRITERIA_INFO},
            "devoir": [""] * teacher_info["sessions_count"],
            "exam": 10.0
        }
        if class_name not in students_db:
            students_db[class_name] = []
        students_db[class_name].append(student)
        save_data()
        flash("تم إضافة التلميذ بنجاح!", "success")
    return redirect(url_for("class_view", class_name=class_name))

@app.route("/batch_add_students/<class_name>", methods=["POST"])
def batch_add_students(class_name):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    raw_data = request.form.get("batch_data", "").strip()
    if raw_data:
        lines = raw_data.split("\n")
        added_count = 0
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                surname = parts[0].strip()
                name = parts[1].strip()
                if surname and name:
                    new_id = int(np.random.randint(100000, 999999))
                    student = {
                        "id": new_id,
                        "surname": surname,
                        "name": name,
                        "gender": "ذكر",
                        "pc": added_count + 1,
                        "deductions": {crit: 0 for crit in CRITERIA_INFO},
                        "devoir": [""] * teacher_info["sessions_count"],
                        "exam": 10.0
                    }
                    if class_name not in students_db:
                        students_db[class_name] = []
                    students_db[class_name].append(student)
                    added_count += 1
        if added_count > 0:
            save_data()
            flash(f"تم استيراد وإضافة {added_count} تلميذاً بنجاح!", "success")
        else:
            flash("تنسيق غير صالح. تأكد من لصق عمودين (اللقب ثم الاسم).", "error")
    return redirect(url_for("class_view", class_name=class_name))

@app.route("/edit_student/<class_name>/<int:student_id>", methods=["POST"])
def edit_student(class_name, student_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    students = students_db.get(class_name, [])
    for st in students:
        if st["id"] == student_id:
            st["surname"] = request.form.get("surname", st["surname"]).strip()
            st["name"] = request.form.get("name", st["name"]).strip()
            st["gender"] = request.form.get("gender", st["gender"])
            try:
                st["pc"] = int(request.form.get("pc", st["pc"]))
            except ValueError:
                pass
            save_data()
            flash("تم تحديث بيانات التلميذ بنجاح!", "success")
            break
    return redirect(url_for("class_view", class_name=class_name))

@app.route("/delete_student/<class_name>/<int:student_id>")
def delete_student(class_name, student_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    students = students_db.get(class_name, [])
    students_db[class_name] = [st for st in students if st["id"] != student_id]
    save_data()
    flash("تم حذف التلميذ بنجاح!", "success")
    return redirect(url_for("class_view", class_name=class_name))

@app.route("/api/deduct/<class_name>/<int:student_id>/<crit>")
def api_deduct(class_name, student_id, crit):
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    students = students_db.get(class_name, [])
    for st in students:
        if st["id"] == student_id:
            st["deductions"][crit] = st["deductions"].get(crit, 0) + 1
            save_data()
            break
    processed_students, _ = process_student_grid(students, teacher_info["sessions_count"])
    target_st = next((st for st in processed_students if st["id"] == student_id), None)
    if target_st:
        return jsonify({
            "deductions": target_st["deductions"],
            "continuous_eval": target_st["continuous_eval"],
            "final_avg": target_st["final_avg"]
        })
    return jsonify({"error": "Not found"}), 404

@app.route("/api/restore/<class_name>/<int:student_id>/<crit>")
def api_restore(class_name, student_id, crit):
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    students = students_db.get(class_name, [])
    for st in students:
        if st["id"] == student_id:
            if st["deductions"].get(crit, 0) > 0:
                st["deductions"][crit] -= 1
                save_data()
            break
    processed_students, _ = process_student_grid(students, teacher_info["sessions_count"])
    target_st = next((st for st in processed_students if st["id"] == student_id), None)
    if target_st:
        return jsonify({
            "deductions": target_st["deductions"],
            "continuous_eval": target_st["continuous_eval"],
            "final_avg": target_st["final_avg"]
        })
    return jsonify({"error": "Not found"}), 404

@app.route("/api/devoir/<class_name>/<int:student_id>/<int:session_idx>/<val>")
def api_devoir(class_name, student_id, session_idx, val):
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    if val != "" and val not in DEVOIR_MAP:
        return jsonify({"error": "Invalid value"}), 400
    students = students_db.get(class_name, [])
    for st in students:
        if st["id"] == student_id:
            while len(st["devoir"]) <= session_idx:
                st["devoir"].append("")
            st["devoir"][session_idx] = val
            save_data()
            break
    processed_students, _ = process_student_grid(students, teacher_info["sessions_count"])
    target_st = next((st for st in processed_students if st["id"] == student_id), None)
    if target_st:
        return jsonify({
            "devoir_total": target_st["devoir_total"],
            "final_avg": target_st["final_avg"]
        })
    return jsonify({"error": "Not found"}), 404

@app.route("/api/exam/<class_name>/<int:student_id>/<val>")
def api_exam(class_name, student_id, val):
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        f_val = float(val)
    except ValueError:
        f_val = 10.0
    students = students_db.get(class_name, [])
    for st in students:
        if st["id"] == student_id:
            st["exam"] = f_val
            save_data()
            break
    processed_students, _ = process_student_grid(students, teacher_info["sessions_count"])
    target_st = next((st for st in processed_students if st["id"] == student_id), None)
    if target_st:
        return jsonify({"final_avg": target_st["final_avg"]})
    return jsonify({"error": "Not found"}), 404

@app.route("/export_all_excel")
def export_all_excel():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            used_sheet_names = set()
            classes_list = teacher_info.get("classes", [])
            
            # ضمان وجود ورقة عمل واحدة على الأقل لمنع خطأ At least one sheet must be visible
            if not classes_list:
                df_empty = pd.DataFrame({"تنبيه": ["لا توجد أقسام مسجلة حالياً للتصدير"]})
                df_empty.to_excel(writer, sheet_title="عام", index=False)
            else:
                for class_name in classes_list:
                    data = students_db.get(class_name, [])
                    processed_students, _ = process_student_grid(data, teacher_info["sessions_count"])
                    rows = []
                    for idx, st in enumerate(processed_students, start=1):
                        rows.append({
                            "الرقم": idx,
                            "اللقب": st.get("surname", ""),
                            "الاسم": st.get("name", ""),
                            "الجنس": st.get("gender", ""),
                            "الفوج": f"فوج {st.get('group', 1)}",
                            "رقم الجهاز": st.get("pc", 1),
                            "مجموع التقويم المستمر": st.get("continuous_eval", 0),
                            "مجموع الفرض": st.get("devoir_total", 0),
                            "الاختبار": st.get("exam", 10.0),
                            "المعدل النهائي": st["final_avg"] if st.get("final_avg") is not None else "--"
                        })
                    
                    df_class = pd.DataFrame(rows)
                    if df_class.empty:
                        df_class = pd.DataFrame({"رسالة": ["لا يوجد تلاميذ في هذا القسم"]})
                    
                    clean_name = re.sub(r'[\/\\\?\*\[\]\:]', '_', str(class_name)).strip()
                    sheet_title = clean_name[:30] if clean_name else "قسم"
                    
                    base_title = sheet_title
                    counter = 1
                    while sheet_title in used_sheet_names:
                        suffix = f"_{counter}"
                        sheet_title = base_title[:30 - len(suffix)] + suffix
                        counter += 1
                    used_sheet_names.add(sheet_title)

                    df_class.to_excel(writer, sheet_title=sheet_title, index=False)
                    try:
                        worksheet = writer.sheets[sheet_title]
                        worksheet.sheet_view.showGridLines = True
                        worksheet.views.sheetView[0].rightToLeft = True
                    except Exception:
                        pass

        output.seek(0)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="جميع_أقسام_شبكة_التقويم.xlsx"
        )
    except Exception as e:
        flash(f"حدث خطأ أثناء تصدير الملف: {str(e)}", "error")
        return redirect(url_for("dashboard"))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
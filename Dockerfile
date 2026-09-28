# استخدام نسخة بايثون رسمية مستقرة ومتوافقة
FROM python:3.11-slim

# تعيين مجلد العمل داخل الحاوية
WORKDIR /app

# تحديث مدير الحزم وتثبيت أدوات النظام الضرورية لبناء الحزم إن احتجت
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات أولاً لاستغلال التخزين المؤقت
COPY requirements.txt .

# تثبيت المتطلبات بدون مشاكل
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع إلى الحاوية
COPY . .

# أمر تشغيل التطبيق عبر Gunicorn (تأكد أن app:app مطابقة لاسم ملفك، مثل main:app إذا كان اسم ملفك main.py)
CMD gunicorn --bind 0.0.0.0:$PORT app:app
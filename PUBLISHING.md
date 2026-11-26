# نشر آمن ومتكرر — MAS AI Agents

الهدف: رفع التغييرات المُختبرة إلى المستودع الصحيح دون كشف أسرار ودون الكتابة فوق عمل موجود.

- المستودع: `https://github.com/drantonhanna2005-beep/MAS-AI-Agents_V2.git`
- الفرع: `main`

## الخطوات (بالترتيب)

1. **فحص ما تغيّر**
   ```powershell
   git status --short
   git diff
   ```
2. **تشغيل الاختبارات**
   ```powershell
   $env:PYTHONPATH="."
   python -m compileall -q app.py core agents
   node --check web/app.js
   python tests/test_gpa.py; python tests/test_regressions.py; python tests/test_fallback.py
   ```
3. **فحص الأسرار** (لا ترفع مفاتيح أبداً)
   - `config.json` و `.env` و `*.db` و `uploads/` و `index_store/` و `data/university/` مستثناة في `.gitignore`.
   - إن ظهر مفتاح داخل ملف مُتتبَّع: احذفه، واعتبره مُسرَّباً، وبدّله من لوحة المزود.
4. **مراجعة ما سيُرفع**
   ```powershell
   git add -u; git add <files>      # لا تستخدم git add -A دون مراجعة
   git diff --cached --stat
   git diff --cached --check
   ```
5. **عمل commit**
   ```powershell
   git commit -m "feat: وصف واضح"
   ```
6. **المزامنة مع الريموت قبل الدفع** (لمنع رفض غير fast-forward)
   ```powershell
   git fetch origin main
   git merge origin/main          # لا تستخدم --force
   ```
7. **الدفع والتحقق**
   ```powershell
   git push origin HEAD:main
   git rev-parse HEAD
   gh api repos/drantonhanna2005-beep/MAS-AI-Agents_V2/commits/main --jq .sha
   # يجب أن يتطابق الـ SHA المحلي مع الريموت
   ```

أو استخدم السكربت الجاهز الذي يقوم بكل ما سبق مع تأكيد قبل الدفع:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish.ps1
```


> **ملاحظة صلاحيات GitHub:** رفع ملفات GitHub Actions يتطلب صلاحية `workflow` في التوكن.
> إن ظهر الخطأ `refusing to allow an OAuth App to create or update workflow` فشغّل مرة واحدة:
> `gh auth refresh -h github.com -s workflow` ثم `git push origin HEAD:main`.
> ملف `.github/workflows/ci.yml` موجود جاهزاً في مساحة العمل، ويصبح فعّالاً بعد رفعه.

## ما يفعله GitHub Actions

عند كل `push` إلى `main` يعمل `.github/workflows/ci.yml` تلقائياً ويقوم بـ:

- فحص صحة صياغة Python وJavaScript.
- اختبار استيراد الخادم وإنشاء قاعدة البيانات.
- تشغيل اختبارات الوحدة (GPA / الانحدار / fallback).
- فحص الأسرار داخل الملفات.

**مهم:** Actions تتحقق فقط بعد الدفع. لا يوجد أي مزامنة تلقائية أو دفع ذاتي في الخلفية — دفع الكود يبقى خطوة يدوية مُتحكَّم بها.

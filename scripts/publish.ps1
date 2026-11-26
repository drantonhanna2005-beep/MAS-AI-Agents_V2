# نشر آمن ومُتحقَّق منه — MAS AI Agents
# يقوم بكل فحوصات ما قبل الدفع، ثم يدفع فقط إلى المستودع والفرع المُثبَّتين أدناه.
# الاستخدام:  powershell -ExecutionPolicy Bypass -File scripts/publish.ps1 [-Message "وصف"] [-Force]
param(
    [string]$Message = "chore: publish verified MAS AI Agents project",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# ---------- هوية المستودع المُثبَّتة (لا تُغيّرها إلا بقرار واعٍ) ----------
$ExpectedOwner  = "drantonhanna2005-beep"
$ExpectedRepo   = "MAS-AI-Agents_V2"
$RemoteUrl      = "https://github.com/$ExpectedOwner/$ExpectedRepo.git"
$Branch         = "main"

function Fail($msg) { Write-Host "`n[FAIL] $msg" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }

# ---------- 0. الجذر ----------
$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { Fail "ليست مستودع Git. شغّل السكربت من داخل المجلد الصحيح." }
Set-Location $root
if (-not (Test-Path "app.py") -or -not (Test-Path "web/app.js")) {
    Fail "هذا ليس جذر مشروع MAS AI Agents (app.py / web/app.js غير موجودين)."
}
Ok "المشروع: $root"
Ok "الفرع الحالي: $(git branch --show-current)"

# ---------- 1. الريموت الصحيح ----------
$remotes = git remote -v
if ($remotes -notmatch [regex]::Escape($RemoteUrl)) {
    Step "الريموت '$RemoteUrl' غير مضاف — أضِفه الآن"
    git remote add publish $RemoteUrl
    Ok "أُضيف الريموت باسم publish"
    $remoteName = "publish"
} else {
    $remoteName = ($remotes -split "`n" | Where-Object { $_ -match [regex]::Escape($RemoteUrl) } |
                   Select-Object -First 1).Split("`t")[0]
    Ok "الريموت: $remoteName -> $RemoteUrl"
}

# ---------- 2. فحص الأسرار في الملفات التي ستُرفع ----------
Step "فحص الأسرار في الملفات غير المستثناة"
$patterns = 'sk-or-v1-[0-9a-f]{20,}|gsk_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{30,}|sk-[0-9a-f]{40,}|github_pat_|ghp_[A-Za-z0-9]{30,}|AQ\.Ab[0-9A-Za-z_-]{20,}|BEGIN [A-Z ]*PRIVATE KEY'
$files = git ls-files -co --exclude-standard
$hits = @()
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
    if ($f -match '\.(png|jpg|jpeg|gif|webp|ico|pdf|zip|db|sqlite|woff2?|ttf)$') { continue }
    $m = Select-String -LiteralPath $f -Pattern $patterns -AllMatches -ErrorAction SilentlyContinue
    if ($m) { $hits += "$f : $($m.Count) match(es)" }
}
if ($hits.Count -gt 0) { $hits | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }; Fail "تم إيقاف النشر: أسرار محتملة في ملفات ستُرفع." }
Ok "لا أسرار في الملفات المُراد رفعها"

# ---------- 3. تأكيد استثناء البيانات الخاصة ----------
Step "تأكيد استثناء البيانات الخاصة"
$mustIgnore = @("config.json", ".env", "history.db")
foreach ($p in $mustIgnore) {
    if (git ls-files --error-unmatch $p 2>$null) { Fail "$p مُتتبَّع بواسطة Git — يجب إزالته من التتبع (git rm --cached) قبل النشر." }
}
$badTracked = git ls-files | Select-String -Pattern '^(uploads/|index_store/|data/university/|logs/)|\.db(-wal|-shm)?$' -AllMatches
if ($badTracked) { Fail "ملفات بيانات/سجلات مُتتبَّعة: $($badTracked -join ', ')" }
Ok "لا مفاتيح/قواعد بيانات/رفعات/فهارس مُتتبَّعة"

# ---------- 4. الاختبارات ----------
Step "فحص الصياغة والاختبارات"
python -m compileall -q app.py core agents
if ($LASTEXITCODE -ne 0) { Fail "فشل فحص صياغة Python" }
Ok "Python compile"
node --check web/app.js; if ($LASTEXITCODE -ne 0) { Fail "خطأ صياغة web/app.js" }
node --check web/i18n.js; node --check web/share.js; node --check web/sw.js
Ok "JavaScript syntax"
$env:PYTHONPATH = "."
python tests/test_gpa.py        | Out-Null; if ($LASTEXITCODE -ne 0) { Fail "test_gpa فشل" }
python tests/test_regressions.py| Out-Null; if ($LASTEXITCODE -ne 0) { Fail "test_regressions فشل" }
python tests/test_fallback.py   | Out-Null; if ($LASTEXITCODE -ne 0) { Fail "test_fallback فشل" }
Ok "اختبارات الوحدة (45 اختباراً)"

# ---------- 5. مراجعة ما سيُرفع ----------
Step "مراجعة التغييرات"
git add -u
git status --short
git diff --cached --check | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "   تحذير: مشاكل مسافات في diff --cached" -ForegroundColor Yellow }
$staged = git diff --cached --name-only
if (-not $staged) { Write-Host "   لا تغييرات مُرتَّبة (staged) — إن كانت هناك ملفات جديدة أضِفها يدوياً." -ForegroundColor Yellow }
Write-Host ($staged -join "`n")
if (-not $Force) {
    $ans = Read-Host "`nهل تريد المتابعة (commit + push إلى $ExpectedRepo/$Branch)؟ اكتب yes"
    if ($ans -ne "yes") { Write-Host "أُلغيت العملية (لم يُدفع شيء)." -ForegroundColor Yellow; exit 0 }
}

# ---------- 6. Commit ----------
Step "إنشاء commit"
if ($staged) {
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { Fail "فشل إنشاء الـ commit" }
    Ok "commit: $(git rev-parse --short HEAD) — $Message"
} else {
    Ok "لا شيء جديد لإنشاء commit له — سننسخ الموجود"
}

# ---------- 7. مزامنة آمنة (بدون force) ----------
Step "مزامنة مع الريموت قبل الدفع"
git fetch $remoteName $Branch
if ($LASTEXITCODE -ne 0) { Fail "تعذر الجلب من الريموت (شبكة/مصادقة)" }
$localSha   = git rev-parse HEAD
$remoteSha  = git rev-parse "$remoteName/$Branch"
if ($localSha -ne $remoteSha) {
    git merge --no-edit "$remoteName/$Branch"
    if ($LASTEXITCODE -ne 0) { Fail "تعذر الدمج التلقائي — حلّ التعارضات يدوياً ثم أعد التشغيل. لم يُدفع شيء." }
    Ok "تم الدمج مع الريموت"
} else { Ok "محلي = ريموت، لا حاجة للدمج" }

# ---------- 8. الدفع ----------
Step "الدفع إلى $ExpectedOwner/$ExpectedRepo : $Branch"
git push $remoteName "HEAD:$Branch"
if ($LASTEXITCODE -ne 0) { Fail "فشل الدفع — اقرأ الرسالة أعلاه (مصادقة/صلاحيات/غير fast-forward)." }
Ok "تم الدفع"

# ---------- 9. تحقق مستقل ----------
Step "التحقق من الريموت"
$local  = git rev-parse HEAD
$remote = (gh api "repos/$ExpectedOwner/$ExpectedRepo/commits/$Branch" --jq .sha) 2>$null
if (-not $remote) {
    git fetch $remoteName $Branch | Out-Null
    $remote = git rev-parse "$remoteName/$Branch"
}
Write-Host "   local : $local"
Write-Host "   remote: $remote"
if ($local -eq $remote) { Ok "المطابقة مؤكدة — الريموت يحتوي نفس الـ commit" }
else { Fail "عدم تطابق! راجع حالة الريموت يدوياً." }

Write-Host "`nاكتمل النشر بنجاح: https://github.com/$ExpectedOwner/$ExpectedRepo/tree/$Branch" -ForegroundColor Green

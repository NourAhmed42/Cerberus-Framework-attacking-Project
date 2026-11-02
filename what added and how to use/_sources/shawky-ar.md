# Shawky عمل ايه

**آخر تحديث: 2 نوفمبر 2026 (توقيت القاهرة)**

هذا الملف يجمع كل حاجه اتعملت في مشروع Cerberus: ايه هي، ليه موجودة، وازاي تستخدمها خطوة بخطوة على Mac (zsh) وWindows (PowerShell).

> **قاعدة مهمة:** كل الأوامر تشتغل من جذر المشروع `Cerberus`. الأدوات المحلية بتشتغل على جهازك بس. الأدوات اللي بتزور مواقع عامة لها حدود يومية، ولا تشغّلها إلا لما تحتاج نتيجة جديدة.

## 0. الخلاصة السريعة

| الحاجة | بتعمل ايه | فين |
|---|---|---|
| إطار الاختبار (Attack framework) | مجموعة وحدات بتشغل الأدوات الخارجية وتقرأ نتايجها | `backend/app/ai_engine/pentest/` |
| Nmap | بيفحص المنافذ المفتوحة | `scripts/live_tests/` + المحول |
| sqlmap | بيكتشف حقن SQL في معامل `id` | `scripts/live_tests/` + المحول |
| Metasploit | بيفحص المنافذ عن طريق الـ daemon الحقيقي (على الجهاز بس) | المحول + `msfrpcd` |
| معمل المبتدئ (beginner lab) | يشغّل الأدوات على هدف محلي مؤقت | `beginner_tools_lab.py` |
| تشغيل الأدوات الثلاث مع بعض | يشغّلهم في نفس الوقت كـ 3 محركات منفصلة | `run_all_tools.py` |
| تشغيل عام محدود | يزور المواقع المسموح بيها بس | `public_tool_results.py` |
| عرض كامل (Demo) | يشغّل كل حاجة بأمر واحد ويطبع ملخص | `scripts/demo/run_everything.py` |
| النتايج الحقيقية | بيسجل النتايج ويعمل PDF | `docs/real_results.json` |
| الاختبارات | بتتأكد إن كل حاجة شغالة | `backend/tests/unit/` |

## 1. التجهيز قبل أي حاجة

### ليه؟
المشروع بيحتاج Python بيئته الخاصة (`.venv`) عشان المكتبات تكون متناسقة. ولو استخدمت Python العام ممكن تطلع أخطاء أو نتايج مختلفة.

### Mac (zsh)

```zsh
cd ~/Cerberus
./backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

### Windows (PowerShell)

```powershell
cd $HOME\Cerberus
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### الأدوات الخارجية

- **Nmap:** على Mac `brew install nmap`. على Windows حمّله من nmap.org/download.
- **sqlmap:** على Mac `brew install sqlmap`. على Windows استنسخه من GitHub ووجّه `SQLMAP_PATH` لملف `sqlmap.py`.
- **Metasploit (اختياري):** مش مطلوب للمعمل المحلي. مطلوب بس لو عايز تشغّل الـ daemon الحقيقي على جهازك.

## 2. إطار الاختبار (Attack framework)

### ايه هو؟
مجموعة ملفات بايثون (35 وحدة برمجية بالحساب الكامل) في `backend/app/ai_engine/pentest/`. فيها 9 وحدات فحص مسجلة، ومنها 3 وحدات بتشغّل الأدوات الخارجية (Nmap وsqlmap وMetasploit).

### ليه موجود؟
عشان نقدر نشغّل أدوات الفحص بطريقة آمنة ومنظمة: فيه فحص للنطاق (scope)، وحدود للتأثير، وتسجيل للنتايج والأدلة.

### القواعد اللي بيطبقها
- ما بيقبلش أي هدف مش معتمد.
- Metasploit بيسمح بـ `auxiliary/scanner/portscan/tcp` بس، ومنافذ محدودة.
- Nmap NSE بيسمح بـ `banner` و`ssl-cert` بس.
- الوحدات اللي مش مراجعة بتترفض.

### الخطوة
الإطار مش بيتشغل لوحده. بيتشغل من خلال الأوامر في الأقسام 3 و4.

## 3. الأدوات الثلاث

### 3.1 Nmap

**ليه؟** بيعرف المنافذ المفتوحة على الهدف، وده أول خطوة في أي فحص.

**الهدف المسموح به:** `scanme.nmap.org` بس. المشغّل مش بيقبل أي هدف تاني. الحد حوالي 10 مرات في 24 ساعة.

**الخطوة (معمل محلي):**

Mac:
```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py nmap
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py nmap
```

**النتيجة المتوقعة:** سطر `PASS: real Nmap found the local lab's open port` ورقم منفذ بيتغير.

### 3.2 sqlmap

**ليه؟** بيكتشف ثغرة حقن SQL في معامل `id`. ده بيحدد لو الموقع ضعيف في الاستعلامات.

**الهدف المسموح به:** معامل `id` في صفحة المنتج في SekuMart بس (`https://sekumart.sekuripy.hr/product.php?id=1`). sqlmap بيكتشف بس، ومابيستخرجش بيانات. الحد 6 مرات في 24 ساعة.

**الخطوة (معمل محلي):**

Mac:
```zsh
export SQLMAP_PATH="$(command -v sqlmap)"
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py sqlmap
```

Windows:
```powershell
$env:SQLMAP_PATH = "$HOME\sqlmap\sqlmap.py"
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py sqlmap
```

**النتيجة المتوقعة:** `PASS: real sqlmap detected` مع معامل `id`.

### 3.3 Metasploit

**ليه؟** بيفحص المنافذ عن طريق الـ daemon الحقيقي `msfrpcd`، وده بيثبت إن التكامل شغال مع Metasploit الحقيقي.

**الهدف:** جهازك بس (`127.0.0.1`). مفيش موقع عام بيسمح بفحص Metasploit.

**الخطوة الأولى: شغّل الـ daemon** (في نافذة طرفية منفصلة، وسيبها شغالة):

Mac:
```zsh
msfrpcd -U msf -P "YOUR_STRONG_PASSWORD" -a 127.0.0.1 -p 55553 -S -n -f
```

Windows (PowerShell): `msfrpcd` غالباً في مجلد `bin` جوه تثبيت Metasploit. اتأكد من اسم الملف في تثبيتك، وبعدين شغّله بنفس المعاملات:

```powershell
& "C:\metasploit-framework\bin\msfrpcd.bat" -U msf -P "YOUR_STRONG_PASSWORD" -a 127.0.0.1 -p 55553 -S -n -f
```

**الخطوة الثانية: اضبط كلمة المرور** في نفس الطرفية اللي هتشغّل منها الأوامر:

Mac:
```zsh
export MSF_RPC_PASSWORD="YOUR_STRONG_PASSWORD"
```

Windows:
```powershell
$env:MSF_RPC_PASSWORD = "YOUR_STRONG_PASSWORD"
```

استبدل `YOUR_STRONG_PASSWORD` بكلمة مرورك. ما تكتبهاش في أي محادثة.

**ملاحظة:** المعمل المحلي بيستخدم Metasploit محاكى (SIMULATED) ومش بيحتاج الـ daemon. الـ daemon الحقيقي بيتشغّل بس في التشغيل المشترك (القسم 4.2).

## 4. أدوات التشغيل

### 4.1 معمل المبتدئ (`beginner_tools_lab.py`)

**ليه؟** بيشغّل الأدوات على هدف مؤقت على جهازك، وبيوقفه في الآخر. ده آمن وسهل للمبتدئين.

**الأوضاع:**

| الوضع | بيعمل ايه |
|---|---|
| `nmap` | Nmap حقيقي على الهدف المحلي |
| `sqlmap` | sqlmap حقيقي على الهدف المحلي |
| `metasploit` | Metasploit محاكى |
| `all` | الثلاثة واحد ورا التاني |
| `parallel` | الثلاثة في نفس الوقت |

الأوامر موجودة في الأقسام 3.1 و3.2. للأوضاع `all` و`parallel`:

Mac:
```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py all
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py parallel
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py all
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py parallel
```

### 4.2 التشغيل المشترك للأدوات الثلاث (`run_all_tools.py`)

**ليه؟** بيشغّل الأدوات الثلاث في نفس الوقت، كل واحدة في محرك منفصل: Nmap على `scanme.nmap.org`، وsqlmap على SekuMart، وMetasploit الحقيقي على جهازك.

**الخطوات:**
1. شغّل `msfrpcd` (القسم 3.3).
2. اضبط `MSF_RPC_PASSWORD` (القسم 3.3).
3. شغّل الأمر:

Mac:
```zsh
./backend/.venv/bin/python scripts/live_tests/run_all_tools.py --confirm-public-tests
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\run_all_tools.py --confirm-public-tests
```

**ملاحظة:** الخيار `--confirm-public-tests` إلزامي. بدونه الأمر بيرفض يبدأ.

### 4.3 التشغيل العام لأداة واحدة (`public_tool_results.py`)

**ليه؟** لما تحتاج نتيجة جديدة من موقع عام بس، من غير ما تشغّل الثلاثة.

Mac:
```zsh
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py nmap --confirm-public-tests
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py sqlmap --confirm-public-tests
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py nmap --confirm-public-tests
.\backend\.venv\Scripts\python.exe scripts\live_tests\public_tool_results.py sqlmap --confirm-public-tests
```

**تنبيه:** النتيجة بتتحفظ في `docs/real_results.json` وبتتحسب في الحد اليومي.

### 4.4 العرض الكامل (`run_everything.py`)

**ليه؟** عشان تعرض للفريق كل حاجة بأمر واحد، وتشوف ملخص بالنتايج.

**المحتوى:**
1. فحص ما هو مثبت (Step 0).
2. المعمل المحلي للثلاث أدوات (Step 1).
3. الاختبارات الآلية، 228 اختبار من غير قاعدة بيانات (Step 2).
4. التشغيل العام (Step 3) بس لو أضفت `--include-public`.

Mac:
```zsh
export SQLMAP_PATH="$(command -v sqlmap)"
./backend/.venv/bin/python scripts/demo/run_everything.py
```

Windows:
```powershell
$env:SQLMAP_PATH = "$HOME\sqlmap\sqlmap.py"
.\backend\.venv\Scripts\python.exe scripts\demo\run_everything.py
```

**ملفات التشغيل المختصرة:**
- Mac: `zsh scripts/demo/run-vscode-tools-test.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File scripts\demo\run-vscode-tools-test.ps1`

## 5. النتايج الحقيقية

**ليه؟** عشان تحفظ النتايج الحقيقية وتفصّلها: عامة، ومعمل محلي، ومحاكاة. ده بيمنع الخلط بينهم.

**الملفات:**
- `docs/real_results.json`: البيانات المحفوظة.
- `docs/real result.pdf`: التقرير المبني منها (المكرر في مجلد الدليل).
- `scripts/render_real_results.py`: الكود اللي بيبني التقرير.
- `docs/all_tools_result/run-all-tools.json`: ناتج تشغيل 2 نوفمبر.

**إعادة بناء التقرير:**

Mac:
```zsh
./backend/.venv/bin/python scripts/render_real_results.py
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe scripts\render_real_results.py
```

**أهم النتايج (2 نوفمبر 2026):**
- Nmap على `scanme.nmap.org`: منافذ 22 و80 و443 مفتوحة.
- sqlmap على SekuMart: تم اكتشاف الحقن في `id`.
- Metasploit على جهازك: وجد المنفذ المفتوح.

## 6. الاختبارات

**ليه؟** عشان تتأكد إن كل حاجة شغالة بعد أي تعديل.

### الاختبارات بدون قاعدة بيانات (228 اختبار)

Mac:
```zsh
cd backend
./.venv/bin/python -m pytest --noconftest -q -k "not persist" tests/unit/test_pentest_tools.py tests/unit/test_pentest_framework.py tests/unit/test_pentest_safety_regressions.py tests/unit/test_sqlmap_integration.py tests/unit/test_public_tool_results.py
cd ..
```

Windows:
```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest --noconftest -q -k "not persist" tests\unit\test_pentest_tools.py tests\unit\test_pentest_framework.py tests\unit\test_pentest_safety_regressions.py tests\unit\test_sqlmap_integration.py tests\unit\test_public_tool_results.py
Set-Location ..
```

**النتيجة المتوقعة:** `228 passed, 2 deselected`.

### الاختبارات الكاملة (385 اختبار)

تحتاج PostgreSQL وRedis مؤقتين. **لا تشغّلها على قاعدة بياناتك الحقيقية**، لأن ملف `conftest.py` بيحذف الجداول. استخدم قاعدة مؤقتة منفصلة.

**ملاحظة إصلاح:** أضفت في `backend/tests/conftest.py` عزل لـ Redis: بيمسح بس مفاتيح `abuse:*` بين الاختبارات.

## 7. الملفات والمجلدات

| الملف | بيعمل ايه |
|---|---|
| `Attack framework/frameworks added.pdf` | شرح الإطار والوحدات والقواعد |
| `Nmap/nmap integration and how to use (2026-11-02).pdf` | دليل Nmap |
| `sqlmap/sqlmap integration and how to use (2026-11-02).pdf` | دليل sqlmap |
| `Metasploit/metasploit added files.pdf` | الملفات المضافة لـ Metasploit |
| `Metasploit/metasploit how to use.pdf` | دليل استخدام Metasploit |
| `Metasploit/metasploit steps to check up.pdf` | خطوات التأكد من Metasploit |
| `Beginner guide/how to run the tools as beginner.pdf` | دليل المبتدئ بالإنجليزي |
| `Beginner guide/how to run the tools as beginner (arabic).pdf` | دليل المبتدئ بالعربي |
| `VS Code terminal/vscode terminal verification steps.pdf` | خطوات التحقق في الطرفية |
| `VS Code terminal/vscode tools test.pdf` | العرض الكامل وشرح الأوامر |
| `VS Code terminal/vscode tools test - python commands (arabic).pdf` | شرح أوامر Python بالعربي |
| `Real results/real result.pdf` | النتايج الحقيقية |
| `Real results/all tools result/run all the tools.pdf` | دليل تشغيل الأدوات الثلاث مع بعض |
| `README.md` | فهرس كل الملفات والقواعد |
| `_sources/` | المصادر (Markdown) وسكربت بناء الـ PDFs `build_pdfs.py` |
| `old PDF versions (archived)/` | النسخ القديمة (خارج مجلد الـ PDFs) |

**بناء كل الـ PDFs من المصادر:**

Mac:
```zsh
./backend/.venv/bin/python "what added and how to use/_sources/build_pdfs.py"
```

Windows:
```powershell
.\backend\.venv\Scripts\python.exe "what added and how to use\_sources\build_pdfs.py"
```

(شغّل الأمر من جذر `Cerberus`.)

## 8. حالة Git

- الـ commits المحلية: `bf543af` و`59dc2b7` فوق `4a8b7d5`، بالاسم "Cerberus Dev <dev@cerberus.local>".
- التغييرات **مش متعملها commit** لسه: المشغّلات والاختبارات والسكربتات الجديدة، والتقارير، والـ PDFs.
- **ما اتعملش push** لأي حاجة.

## 9. التنظيف

- حُذف مجلد الاختبار المؤقت لـ sqlmap.
- اتوقف `msfrpcd` وتم إزالة تثبيت Metasploit المؤقت.
- اتوقفت قاعدة البيانات وRedis المؤقتين وتم حذفهم.
- النسخ القديمة من الـ PDFs اتنقلت لمجلد أرشيف خارج مجلد الـ PDFs.

## 10. اللي لسه ما اتعملش أو ما اتتحققش منه

- **Mac و Windows:** الأوامر ما اتجربتش على الأجهزة دي. ده يشمل ملفات التشغيل `.sh` و`.ps1`.
- **sqlmap و Metasploit:** اتعادوا تثبيتهم مؤقتاً على الجهاز ده لتشغيل 2 نوفمبر (انظر سجل التعديلات)، وتم إزالتهم بعد التشغيل.
- **التشغيل العام:** اتعمل تشغيل عام كامل مرة إضافية في 2 نوفمبر (الساعة 15:55 UTC)، وده بيحتسب في الحدود اليومية.
- **الربط بالتطبيق:** الـ API والـ AI والواجهة مش متوصلين بالأدوات. ده مؤجل حسب الخطة.
- **قاعدة البيانات:** النتايج مش بتتحفظ فيها من العرض والمعمل.

## 11. سجل التعديلات

كل ما تعمل حاجة جديدة، ضيف سطر هنا بالتاريخ وايه اللي اتعمل.

| التاريخ | اللي اتعمل |
|---|---|
| 2 نوفمبر 2026 | تشغيل الأدوات الثلاث في نفس الوقت (`run_all_tools.py`) |
| 2 نوفمبر 2026 | إضافة عرض كامل (`run_everything.py`) وملفات تشغيل مختصرة للـ Mac والـ Windows |
| 2 نوفمبر 2026 | تحديث النتايج الحقيقية ليشمل تشغيل 2 نوفمبر |
| 2 نوفمبر 2026 | تحديث دليل المبتدئ بالإنجليزي وإضافة نسخة عربية |
| 2 نوفمبر 2026 | إضافة شرح أوامر Python بالعربي وشرح الأوامر في دليل العرض |
| 2 نوفمبر 2026 | إنشاء هذا الملف |
| 2 نوفمبر 2026 | تشغيل كل الأدوات على المواقع المسموحة (Nmap على scanme.nmap.org، وsqlmap على SekuMart، وMetasploit على loopback) وإنتاج ملف "Output only" |
| 2 نوفمبر 2026 | تشغيل الأدوات المحلية (nmap وsqlmap وmetasploit وall وparallel) وعرض run_everything المحلي |
| 2 نوفمبر 2026 | إعادة تثبيت sqlmap وMetasploit مؤقتاً للتشغيل، ثم إزالتهم بعد التشغيل |
| 2 نوفمبر 2026 | توسيع ملف "Output only" بمخرجات محلية إضافية: sqlmap lab smoke، وإطار الـ 9 وحدات، وكل اختبارات الأدوات (228 اختبار سطر بسطر). مفيش موقع جديد اتفحص |

# شرح أوامر Python في VS Code tools test

**تاريخ التحديث: 2 نوفمبر 2026 (توقيت القاهرة)**

هذا الملف يشرح بالعربي كل أمر Python في دليل **VS Code tools test**: ماذا يفعل كل أمر، ومتى تستخدمه، وما الذي تراه في الطرفية (Terminal).

> **قاعدة مهمة:** شغّل كل الأوامر من مجلد المشروع `Cerberus`. الأوامر المحلية تعمل على جهازك فقط، ولا تزور أي موقع. أوامر المواقع العامة تزور موقعين مسموح بهما فقط، ولها حدود يومية.

## 1. أي Python نستخدم؟

| الأمر | ماذا يفعل |
|---|---|
| `./backend/.venv/bin/python` (Mac) | يشغّل Python الخاص بالمشروع داخل البيئة الافتراضية `.venv`. |
| `.\backend\.venv\Scripts\python.exe` (Windows) | نفس الشيء على ويندوز. |

**لماذا؟** البيئة `.venv` تحتوي على المكتبات التي يحتاجها المشروع. استخدام Python العام على الجهاز قد يعطيك أخطاء أو نتائج مختلفة، لذلك نستخدم دائماً Python الخاص بالمشروع.

## 2. تشغيل الأدوات على هدف محلي (LOCAL LAB)

هذه الأوامر تشغّل سيرفر تجريبي مؤقت على `127.0.0.1` (جهازك)، وتشغّل الأدوات عليه، ثم توقف السيرفر في النهاية. لا يُحفظ شيء في قاعدة البيانات.

الملف المستخدم: `scripts/live_tests/beginner_tools_lab.py`

| الوضع (mode) | ماذا يفعل | الأداة |
|---|---|---|
| `nmap` | يشغّل Nmap الحقيقي على الهدف المحلي، ويتأكد أنه وجد المنفذ المفتوح. | Nmap حقيقي |
| `sqlmap` | يشغّل sqlmap الحقيقي على معامل `id` في الهدف المحلي، ليتأكد أنه اكتشف حقن SQL. يحتاج `SQLMAP_PATH` إذا لم يكن sqlmap في PATH. | sqlmap حقيقي |
| `metasploit` | يشغّل خطوة Metasploit **بشكل محاكى** (SIMULATED) باستخدام خادم وهمي. لا يتصل بالـ daemon الحقيقي. | محاكاة |
| `all` | يشغّل الأدوات الثلاث **واحدة بعد الأخرى** في خطة واحدة (Nmap ثم sqlmap ثم Metasploit المحاكى). | تسلسلي |
| `parallel` | يشغّل الأدوات الثلاث **في نفس الوقت**، كل واحدة في محرك (engagement) منفصل. | متوازي |

**أمثلة:**

```zsh
./backend/.venv/bin/python scripts/live_tests/beginner_tools_lab.py nmap
```

```powershell
.\backend\.venv\Scripts\python.exe scripts\live_tests\beginner_tools_lab.py nmap
```

**ماذا تعني النتيجة؟**
- `PASS` تعني أن الأداة شغّلت وأعطت النتيجة المتوقعة.
- `SIMULATED` تعني أن النتيجة من خادم وهمي، وليست Metasploit حقيقي.

## 3. تشغيل الأدوات على مواقع عامة (PUBLIC)

هذه الأوامر تزور مواقع حقيقية، لذلك:
- تحتاج الخيار `--confirm-public-tests` لتعمل. بدونه يرفض الأمر البدء.
- تُحفظ النتيجة في `docs/real_results.json`.
- لها حدود يومية: Nmap حوالي 10 مرات في 24 ساعة، وsqlmap 6 مرات في 24 ساعة.

### 3.1 Nmap على `scanme.nmap.org`

الملف: `scripts/live_tests/public_tool_results.py`

```zsh
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py nmap --confirm-public-tests
```

يفحص الموقع المسموح به فقط (`scanme.nmap.org`) بفحص بسيط للمنافذ. لا يقبل أي هدف من سطر الأوامر.

### 3.2 sqlmap على SekuMart

```zsh
./backend/.venv/bin/python scripts/live_tests/public_tool_results.py sqlmap --confirm-public-tests
```

يختبر معامل `id` فقط في صفحة المنتج في موقع SekuMart التجريبي. لا يستخرج بيانات.

### 3.3 كل الأدوات معاً (مع Metasploit الحقيقي)

الملف: `scripts/live_tests/run_all_tools.py`

```zsh
export MSF_RPC_PASSWORD="YOUR_STRONG_PASSWORD"
./backend/.venv/bin/python scripts/live_tests/run_all_tools.py --confirm-public-tests
```

يشغّل ثلاث محركات في نفس الوقت:
- Nmap على `scanme.nmap.org`
- sqlmap على SekuMart
- Metasploit الحقيقي على هدف محلي على جهازك

يحتاج `msfrpcd` شغّال، وكلمة المرور في `MSF_RPC_PASSWORD`. استبدل `YOUR_STRONG_PASSWORD` بكلمة مرورك، ولا تكتبها في أي محادثة.

## 4. سكربت العرض الكامل (Demo)

الملف: `scripts/demo/run_everything.py`

```zsh
./backend/.venv/bin/python scripts/demo/run_everything.py
```

يعمل بهذا الترتيب:
1. **Step 0:** يفحص ما هو مثبت: Python الخاص بالمشروع، Nmap، sqlmap، Metasploit، وPostgreSQL. ويكتب `OK` أو `MISSING` لكل عنصر.
2. **Step 1:** يشغّل الأدوات الثلاث على الهدف المحلي في نفس الوقت (`parallel`).
3. **Step 2:** يشغّل الاختبارات الآلية (228 اختبار) بدون قاعدة بيانات.
4. **Step 3:** لا يعمل إلا مع الخيار `--include-public`.
5. **Summary:** جدول بالنتائج في النهاية.

```zsh
./backend/.venv/bin/python scripts/demo/run_everything.py --include-public
```

يضيف Step 3 (المواقع العامة و Metasploit الحقيقي). يحتاج `MSF_RPC_PASSWORD` مضبوطاً قبلها.

## 5. الاختبارات الآلية (pytest)

```zsh
cd backend
./.venv/bin/python -m pytest --noconftest -q -k "not persist" tests/unit/test_pentest_tools.py
```

على ويندوز (PowerShell):

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest --noconftest -q -k "not persist" tests\unit\test_pentest_tools.py
Set-Location ..
```

| الجزء | معناه |
|---|---|
| `-m pytest` | يشغّل أداة الاختبارات pytest. |
| `--noconftest` | يتخطى إعداد قاعدة البيانات، فلا يحتاج PostgreSQL. |
| `-q` | يعرض ملخصاً مختصراً. |
| `-k "not persist"` | يتخطى الاختبارات التي تحتاج قاعدة بيانات (اسمها يحتوي `persist`). |
| `tests/unit/...` | الملفات التي تُشغَّل. |

**النتيجة المتوقعة:** `228 passed, 2 deselected`. الاختبارات الملغاة (deselected) هي التي تحتاج قاعدة بيانات.

## 6. ملخص سريع للخيارات

| الخيار | ماذا يفعل |
|---|---|
| `--confirm-public-tests` | إلزامي لأي أمر يزور موقعاً عاماً. يؤكد أنك راجعت قواعد الموقع وحدوده. |
| `--include-public` | يضيف خطوة المواقع العامة إلى سكربت العرض. بدونه تُتخطى. |
| `nmap` / `sqlmap` / `metasploit` / `all` / `parallel` | وضع التشغيل على الهدف المحلي. يحدد أي أداة تعمل. |

## 7. قواعد الأمان

- الأوامر لا تقبل هدفاً من المستخدم. الأهداف العامة ثابتة في الكود.
- Nmap يزور `scanme.nmap.org` فقط، وsqlmap يختبر معامل `id` في SekuMart فقط.
- لا تشغّل أوامر المواقع العامة أكثر من مرة إلا إذا طلب الفريق نتيجة جديدة.
- Metasploit الحقيقي يعمل على جهازك فقط، لأن لا يوجد موقع عام يسمح به.

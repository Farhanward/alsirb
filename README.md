# السرب AlSirb

السرب هو فريق وكلاء محلي مصغر يبني برنامجاً من وصف واحد، ثم يمرره على الحوكمة والفحص والاختبار قبل التسليم.

## آلية العمل

1. **intake** يفحص وصف المشروع عبر `C:\Projects\almunaa`.
2. **architect** يختار قالب البرنامج المناسب.
3. **implementer** يولد مشروع Python CLI كامل.
4. **reviewer** يتأكد من اكتمال الملفات.
5. **security** يفحص المشروع عبر `C:\Projects\kashif`.
6. **tester** يشغل الاختبارات عبر `C:\Projects\aegis_local` بلا `shell=True`.
7. **delivery** يكتب تقرير التسليم وسجل تدقيق hash-chain/HMAC.

السرب لا يستخدم Docker حالياً؛ الأدوار هي حاويات عمل منطقية داخل مساحة عمل واحدة، وكل دور يترك ملفاً قابلاً للمراجعة.

## تشغيل سريع

```powershell
python -m alsirb.cli run --brief "ابن لي تطبيق مهام محلي بسيط" --name demo_tasks
```

## بيانات اختبار كبيرة من الإنترنت

```powershell
python -m alsirb.cli download-benchmark --out data\benchmarks\alsirb_neuralchemy_tasks.jsonl
python -m alsirb.cli batch --input data\benchmarks\alsirb_neuralchemy_tasks.jsonl
python -m alsirb.cli stress --input data\benchmarks\alsirb_neuralchemy_tasks.jsonl --repeat 3
```

المصدر: Hugging Face `neuralchemy/Prompt-injection-dataset`.

## التحقق

```powershell
python -m unittest discover -s tests -v
python -m alsirb.cli verify-ledger
```

## آخر نتائج

- Smoke run: بنى مشروع مهام محلي في `workspaces\smoke-tasks-20260704-152653-ae85a931\project`.
- كاشف على المشروع الناتج: 6 ملفات، 0 ملاحظات، PASS.
- AEGIS على الاختبارات: ALLOW، الاختبارات PASS.
- الاختبارات الذاتية: 5/5 ناجحة.
- دفتر التدقيق: `ledger verified` بعد 15 سجلاً.
- Benchmark كامل: 15,919 سجل، Accuracy=95.29%، Precision=97.71%، Recall=94.65%، Specificity=96.34%، F1=96.16%.
- Stress: 47,757 فحص، 0 أخطاء، p99=14.66ms، peak memory=12.75MB، PASS.

## تحسينات إنتاجية 2026-07-04

- أصبحت نقطة دخول CLI في المشاريع المولدة تأتي بعد تعريف `build_parser` و`dispatch`، لذلك يعمل `python -m <package>.cli` فعلياً ولا يفشل بسبب ترتيب التعريفات.
- أصبح أمر الاختبار الذي يرسله السرب إلى AEGIS هو الصيغة الكاملة المحددة `python -m unittest discover -s tests -v`، ومسموح بها كأمر مطابق بالكامل داخل السياسة المحلية.
- أضيف اختبار انحدار يولد مشروع مهام ثم ينفذ CLI الناتج ويكتب قاعدة JSON حقيقية، لضمان أن التسليم ليس مجرد ملفات ساكنة.

## التشغيل المؤسسي (Enterprise) — v1.0.0

- **خدمة HTTP للفحص المسبق**: `python -m alsirb.cli serve` → `POST /api/preflight {"brief": "..."}` يعيد `allowed/action/findings`.
- **قرار أمني**: البناء الكامل (`run`) عبر CLI فقط — الخدمة الشبكية لا تكتب workspaces ولا تنفذ كوداً مولداً.
- **نقاط فحص**: `/api/health` (مفتوح) · `/api/version` · `/api/metrics`.
- **تهيئة عبر البيئة**: متغيرات `ALSIRB_*` — انظر `docs/OPERATIONS.md`.
- **مصادقة**: `ALSIRB_API_KEY` → ترويسة `X-API-Key`. **سجلات JSON**: `logs\alsirb.service.jsonl`.

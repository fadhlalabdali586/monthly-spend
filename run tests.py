#!/usr/bin/env python3
"""اختبارات «لوحة التوزيع» — ملف واحد، بيانات وهمية بالكامل (ما فيه أي بيانات حقيقية).

التشغيل:  python3 run_tests.py path/to/index.html
يحتاج:    pip install playwright  (ومتصفح Chromium)
كل اختبار يبدأ من جوال فاضي (localStorage نظيف) بتاريخ ثابت 30/9/2026 مساءً،
ويبني بياناته الوهمية بنفسه. أي فشل يطلع باسمه وسببه، والنتيجة النهائية PASS/FAIL.
"""
import asyncio, functools, http.server, json, os, socketserver, sys, threading
from playwright.async_api import async_playwright

HTML = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'index.html')
NOW = '2026-09-30T19:45:00'

# ---------- سيرفر محلي ----------
def serve(directory):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
    h = functools.partial(Q, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s.server_address[1]

RESULTS = []
def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print(('  ✓ ' if cond else '  ✗ ') + name + ('' if cond else f'   ← {detail}'))

# ---------- بيانات وهمية أساسية ----------
BASE = """()=>{
  const P=id=>S.pays.find(p=>p.id===id);
  P('credit').name='الائتمانية 1111'; P('mada').name='مدى 2222';
  S.cfg={own:'مختبر,TEST USER',fixed:'الوالدة'};
  S.auto.url='https://x.test/exec'; S.auto.key='k'; S.auto.pending=[]; S.balFloor=7000;
  const cap=M().lines.find(l=>l.kind==='cap'); if(cap) cap.amount=2000;
  save(); refreshAll(); renderInbox(); setTab('today');
}"""

def row(i, t, frm, text):
    return {"id": 1790800000000 + i, "time": t, "from": frm, "text": text}

AHLI_CREDIT_BUY = lambda amt, mer, bal, hhmm='12:00', day='30/09/26': f"شراء-POS\nبـSAR {amt}\nمن {mer}\nإئتمانية **1111 (Apple Pay)\nفي {day} {hhmm}\nالصرف المتبقي SAR {bal}"
AHLI_CREDIT_TOPUP = lambda amt, bal, hhmm='12:00': f"شراء إنترنت (Apple Pay)\nمبلغ SAR {amt}\nبطاقة ائتمانية ***1111\nمن barq\nالتاريخ {hhmm} 30/09/26\nالصرف المتبقي SAR {bal}"
AHLI_MADA_TOPUP = lambda amt, hhmm='12:00': f"شراء انترنت\nبـSAR {amt}\nمن *0000\nمن barq\nمدى-ابل *2222\nفي {hhmm} 30/09/26"
BARQ_BUY = lambda amt, mer: f"شراء إنترنت\nبطاقة فيزا\nمبلغ 10 USD ({amt} SAR)\nلدى {mer}\n2026-09-30 13:00"
BARQ_SELF_OUT = lambda amt: f"حوالة صادرة محلية\nمبلغ{amt}SAR\nرسوم0.00SAR\nالى Test User\nبنكALAHLI BANK\nلحساب9999\n2026-09-30 17:50"


async def main():
    port = serve(os.path.dirname(HTML))
    url = f'http://127.0.0.1:{port}/{os.path.basename(HTML)}'
    rows = {'r': []}
    async with async_playwright() as p:
        b = await p.chromium.launch()

        async def fresh(setup=BASE, viewport=(390, 844)):
            ctx = await b.new_context(viewport={"width": viewport[0], "height": viewport[1]})
            await ctx.add_init_script("(()=>{const D=Date;const T=new D('%s').getTime();class F extends D{constructor(...a){a.length?super(...a):super(T)}static now(){return T}};window.Date=F})()" % NOW)
            async def route(r):
                u = r.request.url
                if u.startswith(f'http://127.0.0.1:{port}'):
                    await r.continue_()
                elif u.startswith('https://x.test/'):
                    await r.fulfill(status=200, content_type='application/json', body=json.dumps({"ok": True, "rows": rows['r']}))
                else:
                    await r.abort()
            await ctx.route('**/*', route)
            pg = await ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(url)
            await pg.evaluate("typeof noFlush!=='undefined'&&(noFlush=true);localStorage.clear()")
            await pg.reload()
            await pg.wait_for_timeout(900)
            if setup:
                await pg.evaluate(setup)
            pg._errs = errs
            return ctx, pg

        async def sync(pg, r):
            rows['r'] = r
            await pg.evaluate('S.auto.since=0;S.auto.seen=[];save()')
            await pg.evaluate('syncSms(true)')
            await pg.wait_for_timeout(500)

        # 1) فهم رسائل البنك (العينات المدمجة في اللوحة)
        print('١) فهم رسائل البنك')
        ctx, pg = await fresh()
        bad = await pg.evaluate("HC_SAMPLES.filter(([f,t,k,a])=>{const p=parseSms(t,f);return p.kind!==k||!sameAmt(p.amt,a)}).map(x=>x[2])")
        check('كل الصيغ المدمجة تنفهم صح', not bad, bad)
        r = await pg.evaluate("[parseSms('حوالة واردة داخلية بـSAR 50\\nمن 0000* سالم الأحمد\\n30/09/26 10:00','SNB-AlAhli').person, parseSms('حوالة واردة محلية ب SAR 2\\nمن*0000 TEST USER\\n30/09/26 17:52','SNB-AlAhli').kind]")
        check('اسم بعد رقم فيه نجمة يطلع بدون نجمة', r[0] == 'سالم الأحمد', r[0])
        check('تحويل من اسمك يتجاهل', r[1] == 'ignore', r[1])
        await ctx.close()

        # 2) الراتب والدورات
        print('٢) الراتب والدورات')
        ctx, pg = await fresh(setup=None)
        r = await pg.evaluate("[['2026-10',28],['2026-11',29],['2027-5',27],['2027-8',29],['2026-12',28]].map(([k,d])=>{const[y,m]=k.split('-').map(Number);return salaryDayOf(y,m).getDate()===d})")
        check('الراتب: الجمعة ← الخميس، السبت ← الأحد', all(r), r)
        c = await pg.evaluate("(()=>{const c=cycleOf('2026-12');return [c.st.getDate(),c.st.getMonth()+1,c.en.getDate(),c.en.getMonth()+1]})()")
        check('دورة ديسمبر 29/11 → 27/12', c == [29, 11, 27, 12], c)
        cur = await pg.evaluate('S.current')
        check('تثبيت جديد يوم 30/9 يبدأ بدورة أكتوبر', cur == '2026-10', cur)
        await ctx.close()

        # 3) رسائل الائتمانية والرصيد
        print('٣) الرصيد من رسائل البنك')
        ctx, pg = await fresh()
        await sync(pg, [row(1, '2026-09-30T12:00:00', 'SNB-AlAhli', AHLI_CREDIT_BUY('46.00', 'Test Shop', '7950.00'))])
        v = await pg.evaluate("[S.bal.c.val, S.auto.pending.length, S.auto.pending[0].balSkip]")
        check('رسالة الشراء تحدّث رصيد الائتمانية', v[0] == 7950 and v[1] == 1 and v[2] == 'c', v)
        await pg.evaluate("ibApprove(S.auto.pending[0].id,'dining')")
        check('تسجيل العملية ما يخصمها مرتين', await pg.evaluate("balLive('c')") == 7950, await pg.evaluate("balLive('c')"))
        await ctx.close()

        # 4) برق: الشحن، الباقي، الشراء
        print('٤) برق')
        ctx, pg = await fresh()
        await sync(pg, [row(1, '2026-09-30T10:00:00', 'SNB-AlAhli', AHLI_CREDIT_TOPUP('50.00', '1000.00', '10:00')),
                        row(2, '2026-09-30T13:00:00', 'barq app', BARQ_BUY('45.00', 'NETFLIX'))])
        v = await pg.evaluate("[S.bal.c.val, JSON.stringify(S.barqPool), S.auto.pending[0].pay, S.auto.pending[0].via||'']")
        check('الشحن ينضاف للرصيد كـ«باقي في برق»', v[0] == 1050, v)
        check('شراء برق ينحسب على البطاقة اللي شحنت', v[2] == 'credit' and v[3] != '', v)
        await pg.evaluate("ibApprove(S.auto.pending[0].id,'subs')")
        check('الرصيد = البطاقة + الباقي في برق (1005)', await pg.evaluate("balLive('c')") == 1005, await pg.evaluate("balLive('c')"))
        await ctx.close()

        ctx, pg = await fresh()
        await sync(pg, [row(1, '2026-09-30T15:57:00', 'SNB-AlAhli', AHLI_MADA_TOPUP('1', '15:57')),
                        row(2, '2026-09-30T15:57:20', 'SNB-AlAhli', AHLI_CREDIT_TOPUP('1.00', '7990.00', '15:57')),
                        row(3, '2026-09-30T15:57:30', 'barq app', 'إضافة اموال\n1.0 SAR\nالبطاقة: **1111 , ابل باي\n2026-09-30 15:57')])
        pool = await pg.evaluate('S.barqPool')
        check('شحنتين من بطاقتين = شحنتين، ورسالتين لنفس الشحنة = وحدة', pool.get('mada') == 1 and pool.get('credit') == 1, pool)
        await sync(pg, [row(4, '2026-09-30T17:50:00', 'barq app', BARQ_SELF_OUT('2.00'))])
        pool = await pg.evaluate('S.barqPool')
        check('التحويل من برق لحسابك يصفّر الباقي', (pool.get('mada') or 0) == 0 and (pool.get('credit') or 0) == 0, pool)
        await ctx.close()

        # 5) تنبيه التكرار: الشراء بدل الشحن اليدوي
        print('٥) الشراء بدل الشحن اليدوي')
        ctx, pg = await fresh()
        await pg.evaluate("M().expenses.push({id:'man1',cat:'bills',amt:60.5,date:'2026-09-28',d:'28/9',pay:'credit',note:'اشتراك'});S.barqSrc='credit';save()")
        await sync(pg, [row(1, '2026-09-30T12:04:00', 'barq app', BARQ_BUY('60.48', 'TEST SUB'))])
        await pg.evaluate("renderInbox();setTab('today')")
        check('يطلع تنبيه «مكررة مع شحن سجلته بيدك»', await pg.evaluate("!!document.querySelector('[data-bqfix]')"))
        await pg.click('[data-bqfix]')
        await pg.wait_for_timeout(200)
        v = await pg.evaluate("JSON.stringify(M().expenses.filter(e=>e.amt>60&&e.amt<61).map(e=>[e.id==='man1',e.amt,e.pay,!!e.via]))")
        check('الزر يسجل الشراء ويشيل الشحن اليدوي', json.loads(v) == [[False, 60.48, 'credit', True]], v)
        await ctx.close()

        # 6) ترحيل البيانات القديمة (نسخة احتياطية قديمة)
        print('٦) ترحيل قديم')
        ctx, pg = await fresh(setup=None)
        await pg.evaluate("""()=>{const bq=S.pays.find(p=>/برق/.test(p.name)).id;delete S.migBarq1;
          M().expenses.push({id:'m1',cat:'bills',amt:60.5,date:'2026-09-28',d:'28/9',pay:'credit',note:'Stream'},{id:'m2',cat:'bills',amt:60.48,date:'2026-09-30',d:'30/9',pay:bq,note:'STREAM SUB',src:'sms'});
          S.lnAlias={'* سالم الأحمد':'سالم'};save()}""")
        await pg.wait_for_timeout(450); await pg.reload(); await pg.wait_for_timeout(900)
        v = await pg.evaluate("JSON.stringify(M().expenses.filter(e=>['m1','m2'].includes(e.id)).map(e=>[e.id,e.pay,!!e.via]))")
        check('يخلي الشراء (على الائتمانية عبر برق) ويشيل الشحن', json.loads(v) == [['m2', 'credit', True]], v)
        check('أسماء السلف المتعلمة تنظفت من النجمة', await pg.evaluate("S.lnAlias['سالم الأحمد']==='سالم'"))
        await ctx.close()

        # 7) السلف
        print('٧) السلف')
        ctx, pg = await fresh()
        await pg.evaluate("addLoan('سالم',300,'2026-09-01','','manual');save()")
        await sync(pg, [row(1, '2026-09-30T08:13:00', 'SNB-AlAhli', 'حوالة واردة داخلية بـSAR 300\nمن 0000* سالم الأحمد\n30/09/26 08:13')])
        m = await pg.evaluate("JSON.stringify(loanMatches(S.auto.pending[0]).map(x=>[x.person,x.strong]))")
        check('الحوالة الواردة تتعرف كسداد سلفة', json.loads(m) == [['سالم', True]], m)
        await pg.evaluate("payPerson(S.loans[0].id,300,'2026-09-30','تحويل')")
        check('السداد يقفل السلفة', await pg.evaluate("lnRemain(S.loans[0])") == 0)
        await ctx.close()

        # 8) الأرقام العربية
        print('٨) الأرقام العربية')
        ctx, pg = await fresh()
        r = await pg.evaluate("['٥٠٫٧٥','١٬٣٠٠','1,300','۱۲۳','-٢٥'].map(toEnDigits)")
        check('تحويل الأرقام العربية', r == ['50.75', '1300', '1300', '123', '-25'], r)
        await pg.evaluate("document.getElementById('addMask').classList.add('on')")
        await pg.focus('#amt'); await pg.keyboard.type('٤٥٫٥')
        check('الكتابة بالكيبورد العربي في خانة المبلغ', await pg.input_value('#amt') == '45.5', await pg.input_value('#amt'))
        await ctx.close()

        # 9) الرئيسية: الرقم اليومي والتقويم وورقة اليوم
        print('٩) التقويم وورقة اليوم')
        ctx, pg = await fresh()
        await pg.evaluate("""()=>{const E=[['bills',110,'2026-09-28','credit','فاتورة نت'],['dining',25,'2026-09-28','mada','مطعم'],['fuel',95.4,'2026-09-29','mada','محطة'],['grocery',12.5,'2026-09-29','mada','بقالة'],['coffee',18,'2026-09-30','mada','قهوة']];
          E.forEach((x,i)=>M().expenses.push({id:'e'+i,cat:x[0],amt:x[1],date:x[2],d:shortD(x[2]),pay:x[3],note:x[4]}));
          balAnchor('c',7900);balAnchor('a',600);balAnchor('k',0);save();refreshAll();setTab('today')}""")
        per = await pg.evaluate('calPer')
        check('الرقم اليومي = المتاح ÷ الأيام لين الراتب', per == int((900 + 600) / 28), per)
        cls = await pg.evaluate("Object.fromEntries([...document.querySelectorAll('#cal [data-d]')].map(x=>[x.dataset.d,x.className]))")
        check('28/9 أخضر (الفاتورة ما تنحسب)', 'ok' in cls.get('2026-09-28', ''), cls)
        check('29/9 أحمر (فوق المسموح)', 'over' in cls.get('2026-09-29', ''), cls)
        check('30/9 محدد كاليوم', 'today' in cls.get('2026-09-30', ''), cls)
        check('مربع الراتب 28 أكتوبر', await pg.evaluate("document.querySelector('#cal .cl.pay').textContent.includes('28')"))
        await pg.click('#cal [data-d="2026-09-29"]'); await pg.wait_for_timeout(300)
        names = await pg.evaluate("[...document.querySelectorAll('#daySheet .ds-row b')].map(x=>x.textContent)")
        check('ورقة اليوم مرتبة من الأكبر', names == ['محطة', 'بقالة'], names)
        await pg.click('[data-dnav="-1"]'); await pg.wait_for_timeout(150)
        check('الأسهم تتنقل، والفواتير في قسم لحالها', await pg.evaluate("document.querySelector('.ds-row.bill b').textContent") == 'فاتورة نت')
        check('ما فيه يوم قبل بداية الدورة', await pg.evaluate("document.querySelector('[data-dnav=\"-1\"]').disabled"))
        await pg.click('[data-dadd]'); await pg.wait_for_timeout(250)
        check('«أضف مصروف لهذا اليوم» يحط التاريخ', await pg.input_value('#eDate') == '2026-09-28', await pg.input_value('#eDate'))
        await ctx.close()

        # 10) الإخفاء
        print('١٠) وضع الإخفاء')
        ctx, pg = await fresh()
        await pg.evaluate("balAnchor('c',7900);balAnchor('a',600);save();refreshAll()")
        await pg.wait_for_timeout(1500); await pg.click('#eye'); await pg.wait_for_timeout(800)
        v = await pg.evaluate("[document.getElementById('remain').textContent, document.querySelector('#cal .cl.today').textContent.trim()]")
        check('المبالغ تختفي وأرقام الأيام تبقى', v[0] == '••••' and v[1] == '30', v)
        await ctx.close()

        # 11) الحفظ لو سكّرت التطبيق بسرعة
        print('١١) الحفظ السريع')
        ctx, pg = await fresh()
        await pg.evaluate("M().expenses.push({id:'q1',cat:'dining',amt:9,date:'2026-09-30',d:'30/9',pay:'mada',note:'سريع'});save();document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('pagehide'))")
        saved = await pg.evaluate("JSON.parse(localStorage.getItem(KEY)).months[S.current].expenses.some(e=>e.id==='q1')")
        check('التعديل ينحفظ فوراً لو طلعت من التطبيق', saved)
        await ctx.close()

        # 12) الاسترجاع ما ينكتب فوقه
        print('١٢) الاسترجاع')
        ctx, pg = await fresh()
        await pg.evaluate("""()=>{const snap=JSON.parse(JSON.stringify(S));snap.months[snap.current].expenses=[{id:'old1',cat:'dining',amt:5,date:'2026-09-29',d:'29/9',pay:'mada',note:'من النسخة'}];
          localStorage.setItem(PREV_KEY,JSON.stringify({at:Date.now(),data:JSON.stringify(snap)}));renderPrev();
          M().expenses.push({id:'new1',cat:'dining',amt:7,date:'2026-09-30',d:'30/9',pay:'mada',note:'بعد'});save();window.ask=async()=>true}""")
        await pg.evaluate("document.getElementById('prevBack').click()")
        await pg.wait_for_timeout(1500)
        ids = await pg.evaluate("M().expenses.map(e=>e.id)")
        check('استرجاع النسخة المحلية ما ينكتب فوقه', ids == ['old1'], ids)
        await ctx.close()

        # 13) الأسماء بصيغة الأهلي الجديدة «مرسل:» و«إلى:»
        print('١٣) أسماء الأهلي')
        ctx, pg = await fresh()
        r = await pg.evaluate("""[
          parseSms('حوالة واردة داخلية\\nمبلغ:SAR 296\\nمرسل:سالم الأحمد\\nمن:*0000*\\nإلى:*1111*\\nفي:18:35 28/09/26','SNB-AlAhli'),
          parseSms('حوالة صادرة داخلية\\nمبلغ:SAR 300\\nإلى:الوالدة الكريمة\\nإلى:*0000*\\nفي:08:25 29/09/26','SNB-AlAhli'),
          parseSms('حوالة واردة داخلية\\nمبلغ:SAR 100\\nمرسل:TEST USER\\nمن:*0000*\\nإلى:*1111*\\nفي:10:00 29/09/26','SNB-AlAhli'),
          parseSms('حوالة واردة داخلية\\nمبلغ:SAR 2600\\nمرسل:شركة تجربة للصناعة المحد\\nمن:*0000*\\nإلى:*1111*\\nفي:14:19 29/09/26','SNB-AlAhli'),
          parseSms('حوالة صادرة داخلية\\nمبلغ:SAR 1000\\nإلى:سالم الأحمد\\nإلى:*5404*\\nفي:08:25 29/09/26','SNB-AlAhli')
        ].map(p=>[p.kind,p.person||'',p.inc||'',p.why||''])""")
        check('«مرسل:الاسم» ينقرى', r[0][:2] == ['in', 'سالم الأحمد'], r[0])
        check('«إلى:الوالدة» = بند ثابت يتجاهل', r[1][0] == 'ignore' and r[1][3] == 'بند ثابت', r[1])
        check('«مرسل:اسمك» = تحويل لنفسك', r[2][0] == 'ignore' and r[2][3] == 'تحويل لنفسك', r[2])
        check('مرسل شركة = دخل/تعويض مو سلفة', r[3][0] == 'in' and r[3][2] == 'co', r[3])
        check('«إلى:الاسم» في الصادرة ينقرى (مو رقم الحساب)', r[4][:2] == ['out', 'سالم الأحمد'], r[4])
        await pg.evaluate("addLoan('سالم',296,'2026-09-01','','manual');save()")
        await sync(pg, [row(1, '2026-09-28T18:35:00', 'SNB-AlAhli', 'حوالة واردة داخلية\nمبلغ:SAR 296\nمرسل:سالم الأحمد\nمن:*0000*\nإلى:*1111*\nفي:18:35 28/09/26')])
        m = await pg.evaluate("JSON.stringify(loanMatches(S.auto.pending[0]).map(x=>[x.person,x.strong]))")
        check('سداد السلفة يتعرف بالصيغة الجديدة', json.loads(m) == [['سالم', True]], m)
        await ctx.close()

        # 14) الراتب والبونص
        print('١٤) الراتب والبونص')
        SAL = lambda amt, d='28/09/26': f"حوالة واردة راتب\nمبلغ SAR {amt}\nحساب*0000\nفي 06:48 {d}"
        ctx, pg = await fresh()
        await pg.evaluate("M().salary=5000;save()")
        await sync(pg, [row(1, '2026-09-28T06:48:00', 'SNB-AlAhli', SAL(5000))])
        v = await pg.evaluate("[S.auto.pending.length, paydayRec().done.salary===true, paydayRec().auto.salary===true]")
        check('حوالة الراتب المعتادة تعلّم «نزل الراتب» وما تطلع عملية', v == [0, True, True], v)
        await sync(pg, [row(2, '2026-09-28T06:49:00', 'SNB-AlAhli', SAL(9000))])
        v = await pg.evaluate("[S.auto.pending.length, S.auto.pending[0]&&S.auto.pending[0].inc, S.auto.pending[0]&&S.auto.pending[0].label]")
        check('حوالة «راتب» بمبلغ ثاني (بونص) تطلع في العمليات الجديدة', v[0] == 1 and v[1] == 'sal', v)
        await pg.evaluate("renderInbox();setTab('today')")
        check('بدون خطة: ما فيه زر «وزّعه حسب الخطة»', await pg.evaluate("!document.querySelector('[data-bonus]')"))
        await pg.evaluate("(()=>{const o=incDestOptions().map(x=>x.v);S.bonus={plan:{[o[0]]:30,[o[1]]:70},lastBasic:5000};save();renderInbox();setTab('today')})()")
        await pg.click('[data-bonus]'); await pg.wait_for_timeout(250)
        v = await pg.evaluate("JSON.stringify([S.auto.pending.length, M().income.map(x=>x.amt), M().income.reduce((t,x)=>t+x.amt,0), S.bonus.last])")
        check('«وزّعه حسب الخطة» يقسم 30/70 ويحفظ آخر بونص', json.loads(v) == [0, [2700, 6300], 9000, 9000], v)
        await sync(pg, [row(3, '2026-09-29T09:00:00', 'SNB-AlAhli', SAL(5000, '29/09/26'))])
        v = await pg.evaluate("[S.auto.pending.length, !!document.querySelector('[data-ib] [data-sal]')]")
        check('حوالة راتب ثانية بعد الراتب ما تنبلع — تطلع وتسألك', v[0] == 1, v)
        await pg.evaluate("renderInbox();setTab('today')")
        await pg.click('[data-sal]'); await pg.wait_for_timeout(200)
        check('«هذا راتبي» يشيلها', await pg.evaluate("S.auto.pending.length") == 0)
        await ctx.close()

        # 15) الأرباح وإيداع الصراف وسداد الفواتير
        print('١٥) الأرباح والإيداع والفواتير')
        ctx, pg = await fresh()
        await pg.evaluate("balAnchor('k',500);balAnchor('a',600);save()")
        await sync(pg, [row(1, '2026-09-30T07:25:00', 'AlRajhiBank', 'ايداع:الأرباح الشهرية لحساب الادخار\nمبلغ:SAR 40\nإلى:0000\n07:25 30/9/26'),
                        row(2, '2026-09-30T10:00:00', 'SNB-AlAhli', 'ايداع صراف آلي\nمبلغ SAR 100\nحساب 000*000\nفي 10:00 30/09/26'),
                        row(3, '2026-09-30T19:45:00', 'SNB-AlAhli', 'سداد فاتورة\nمبلغ SAR 200\nمن 000*000\nمفوتر 123\nفاتورة 0000\nفي 19:45 30/09/26')])
        v = await pg.evaluate("JSON.stringify(S.auto.pending.map(p=>[p.kind,p.inc||'',p.label,p.cat||'',p.mkey||'']))")
        P = json.loads(v)
        check('الأرباح تطلع «عائد حساب الطوارئ»', P[0][:3] == ['in', 'profit', 'عائد حساب الطوارئ'], P)
        check('إيداع الصراف يطلع كإيداع كاش', P[1][0] == 'dep', P)
        check('سداد فاتورة = مصروف فواتير', P[2][0] == 'expense' and P[2][2] == 'سداد فاتورة · مفوتر 123' and P[2][3] == 'bills' and P[2][4] == 'sadad123', P)
        sav0 = await pg.evaluate("M().assets.find(a=>a.id==='sav').val")
        await pg.evaluate("renderInbox();setTab('today')")
        check('زر الأرباح يقول وين بيروح (حساب الادخار)', 'حساب الادخار' in await pg.inner_text('[data-inc-prof]'), await pg.inner_text('[data-inc-prof]'))
        await pg.click('[data-inc-prof]'); await pg.wait_for_timeout(200)
        v = await pg.evaluate("JSON.stringify([M().income.map(x=>[x.amt,x.dest]), M().assets.find(a=>a.id==='sav').val])")
        check('الأرباح بضغطة تروح حساب الادخار', json.loads(v)[0] == [[40, 'asset:sav']] and json.loads(v)[1] - sav0 == 40, v)
        await pg.click('[data-dep]'); await pg.wait_for_timeout(200)
        v = await pg.evaluate("[balLive('k'),balLive('a')]")
        check('«من كاشي لحساب المصروف» ينقل 100 من الكاش لمدى', v == [400, 700], v)
        # يتذكر الوجهة لو اخترت غيرها
        await sync(pg, [row(9, '2026-09-30T08:00:00', 'AlRajhiBank', 'ايداع:الأرباح الشهرية لحساب الادخار\nمبلغ:SAR 12\nإلى:0000\n08:00 30/9/26')])
        await pg.evaluate("renderInbox();setTab('today')")
        await pg.click('[data-ib] [data-inc-in]'); await pg.wait_for_timeout(250)
        check('«وجهة ثانية» يفتح على حساب الادخار', await pg.evaluate("document.querySelector('#incDest input:checked').value") == 'asset:sav')
        await pg.evaluate("document.querySelector('#incDest input[value=\"cap\"]').checked=true")
        await pg.click('#incSave'); await pg.wait_for_timeout(250)
        check('يتذكر اختيارك للأرباح الجاية', await pg.evaluate("profitDest()") == 'cap', await pg.evaluate("profitDest()"))
        # الدخل يطلع في العمليات
        await pg.evaluate("renderCap();setTab('today')")
        check('آخر العمليات تعرض الدخل', await pg.evaluate("document.querySelectorAll('#log [data-inced]').length") >= 1)
        await pg.evaluate("setTab('month');renderAllOps()")
        v = await pg.evaluate("[document.querySelectorAll('#allOps [data-inced]').length, !!document.querySelector('[data-oa=\"i\"]'), document.getElementById('opsSum').textContent]")
        check('كل العمليات فيها الدخل وفلتر «دخل»', v[0] == 2 and v[1] and '+52' in v[2], v)
        await pg.click('[data-oa="i"]'); await pg.wait_for_timeout(150)
        check('فلتر «دخل» يعرض الدخل بس', await pg.evaluate("[document.querySelectorAll('#allOps [data-inced]').length, document.querySelectorAll('#allOps [data-ed]').length]") == [2, 0])
        await pg.evaluate("openDay('2026-09-30')"); await pg.wait_for_timeout(200)
        v = await pg.evaluate("[document.querySelectorAll('#daySheet [data-dinc]').length, document.querySelector('.ds-total').textContent]")
        check('ورقة اليوم: الدخل في قسم لحاله وما ينحسب على صرفك', v[0] == 2 and v[1].startswith('0'), v)
        await pg.click('#daySheet [data-dinc]'); await pg.wait_for_timeout(200)
        check('الضغط على الدخل يفتح تعديله', await pg.evaluate("document.getElementById('incMask').classList.contains('on')&&document.getElementById('incTitle').textContent==='تعديل الدخل'"))
        await ctx.close()

        # 15ب) برق: فلوس الراجحي تمر من برق
        print('١٥ب) برق والراجحي')
        ctx, pg = await fresh()
        await pg.evaluate("balAnchor('c',8000);S.barqPool={credit:5};S.barqSrc='credit';S.bal.c.val=8005;save()")
        await sync(pg, [row(1, '2026-09-30T09:00:00', 'barq app', 'حوالة واردة محلية\nمبلغ40SAR\nمن Test User\n2026-09-30 09:00')])
        v = await pg.evaluate("[JSON.stringify(S.barqPool), balLive('c'), S.auto.pending.length]")
        check('التحويل الداخل لبرق ما يخصم من باقي الائتمانية', json.loads(v[0]) == {'credit': 5, 'ext': 40} and v[1] == 8005 and v[2] == 0, v)
        await sync(pg, [row(2, '2026-09-30T09:05:00', 'barq app', BARQ_SELF_OUT('40.00'))])
        v = await pg.evaluate("[JSON.stringify(S.barqPool), balLive('c')]")
        check('الطالع من برق ينخصم من فلوس الراجحي أول', json.loads(v[0]) == {'credit': 5, 'ext': 0} and v[1] == 8005, v)
        await pg.evaluate("S.barqPool={};S.barqLastTop=null;save()")
        await sync(pg, [row(3, '2026-09-30T10:00:00', 'barq app', 'إضافة اموال\n30.0 SAR\nالبطاقة: **9999 , ابل باي\n2026-09-30 10:00'),
                        row(4, '2026-09-30T10:00:20', 'SNB-AlAhli', AHLI_CREDIT_TOPUP('30.00', '7970.00', '10:00'))])
        v = await pg.evaluate("JSON.stringify(S.barqPool)")
        check('رسالة برق قبل رسالة البنك: الشحنة تنحسب مرة وحدة على البطاقة', json.loads(v) == {'ext': 0, 'credit': 30}, v)
        await ctx.close()

        # 16) خطة البونص في الأهداف
        print('١٦) خطة البونص')
        ctx, pg = await fresh()
        await pg.evaluate("setTab('goals')"); await pg.wait_for_timeout(200)
        check('بطاقة البونص تطلع وفيها تنبيه بدون خطة', await pg.evaluate("!!document.querySelector('#bonusCard .bn-nudge')"))
        await pg.fill('#bnLast', '٩٠٠٠'); await pg.fill('#bnLastB', '5000'); await pg.fill('#bnBasic', '5500')
        ins = await pg.query_selector_all('[data-bnp]')
        await ins[0].fill('40'); await ins[1].fill('50')
        check('المجموع يتنبه لو مو 100', '90' in await pg.inner_text('#bnSum'), await pg.inner_text('#bnSum'))
        await pg.click('#bnSave'); await pg.wait_for_timeout(150)
        check('ما يحفظ والمجموع 90%', await pg.evaluate("!(S.bonus&&S.bonus.plan)"))
        await ins[1].fill('60')
        await pg.click('#bnSave'); await pg.wait_for_timeout(250)
        v = await pg.evaluate("[S.bonus.last,S.bonus.lastBasic,S.bonus.basic,bonusPlanOk(),document.querySelector('.bn-top b').textContent]")
        check('يحفظ الأرقام (والعربي ينقلب) والخطة', v[:4] == [9000, 5000, 5500, True], v)
        check('المتوقع = 1.8 × الأساسي الحالي (≈ 9,900)', '9,900' in v[4], v[4])
        await ctx.close()

        # 17) صحة النظام وسجل الأخطاء بعد جولة كاملة
        print('١٧) صحة النظام')
        ctx, pg = await fresh()
        await sync(pg, [row(1, '2026-09-30T12:00:00', 'SNB-AlAhli', AHLI_CREDIT_BUY('10.00', 'Test', '7990.00'))])
        for t in ['month', 'goals', 'settings', 'today']:
            await pg.evaluate(f"setTab('{t}')"); await pg.wait_for_timeout(200)
        await pg.evaluate("openDay('2026-09-30');openBal();document.querySelectorAll('.mask.on').forEach(x=>x.classList.remove('on'))")
        await pg.evaluate('runHealth()'); await pg.wait_for_timeout(1500)
        res = await pg.evaluate("S.health.res.map(r=>[r.st,r.t])")
        check('فحص الصحة يشتغل', len(res) > 5, res)
        check('ما فيه أخطاء داخلية بعد جولة كاملة', await pg.evaluate('errList(7).length') == 0, await pg.evaluate('JSON.stringify(errList(7))'))
        check('ما فيه أخطاء JavaScript في الصفحة', not pg._errs, pg._errs)
        await ctx.close()

        await b.close()

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{'PASS' if not failed else 'FAIL'} — {len(RESULTS) - len(failed)}/{len(RESULTS)} نجحت")
    for n, _, d in failed:
        print('  ✗', n, '←', d)
    sys.exit(1 if failed else 0)

asyncio.run(main())

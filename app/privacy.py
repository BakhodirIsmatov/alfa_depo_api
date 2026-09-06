# Embedded legal copy and CSS remain readable as complete HTML lines.
# ruff: noqa: E501

from dataclasses import dataclass
from textwrap import dedent

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/api/privacy-policy", tags=["Legal"])

_CANONICAL_BASE = "https://api-depo.xtrial.uz/api/privacy-policy"
_EFFECTIVE_DATE = "6 September 2026"


@dataclass(frozen=True)
class PolicyCopy:
    language: str
    locale_name: str
    title: str
    subtitle: str
    effective_label: str
    effective_date: str
    contents_label: str
    contact_label: str
    body: str


_POLICIES = {
    "tr": PolicyCopy(
        language="tr",
        locale_name="Türkçe",
        title="Gizlilik Politikası",
        subtitle="Alfateks Depo mobil uygulaması ve ilişkili depo API hizmetleri",
        effective_label="Yürürlük tarihi",
        effective_date="6 Eylül 2026",
        contents_label="İçindekiler",
        contact_label="Gizlilik talebi gönder",
        body=dedent(
            """
            <section id="controller">
              <h2>1. Veri sorumlusu ve kapsam</h2>
              <p>Bu politika, Alfateks Tekstil Ürünleri Madencilik Sanayi ve Ticaret A.Ş. ("Alfateks", "biz") tarafından sunulan Alfateks Depo mobil uygulaması ve uygulamanın kullandığı depo API hizmetleri için geçerlidir. Uygulama, yalnızca Alfateks tarafından yetkilendirilmiş kurumsal kullanıcıların depo operasyonlarını yürütmesi amacıyla sunulur.</p>
              <p>Gizlilik talepleri için <a href="mailto:info@alfateks.com.tr">info@alfateks.com.tr</a> adresine yazabilir veya <a href="tel:+902242802727">+90 224 280 27 27</a> numarasını arayabilirsiniz.</p>
            </section>
            <section id="data">
              <h2>2. İşlediğimiz veriler</h2>
              <ul>
                <li><strong>Hesap ve yetki bilgileri:</strong> kullanıcı adı, ad-soyad, e-posta adresi, aktiflik durumu, rol ve etkin izinler.</li>
                <li><strong>Depo operasyon verileri:</strong> ürün, ürün kodu, marka, renk, parti/lot numarası, stok miktarı, minimum stok, adet (count), notlar ve stok işlem geçmişi.</li>
                <li><strong>Kullanıcı tarafından sağlanan içerik:</strong> yalnızca kullanıcı ürün kaydı için özellikle seçtiğinde veya çektiğinde yüklenen ürün görseli.</li>
                <li><strong>Güvenlik ve teknik kayıtlar:</strong> oturum bilgileri, işlem zamanı, istek kimliği, IP adresi, user-agent, başarılı/başarısız girişler ve yetkili kullanıcı işlemlerine ilişkin denetim kayıtları.</li>
              </ul>
            </section>
            <section id="device">
              <h2>3. Cihaz izinleri ve OCR</h2>
              <ul>
                <li><strong>Kamera:</strong> QR/barkod tarama, metin tanıma (OCR) ve kullanıcı isterse ürün görseli çekmek için kullanılır.</li>
                <li><strong>Yerel OCR:</strong> mobil uygulamada yalnızca OCR amacıyla çekilen görüntü cihaz üzerinde Google ML Kit ile işlenir ve API'ye yüklenmez.</li>
                <li><strong>API OCR:</strong> yetkili başka bir istemci API OCR özelliğini açıkça çağırırsa görsel yalnızca alan önerileri üretmek için geçici olarak işlenir; ürün görseli olarak kaydedilmez.</li>
                <li><strong>Bluetooth:</strong> desteklenen termal etiket yazıcılarını keşfetmek ve yazdırma iletişimi kurmak için kullanılır.</li>
                <li><strong>Hareket sensörü:</strong> isteğe bağlı sallama kısayolunu çalıştırmak için kullanılır; hareket geçmişi saklanmaz.</li>
                <li><strong>Yerel önbellek:</strong> bağlantı hatalarında ürün listesini göstermek için sınırlı ürün verisi cihazda önbelleğe alınabilir. Oturum sınırlarında bu önbellek temizlenir; parola cihaz önbelleğinde saklanmaz.</li>
              </ul>
            </section>
            <section id="purposes">
              <h2>4. İşleme amaçları ve hukuki sebepler</h2>
              <p>Verileri kimlik doğrulama ve yetkilendirme, ürün ve stok operasyonlarını yürütme, rapor oluşturma, etiketleme, güvenliği sağlama, kötüye kullanımı önleme, hata giderme ve yasal yükümlülüklere uyma amaçlarıyla işleriz. İşleme; sözleşmenin kurulması veya ifası, hukuki yükümlülükler, bir hakkın tesisi/kullanılması/korunması ve temel haklara zarar vermeyen meşru menfaatler gibi uygulanabilir hukuki sebeplere dayanır.</p>
            </section>
            <section id="sharing">
              <h2>5. Paylaşım ve yurt dışı aktarım</h2>
              <p>Verileri satmayız ve reklam hedefleme amacıyla kullanmayız. Veriler, yalnızca görevleri gereği erişmesi gereken yetkili Alfateks personeli ile barındırma, altyapı, güvenlik veya teknik destek sağlayan hizmet sağlayıcılarla gerekli olduğu ölçüde paylaşılabilir. Bir aktarım Türkiye dışına yapılacaksa, yürürlükteki mevzuatta öngörülen aktarım şartları ve uygun güvenceler uygulanır.</p>
            </section>
            <section id="retention">
              <h2>6. Saklama ve silme</h2>
              <p>Verileri, yukarıdaki amaçlar için gerekli süre, Alfateks'in kurumsal saklama planı ve uygulanabilir yasal süreler boyunca saklarız. Hesap devre dışı bırakılması bütün operasyon ve denetim kayıtlarının otomatik olarak silindiği anlamına gelmez; stok bütünlüğü, güvenlik ve yasal ispat için bazı kayıtların korunması gerekebilir. Saklama süresi sona erdiğinde veriler silinir, anonimleştirilir veya güvenli biçimde yok edilir.</p>
            </section>
            <section id="security">
              <h2>7. Güvenlik</h2>
              <p>Aktarım sırasında HTTPS, rol ve izin tabanlı erişim, güvenli oturum yönetimi, işlem denetimi ve erişim sınırlandırmaları gibi teknik ve idari tedbirler uygularız. Hiçbir yöntem mutlak güvenlik sağlayamaz; şüpheli bir durum tespit ederseniz bizimle iletişime geçin.</p>
            </section>
            <section id="rights">
              <h2>8. Haklarınız</h2>
              <p>6698 sayılı Kişisel Verilerin Korunması Kanunu'nun 11. maddesi kapsamındaki haklarınız dahil olmak üzere; verilerinizin işlenip işlenmediğini öğrenme, bilgi talep etme, işleme amacını ve uygun kullanımını öğrenme, aktarılan tarafları bilme, düzeltme, şartları varsa silme/yok etme, yapılan işlemlerin alıcılara bildirilmesini isteme, otomatik analiz sonucuna itiraz etme ve kanuna aykırı işleme nedeniyle zararın giderilmesini talep etme haklarına sahip olabilirsiniz.</p>
              <p>Talebinizi kimliğinizi doğrulamamıza yetecek bilgilerle <a href="mailto:info@alfateks.com.tr">info@alfateks.com.tr</a> adresine iletebilirsiniz. Talebi değerlendirirken ek doğrulama isteyebiliriz.</p>
            </section>
            <section id="children">
              <h2>9. Çocukların gizliliği</h2>
              <p>Uygulama kurumsal depo personeline yöneliktir ve çocuklara yönelik değildir. Bilerek çocuklardan kişisel veri toplamıyoruz.</p>
            </section>
            <section id="changes">
              <h2>10. Değişiklikler</h2>
              <p>Bu politikayı ürün, mevzuat veya veri işleme uygulamalarındaki değişiklikleri yansıtmak için güncelleyebiliriz. Önemli değişikliklerde yürürlük tarihini yeniler ve uygun kanallardan bildirim yaparız.</p>
            </section>
            """
        ).strip(),
    ),
    "en": PolicyCopy(
        language="en",
        locale_name="English",
        title="Privacy Policy",
        subtitle="Alfateks Warehouse mobile application and related warehouse API services",
        effective_label="Effective date",
        effective_date=_EFFECTIVE_DATE,
        contents_label="Contents",
        contact_label="Send a privacy request",
        body=dedent(
            """
            <section id="controller">
              <h2>1. Data controller and scope</h2>
              <p>This policy applies to the Alfateks Warehouse mobile application and the warehouse API services it uses, provided by Alfateks Tekstil Ürünleri Madencilik Sanayi ve Ticaret A.Ş. ("Alfateks", "we", "us"). The application is provided solely for warehouse operations by organizational users authorized by Alfateks.</p>
              <p>For privacy requests, email <a href="mailto:info@alfateks.com.tr">info@alfateks.com.tr</a> or call <a href="tel:+902242802727">+90 224 280 27 27</a>.</p>
            </section>
            <section id="data">
              <h2>2. Data we process</h2>
              <ul>
                <li><strong>Account and authorization data:</strong> username, full name, email address, account status, role, and effective permissions.</li>
                <li><strong>Warehouse operations data:</strong> product information, product code, brand, color, batch/lot number, stock quantity, minimum stock, count, notes, and stock transaction history.</li>
                <li><strong>User-provided content:</strong> a product image uploaded only when the user intentionally selects or captures it for the product record.</li>
                <li><strong>Security and technical records:</strong> session details, timestamps, request identifiers, IP address, user-agent, successful or failed sign-ins, and audit records of authorized user actions.</li>
              </ul>
            </section>
            <section id="device">
              <h2>3. Device permissions and OCR</h2>
              <ul>
                <li><strong>Camera:</strong> used for QR/barcode scanning, optical character recognition (OCR), and taking a product image when requested by the user.</li>
                <li><strong>On-device OCR:</strong> an image captured only for OCR in the mobile application is processed on the device with Google ML Kit and is not uploaded to the API.</li>
                <li><strong>API OCR:</strong> if another authorized client explicitly invokes the API OCR feature, the image is processed transiently to produce editable field suggestions and is not stored as a product image.</li>
                <li><strong>Bluetooth:</strong> used to discover and communicate with supported thermal label printers.</li>
                <li><strong>Motion sensor:</strong> used for an optional shake shortcut; motion history is not retained.</li>
                <li><strong>Local cache:</strong> limited product data may be cached on the device to display the product list during connection failures. The cache is cleared at session boundaries; passwords are not stored in the device cache.</li>
              </ul>
            </section>
            <section id="purposes">
              <h2>4. Purposes and legal bases</h2>
              <p>We process data to authenticate and authorize users, operate product and stock workflows, create reports, support labeling, secure the service, prevent misuse, troubleshoot errors, and comply with legal obligations. Depending on the context, processing relies on performance of a contract, compliance with legal obligations, establishment or protection of legal rights, and legitimate interests that do not override fundamental rights.</p>
            </section>
            <section id="sharing">
              <h2>5. Sharing and international transfers</h2>
              <p>We do not sell data or use it for targeted advertising. Data may be shared, only as necessary, with authorized Alfateks personnel and service providers that supply hosting, infrastructure, security, or technical support. If data is transferred outside Türkiye, the transfer requirements and appropriate safeguards required by applicable law will be applied.</p>
            </section>
            <section id="retention">
              <h2>6. Retention and deletion</h2>
              <p>We retain data for as long as necessary for the purposes above, under Alfateks's organizational retention schedule, and for applicable legal periods. Deactivating an account does not automatically remove all operational or audit records; some records may need to be preserved for stock integrity, security, and legal evidence. At the end of the applicable period, data is deleted, anonymized, or securely destroyed.</p>
            </section>
            <section id="security">
              <h2>7. Security</h2>
              <p>We use technical and organizational safeguards such as HTTPS in transit, role- and permission-based access, secure session management, audit trails, and access restrictions. No method is absolutely secure; contact us if you identify a suspected security issue.</p>
            </section>
            <section id="rights">
              <h2>8. Your rights</h2>
              <p>Subject to applicable law, including Article 11 of Türkiye's Personal Data Protection Law No. 6698, you may have rights to learn whether your data is processed, request information, learn the purpose and proper use of processing, identify recipients, request correction, request deletion or destruction where conditions apply, request notification of those actions to recipients, object to certain automated outcomes, and claim compensation for unlawful processing.</p>
              <p>Submit a request with enough information for us to verify your identity to <a href="mailto:info@alfateks.com.tr">info@alfateks.com.tr</a>. We may request additional verification before responding.</p>
            </section>
            <section id="children">
              <h2>9. Children's privacy</h2>
              <p>The application is intended for organizational warehouse personnel and is not directed to children. We do not knowingly collect personal data from children.</p>
            </section>
            <section id="changes">
              <h2>10. Changes</h2>
              <p>We may update this policy to reflect changes in the product, law, or our data practices. For material changes, we will update the effective date and provide notice through an appropriate channel.</p>
            </section>
            """
        ).strip(),
    ),
}

_NAV_ITEMS = {
    "tr": (
        ("controller", "Veri sorumlusu"),
        ("data", "İşlenen veriler"),
        ("device", "Cihaz ve OCR"),
        ("purposes", "Amaçlar"),
        ("sharing", "Paylaşım"),
        ("retention", "Saklama"),
        ("security", "Güvenlik"),
        ("rights", "Haklarınız"),
        ("children", "Çocuklar"),
        ("changes", "Değişiklikler"),
    ),
    "en": (
        ("controller", "Controller"),
        ("data", "Data processed"),
        ("device", "Device and OCR"),
        ("purposes", "Purposes"),
        ("sharing", "Sharing"),
        ("retention", "Retention"),
        ("security", "Security"),
        ("rights", "Your rights"),
        ("children", "Children"),
        ("changes", "Changes"),
    ),
}


def _security_headers(language: str) -> dict[str, str]:
    return {
        "Cache-Control": "public, max-age=3600",
        "Content-Language": language,
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _render_policy(policy: PolicyCopy) -> str:
    other_language = "en" if policy.language == "tr" else "tr"
    other_label = _POLICIES[other_language].locale_name
    nav = "".join(
        f'<li><a href="#{anchor}">{label}</a></li>' for anchor, label in _NAV_ITEMS[policy.language]
    )
    canonical_url = f"{_CANONICAL_BASE}/{policy.language}"
    alternate_url = f"{_CANONICAL_BASE}/{other_language}"
    return dedent(
        f"""<!doctype html>
        <html lang="{policy.language}">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <meta name="color-scheme" content="light dark">
          <meta name="robots" content="index, follow">
          <meta name="description" content="{policy.subtitle}">
          <link rel="canonical" href="{canonical_url}">
          <link rel="alternate" hreflang="tr" href="{_CANONICAL_BASE}/tr">
          <link rel="alternate" hreflang="en" href="{_CANONICAL_BASE}/en">
          <link rel="alternate" hreflang="x-default" href="{_CANONICAL_BASE}/tr">
          <title>{policy.title} | Alfateks</title>
          <style>
            :root {{ color-scheme: light dark; --bg:#f3f7fa; --surface:#fff; --text:#102431; --muted:#526775; --line:#d9e4ea; --brand:#285f7a; --soft:#e8f1f5; }}
            * {{ box-sizing:border-box; }}
            html {{ scroll-behavior:smooth; }}
            body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
            a {{ color:var(--brand); text-underline-offset:3px; }}
            a:focus-visible {{ outline:3px solid #f2a900; outline-offset:3px; border-radius:3px; }}
            .shell {{ width:min(1120px,calc(100% - 32px)); margin:0 auto; }}
            header {{ padding:48px 0 32px; background:linear-gradient(135deg,#153e53,#327999); color:#fff; }}
            .eyebrow {{ margin:0 0 12px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; opacity:.82; }}
            h1 {{ max-width:780px; margin:0; font-size:clamp(2rem,6vw,3.8rem); line-height:1.08; }}
            .subtitle {{ max-width:760px; margin:18px 0 0; font-size:1.08rem; opacity:.9; }}
            .meta {{ display:flex; flex-wrap:wrap; gap:12px 24px; align-items:center; margin-top:24px; }}
            .language {{ display:inline-flex; padding:8px 14px; border:1px solid rgba(255,255,255,.4); border-radius:999px; color:#fff; font-weight:700; text-decoration:none; }}
            .layout {{ display:grid; grid-template-columns:250px minmax(0,1fr); gap:32px; padding:32px 0 64px; align-items:start; }}
            nav {{ position:sticky; top:20px; padding:20px; border:1px solid var(--line); border-radius:16px; background:var(--surface); }}
            nav h2 {{ margin:0 0 12px; font-size:1rem; }}
            nav ol {{ margin:0; padding-left:22px; }}
            nav li + li {{ margin-top:7px; }}
            main {{ min-width:0; }}
            section {{ padding:28px; border:1px solid var(--line); border-radius:16px; background:var(--surface); box-shadow:0 8px 28px rgba(16,36,49,.05); }}
            section + section {{ margin-top:18px; }}
            section h2 {{ margin:0 0 12px; font-size:1.35rem; line-height:1.3; }}
            section p:last-child, section ul:last-child {{ margin-bottom:0; }}
            li + li {{ margin-top:8px; }}
            .contact {{ display:inline-flex; margin-top:24px; padding:12px 18px; border-radius:10px; background:var(--brand); color:#fff; font-weight:700; text-decoration:none; }}
            footer {{ padding:24px 0 44px; color:var(--muted); text-align:center; }}
            @media (max-width:760px) {{
              header {{ padding-top:34px; }} .layout {{ grid-template-columns:1fr; }} nav {{ position:static; }} section {{ padding:22px; }}
            }}
            @media (prefers-reduced-motion:reduce) {{ html {{ scroll-behavior:auto; }} }}
            @media (prefers-color-scheme:dark) {{
              :root {{ --bg:#0d1820; --surface:#14242e; --text:#edf5f8; --muted:#b1c2cc; --line:#2e4654; --brand:#7bc1df; --soft:#17303d; }}
              header {{ background:linear-gradient(135deg,#102e3d,#245c75); }} section {{ box-shadow:none; }} .contact {{ background:#7bc1df; color:#0b2734; }}
            }}
          </style>
        </head>
        <body>
          <header>
            <div class="shell">
              <p class="eyebrow">Alfateks Warehouse</p>
              <h1>{policy.title}</h1>
              <p class="subtitle">{policy.subtitle}</p>
              <div class="meta">
                <span>{policy.effective_label}: <strong>{policy.effective_date}</strong></span>
                <a class="language" href="{alternate_url}" lang="{other_language}" hreflang="{other_language}">{other_label}</a>
              </div>
            </div>
          </header>
          <div class="shell layout">
            <nav aria-label="{policy.contents_label}">
              <h2>{policy.contents_label}</h2>
              <ol>{nav}</ol>
            </nav>
            <main>
              {policy.body}
              <a class="contact" href="mailto:info@alfateks.com.tr">{policy.contact_label}</a>
            </main>
          </div>
          <footer><div class="shell">© 2026 Alfateks Tekstil Ürünleri Madencilik Sanayi ve Ticaret A.Ş.</div></footer>
        </body>
        </html>"""
    )


@router.get("", include_in_schema=False)
async def privacy_policy_default() -> RedirectResponse:
    return RedirectResponse(url="/api/privacy-policy/tr", status_code=307)


@router.get("/tr", response_class=HTMLResponse, summary="Turkish privacy policy")
async def privacy_policy_tr() -> HTMLResponse:
    policy = _POLICIES["tr"]
    return HTMLResponse(_render_policy(policy), headers=_security_headers(policy.language))


@router.get("/en", response_class=HTMLResponse, summary="English privacy policy")
async def privacy_policy_en() -> HTMLResponse:
    policy = _POLICIES["en"]
    return HTMLResponse(_render_policy(policy), headers=_security_headers(policy.language))

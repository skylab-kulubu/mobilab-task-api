# MOBILAB Task API

Etkinlik Keşif Uygulaması görevi için etkinlik API'si.

**Base URL:** `https://<API_ADRESI>`
**Etkileşimli dokümantasyon:** `https://<API_ADRESI>/docs`

> Bu API gerçek dünyayı taklit eder: bazı istekler yavaş gelir, bazıları da hata döner.
> Bu bir hata değil, görevin parçası. Uygulaman bu durumlarla düzgün başa çıkabilmeli.

---

## Uç noktalar

### `GET /events`

Etkinlik listesi, başlangıç tarihine göre sıralı. Liste yanıtında `description` alanı **yoktur**; detay için `/events/{id}` kullan.

| Parametre  | Tip    | Açıklama                                   | Varsayılan |
|------------|--------|--------------------------------------------|------------|
| `q`        | string | Başlık ve etiketlerde arama                | -          |
| `category` | string | Kategori filtresi (ör. `Workshop`)         | -          |
| `online`   | bool   | `true`: sadece online, `false`: yüz yüze   | -          |
| `page`     | int    | Sayfa numarası (1'den başlar)              | `1`        |
| `limit`    | int    | Sayfa başına kayıt (1-50)                  | `10`       |

Örnek: `GET /events?q=flutter&page=1&limit=10`

```json
{
  "items": [
    {
      "id": "evt-001",
      "title": "Flutter ile İlk Uygulamanı Yayınla",
      "category": "Workshop",
      "startDate": "2026-10-21T18:00:00+03:00",
      "endDate": "2026-10-21T20:00:00+03:00",
      "location": "Davutpaşa Kampüsü, Elektrik-Elektronik Fakültesi B-112",
      "organizer": "MOBILAB",
      "imageUrl": "https://picsum.photos/seed/evt001/800/450",
      "capacity": 60,
      "registeredCount": 42,
      "isOnline": false,
      "tags": ["flutter", "mobil", "yayınlama"]
    }
  ],
  "page": 1,
  "limit": 10,
  "total": 3,
  "hasMore": false
}
```

### `GET /events/{id}`

Tek bir etkinliğin tüm detayları (`description` dahil). Etkinlik yoksa `404` döner.

### `GET /categories`

Filtrelemede kullanabileceğin kategori listesi.

```json
{ "items": ["Hackathon", "Panel", "Seminer", "Sosyal", "Workshop", "Yarışma"] }
```

## Hata formatı

Tüm hatalar aynı yapıdadır:

```json
{ "error": "not_found", "message": "'evt-999' id'li etkinlik bulunamadı." }
```

| Kod   | Anlamı                                  |
|-------|-----------------------------------------|
| `404` | Etkinlik bulunamadı                     |
| `422` | Geçersiz parametre (ör. `limit=100`)    |
| `500` | Sunucu hatası, tekrar denemek işe yarar |

## Alanlar hakkında

- `imageUrl` boş (`null`) olabilir ya da çalışmayan bir linke işaret edebilir.
- `registeredCount == capacity` ise etkinlik doludur.
- Tarihler ISO 8601 formatında, saat dilimi bilgisiyle gelir.

## Yedek

API'ye ulaşamazsan aynı verinin statik hali: `<RAW_JSON_LINKI>`
(Statik dosyada sayfalama, arama ve filtre yoktur; bunları uygulama tarafında yapman gerekir.)

---

<details>
<summary><b>Yöneticiler için: kurulum ve yayınlama</b></summary>

### Yerelde

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Kaos kapalı denemek için:
CHAOS_ENABLED=false uvicorn main:app --reload
```

### Kendi sunucunda (Docker)

```bash
docker compose up -d --build
```

8000 portunda açılır. Önüne Nginx/Caddy ile HTTPS koy; Android ve iOS düz HTTP isteklerini varsayılan olarak engeller.

### Vercel

```bash
npm i -g vercel
vercel        # ilk kurulum
vercel --prod # yayınla
```

Ortam değişkenlerini Vercel panelinden ayarlayabilirsin.

### Ortam değişkenleri

| Değişken           | Açıklama                          | Varsayılan |
|--------------------|-----------------------------------|------------|
| `CHAOS_ENABLED`    | Gecikme + rastgele hata           | `true`     |
| `CHAOS_ERROR_RATE` | Hata dönecek isteklerin oranı     | `0.1`      |
| `CHAOS_MIN_DELAY`  | Minimum gecikme (saniye)          | `0.3`      |
| `CHAOS_MAX_DELAY`  | Maksimum gecikme (saniye)         | `1.5`      |

`/`, `/health` ve `/docs` kaostan etkilenmez.

</details>

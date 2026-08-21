# GolAnaliz Veri Toplama Hattı (GitHub Actions)

Bu klasör, Sportmonks'tan verileri **senin adına, saatte bir, ücretsiz** çeken ve
`docs/matches.json` dosyasına yazan bir GitHub Actions kurulumu içeriyor. GitHub
Pages bu dosyayı otomatik olarak herkese açık, sabit bir adresten yayınlar -
telefon uygulaması artık Sportmonks'a değil bu adrese bağlanacak.

## Kurulum Adımları

### 1. GitHub'da yeni bir repo oluştur
github.com'da "New repository" ile yeni bir repo aç (örn. `golanaliz-data`).
**Public** (herkese açık) olması gerekiyor - GitHub Pages'in ücretsiz sürümü
sadece public repolarda çalışıyor. (JSON verisi zaten "kim tuttu kim tutmadı"
gibi hassas bir şey içermiyor, herkese açık olması sorun değil.)

### 2. Bu klasördeki dosyaları o repoya yükle
Bu klasördeki `fetch_predictions.py`, `.github/workflows/update-predictions.yml`
ve `README.md` dosyalarını, oluşturduğun reponun **kök dizinine** (aynı klasör
yapısıyla) yükle. GitHub'ın web arayüzünden "Add file → Upload files" ile
sürükle-bırak yapabilirsin, ya da Git kullanıyorsan `git push` ile.

### 3. API anahtarını GitHub'a "Secret" olarak ekle
Reponda: **Settings → Secrets and variables → Actions → New repository secret**
- Name: `SPORTMONKS_API_KEY`
- Value: senin gerçek Sportmonks API anahtarın

Bu, anahtarın hiçbir zaman kod içinde açık yazılmayacağı, sadece GitHub'ın
güvenli deposunda duracağı anlamına gelir.

### 4. GitHub Pages'i aç
Reponda: **Settings → Pages** → "Build and deployment" kısmında:
- Source: "Deploy from a branch"
- Branch: `main`, klasör: `/docs`

Kaydettikten sonra GitHub sana bir adres verecek, şuna benzer:
`https://kullaniciadin.github.io/golanaliz-data/`

### 5. İlk çalıştırmayı elle tetikle (test için)
Reponda: **Actions** sekmesi → "Tahminleri Güncelle" workflow'u → sağ üstte
"Run workflow" butonu. Birkaç dakika içinde `docs/matches.json` dosyası
oluşacak, GitHub Pages adresinden görebileceksin:
`https://kullaniciadin.github.io/golanaliz-data/matches.json`

Bundan sonra, hiçbir şey yapmana gerek kalmadan **her saat başı otomatik**
çalışacak.

## Sonraki adım: Android uygulamasını bu adrese bağlamak

Bu JSON hazır olduğunda, Android tarafında `SportmonksApi`'ye doğrudan bağlanan
kodu, bu sabit JSON adresini çeken çok daha basit bir koda çevirmemiz gerekecek
- bu ayrı bir adım, hazır olunca haber ver.

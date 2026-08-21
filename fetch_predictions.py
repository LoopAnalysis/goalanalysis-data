"""
GolAnaliz HAM VERİ toplama script'i.

Bu script, HİÇBİR hesaplama (Poisson, harmanlama vs.) YAPMAZ - o mantık hâlâ
Kotlin tarafında (GoalPredictionRepository.kt) yaşıyor, hiç değişmedi.

Bu script'in tek işi:
  1. Önümüzdeki 3 gün için tüm fikstürleri (maç listesini) Sportmonks'un
     KENDİ ORİJİNAL JSON formatında çeker
  2. O fikstürlerdeki HER TAKIM için, son 120 günlük geçmişini (yine Sportmonks'un
     orijinal formatında) BİR KERE çeker - aynı takım birden fazla maçta geçse bile
     tekrar tekrar çekmez (dedup)
  3. İkisini tek bir JSON dosyasına (docs/raw_data.json) yazar

Format, Sportmonks'un kendi API yanıtıyla BİREBİR aynı olduğu için, Kotlin
tarafındaki mevcut Fixture/Odds Gson modelleri HİÇ DEĞİŞMEDEN bu dosyayı da
okuyabiliyor - tek fark, verinin nereden indirildiği (Sportmonks yerine bu
sabit JSON adresinden).

GitHub Actions tarafından SAATTE BİR otomatik çalıştırılması için tasarlandı.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from threading import Lock

import requests

API_KEY = os.environ.get("SPORTMONKS_API_KEY")
if not API_KEY:
    print("HATA: SPORTMONKS_API_KEY ortam değişkeni bulunamadı.", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.sportmonks.com/v3/football"


def api_get(path: str, params: dict) -> dict:
    """429 (hız sınırı) VE 5xx (geçici sunucu hatası, örn. 504 Gateway Timeout)
    durumunda otomatik olarak bekleyip tekrar dener."""
    params = {**params, "api_token": API_KEY}
    last_error = None
    for attempt in range(6):
        try:
            response = requests.get(f"{BASE_URL}/{path}", params=params, timeout=60)
        except requests.exceptions.RequestException as e:
            last_error = e
            wait = min(2 ** attempt, 30)
            print(f"  Ağ hatası ({e}), {wait}sn bekleniyor (deneme {attempt + 1}/6)...")
            time.sleep(wait)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            wait = min(2 ** attempt, 30)
            print(f"  {response.status_code} alındı, {wait}sn bekleniyor (deneme {attempt + 1}/6)...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"6 denemeden sonra da başarısız oldu. Son hata: {last_error}")


def fetch_all_pages(path: str, params: dict, max_pages: int = 3) -> list:
    """Sportmonks'un KENDİ ORİJİNAL fixture nesnelerini (hiç dönüştürmeden) döner.
    [max_pages]: takım geçmişi çekerken zaten sadece en yeni ~10 maçı kullanıyoruz,
    o yüzden çok kalabalık takımlar için sonsuza kadar sayfalamaya gerek yok - bu,
    en aktif takımların (birden fazla kupada oynayanlar) gereksiz yere onlarca istek
    atmasını önlüyor."""
    all_data = []
    page = 1
    while page <= max_pages:
        result = api_get(path, {**params, "page": page})
        all_data.extend(result.get("data", []))
        pagination = result.get("pagination", {})
        if not pagination.get("has_more"):
            break
        page += 1
    return all_data


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    end_date = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")

    print(f"Fikstürler çekiliyor: {today} -> {end_date}")
    upcoming_fixtures = fetch_all_pages(
        f"fixtures/between/{today}/{end_date}",
        {"include": "participants;league;odds"},
    )
    upcoming_fixtures = list({f["id"]: f for f in upcoming_fixtures}.values())
    print(f"{len(upcoming_fixtures)} fikstür bulundu")

    team_ids = set()
    for fixture in upcoming_fixtures:
        for participant in fixture.get("participants") or []:
            if participant.get("id"):
                team_ids.add(participant["id"])
    print(f"{len(team_ids)} benzersiz takım bulundu, geçmişleri çekiliyor...")

    history_end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    history_start = (datetime.now(timezone.utc) - timedelta(days=121)).strftime("%Y-%m-%d")

    def fetch_team_history(team_id: int) -> tuple[int, list]:
        fixtures = fetch_all_pages(
            f"fixtures/between/{history_start}/{history_end}/{team_id}",
            {"include": "participants;scores;statistics"},
        )
        return team_id, fixtures

    # Takımları SIRAYLA değil, AYNI ANDA (paralel) çekiyoruz - 10 takım birden. Sportmonks'un
    # saatlik kotası (3000 istek) buna rahatça izin veriyor, sadece anlık yoğunluğu (429/504)
    # kontrol altında tutmak için işçi sayısını makul (10) tutuyoruz.
    team_histories = {}
    completed_lock = Lock()
    completed_count = 0
    team_id_list = sorted(team_ids)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_team_history, tid): tid for tid in team_id_list}
        for future in as_completed(futures):
            team_id, fixtures = future.result()
            team_histories[str(team_id)] = fixtures
            with completed_lock:
                completed_count += 1
                if completed_count % 20 == 0 or completed_count == len(team_id_list):
                    print(f"  [{completed_count}/{len(team_id_list)}] takım geçmişleri çekildi...")

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "upcomingFixtures": upcoming_fixtures,
        "teamHistories": team_histories,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/raw_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    size_mb = os.path.getsize("docs/raw_data.json") / (1024 * 1024)
    print(f"\nBitti: {len(upcoming_fixtures)} fikstür + {len(team_histories)} takım geçmişi")
    print(f"docs/raw_data.json yazıldı ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

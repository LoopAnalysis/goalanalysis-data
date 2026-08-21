"""
GolAnaliz HAM VERİ toplama script'i.

Bu script, HİÇBİR hesaplama (Poisson, harmanlama vs.) YAPMAZ - o mantık hâlâ
Kotlin tarafında (GoalPredictionRepository.kt) yaşıyor, hiç değişmedi.

Bu script'in tek işi:
  1. Önümüzdeki 3 gün için tüm fikstürleri (maç listesini) Sportmonks'un
     KENDİ ORİJİNAL JSON formatında çeker
  2. O fikstürlerdeki HER TAKIM için, son 180 günlük geçmişini (yine Sportmonks'un
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
from datetime import datetime, timedelta, timezone

import requests

API_KEY = os.environ.get("SPORTMONKS_API_KEY")
if not API_KEY:
    print("HATA: SPORTMONKS_API_KEY ortam değişkeni bulunamadı.", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.sportmonks.com/v3/football"


def api_get(path: str, params: dict) -> dict:
    """429 (hız sınırı) durumunda otomatik olarak bekleyip tekrar dener."""
    params = {**params, "api_token": API_KEY}
    for attempt in range(4):
        response = requests.get(f"{BASE_URL}/{path}", params=params, timeout=30)
        if response.status_code == 429:
            wait = 2 ** attempt
            print(f"  429 alındı, {wait}sn bekleniyor (deneme {attempt + 1}/4)...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("429 hatası - 4 denemeden sonra da başarısız oldu")


def fetch_all_pages(path: str, params: dict) -> list:
    """Sportmonks'un KENDİ ORİJİNAL fixture nesnelerini (hiç dönüştürmeden) döner."""
    all_data = []
    page = 1
    while True:
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
    history_start = (datetime.now(timezone.utc) - timedelta(days=181)).strftime("%Y-%m-%d")

    team_histories = {}
    for index, team_id in enumerate(sorted(team_ids)):
        print(f"  [{index + 1}/{len(team_ids)}] takım {team_id} geçmişi çekiliyor...")
        fixtures = fetch_all_pages(
            f"fixtures/between/{history_start}/{history_end}/{team_id}",
            {"include": "participants;scores;statistics"},
        )
        team_histories[str(team_id)] = fixtures
        time.sleep(0.06)

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

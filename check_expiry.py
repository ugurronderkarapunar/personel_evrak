"""Her sabah GitHub Actions tarafından çalıştırılır."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db
import notify

BASE = """SELECT b.id, b.belge_adi, b.bitis, p.ad, p.soyad, p.unvan
FROM belge b JOIN personel p ON p.id = b.personel_id
WHERE {cond} ORDER BY b.bitis"""


def line(r, today):
    kalan = (r["bitis"] - today).days
    if kalan < 0:
        durum = f"{-kalan} gün önce doldu"
    elif kalan == 0:
        durum = "BUGÜN doluyor"
    else:
        durum = f"{kalan} gün kaldı"
    return (f"• {r['ad']} {r['soyad']} ({r['unvan']}) – {r['belge_adi']} – "
            f"{r['bitis']:%d.%m.%Y} ({durum})")


def process(rows, today, subject, flag_sql):
    if not rows:
        return
    if notify.send_all(subject, [line(r, today) for r in rows]):
        ids = [r["id"] for r in rows]
        db.execute(f"UPDATE belge SET {flag_sql} WHERE id = ANY(%s)", (ids,))
        print(f"{subject}: {len(rows)} kayıt bildirildi.")
    else:
        print(f"{subject}: gönderilemedi, yarın tekrar denenecek.")


def main():
    today = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    limit = today + timedelta(days=15)

    expired = db.query(
        BASE.format(cond="b.bitis < %s AND NOT b.bildirim_bitti_gonderildi"), (today,))
    process(expired, today, "⚠️ SÜRESİ DOLAN BELGELER",
            "bildirim_bitti_gonderildi = TRUE, bildirim_15gun_gonderildi = TRUE")

    soon = db.query(
        BASE.format(cond="b.bitis BETWEEN %s AND %s AND NOT b.bildirim_15gun_gonderildi"),
        (today, limit))
    process(soon, today, "⏰ SÜRESİ 15 GÜN İÇİNDE DOLACAK BELGELER",
            "bildirim_15gun_gonderildi = TRUE")


if __name__ == "__main__":
    main()

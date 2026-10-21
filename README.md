# Belge Takip

Streamlit (arayüz) + Neon Postgres (veritabanı) + GitHub Actions (günlük bildirim).

## Streamlit Cloud → App settings → Secrets
```
DATABASE_URL = "postgresql://...neon.tech/neondb?sslmode=require"
APP_PASSWORD = "güçlü-bir-şifre"
```

## GitHub → Settings → Secrets and variables → Actions
DATABASE_URL, MAIL_USER, MAIL_APP_PASSWORD, MAIL_TO, WA_PHONE, WA_APIKEY
(WA_PHONE örn: +905xxxxxxxxx — CallMeBot'tan alınan apikey ile)

from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import numpy as np
import requests
import csv
import os
import smtplib
import mimetypes
from email.message import EmailMessage
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
       
# =====================================================================
# KONFIGURASI PATH (KOMPATIBEL WINDOWS & GITHUB ACTIONS)
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder output
output_dir = os.path.join(BASE_DIR, "output")
os.makedirs(output_dir, exist_ok=True)

# Folder ikon hasil download dari API BMKG
icon_dir = os.path.join(output_dir, "ikon_cuaca")
os.makedirs(icon_dir, exist_ok=True)

# Folder ikon template yang ada di repository
ikon_dir = os.path.join(BASE_DIR, "ikon_cuaca1")

# File template video
video_path = os.path.join(BASE_DIR, "prakiraan.mp4")

# File CSV output
csv_path = os.path.join(output_dir, "prakiraan_cuaca.csv")

# File video output
output_video_path = os.path.join(output_dir, "prakiraan_video_output.mp4")

# Ikon arah angin
ikon_arah_path = os.path.join(ikon_dir, "ikon_arah_angin.png")

custom_font = os.path.join(BASE_DIR, "fonts", "Bahnschrift.ttf")

if os.path.exists(custom_font):
    font_path = custom_font
else:
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

font = ImageFont.truetype(font_path, 21)

# =====================================================================
# URL API BMKG
# =====================================================================
url = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=36.71.01.1003"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# =====================================================================
# FUNGSI KONVERSI KM/J KE KNOTS
# =====================================================================
def kmh_to_knots(kmh):
    try:
        return f"{float(kmh) * 0.539957:.1f} kt"
    except:
        return ""

# =====================================================================
# AMBIL DATA BMKG
# =====================================================================
print("📡 Mengambil data BMKG...")
response = requests.get(url, headers=headers, timeout=60)
response.raise_for_status()
data_json = response.json()

# =====================================================================
# SIMPAN CSV
# =====================================================================
print("📝 Membuat file CSV...")
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)

    writer.writerow([
        "Tanggal", "Jam", "Cuaca",
        "Suhu", "Kelembapan",
        "Kecepatan Angin", "Kecepatan Angin (knots)",
        "Arah Angin (°)", "File Ikon"
    ])

    for group in data_json["data"][0]["cuaca"]:
        for item in group:
            dt = item.get("local_datetime", "")
            tanggal = dt[:10] if len(dt) >= 10 else ""
            jam = dt[11:16] if len(dt) >= 16 else ""

            cuaca = item.get("weather_desc", "")
            suhu_raw = item.get("t", "")
            hu_raw = item.get("hu", "")
            ws_raw = item.get("ws", "")
            wd_deg = item.get("wd_deg", "")

            suhu = f"{suhu_raw}°C" if suhu_raw != "" else ""
            kelembapan = f"{hu_raw}%" if hu_raw != "" else ""
            angin = f"{ws_raw} km/j" if ws_raw != "" else ""
            angin_knots = kmh_to_knots(ws_raw)

            ikon_url = item.get("image", "")
            ikon_filename = ""

            if ikon_url:
                ikon_filename = ikon_url.split("/")[-1]
                ikon_path = os.path.join(icon_dir, ikon_filename)

                if not os.path.exists(ikon_path):
                    try:
                        r = requests.get(ikon_url, timeout=60)
                        with open(ikon_path, "wb") as f:
                            f.write(r.content)
                    except Exception as e:
                        print(f"⚠️ Gagal download ikon {ikon_filename}: {e}")

            writer.writerow([
                tanggal,
                jam,
                cuaca,
                suhu,
                kelembapan,
                angin,
                angin_knots,
                wd_deg,
                ikon_filename,
            ])

print(f"✅ CSV berhasil dibuat: {csv_path}")

# =====================================================================
# BACA CSV
# =====================================================================
df = pd.read_csv(csv_path)
print("Kolom CSV:", df.columns.tolist())

# =====================================================================
# LOAD VIDEO TEMPLATE
# =====================================================================
print("🎬 Memuat template video...")
video = VideoFileClip(video_path)
video_w, video_h = video.size
print(f"Ukuran video: {video_w}x{video_h}")

# =====================================================================
# CANVAS TRANSPARAN
# =====================================================================
overlay_img = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay_img)

# =====================================================================
# FONT
# =====================================================================
font_size = 21
font = ImageFont.truetype(font_path, font_size)

# =====================================================================
# FUNGSI AMBIL NILAI
# =====================================================================
def ambil_nilai(df, baris, kolom):
    try:
        nilai = df.iloc[baris][kolom]
        if pd.isna(nilai):
            return ""
        return str(nilai).strip()
    except:
        return ""

# =====================================================================
# FUNGSI IKON ARAH ANGIN
# =====================================================================
def paste_rotated_icon(base_img, icon_path, center_position, angle):
    if not os.path.exists(icon_path):
        return

    size = 31
    ikon_img = (
        Image.open(icon_path)
        .convert("RGBA")
        .resize((size, size), Image.LANCZOS)
    )

    ikon_img_rotated = ikon_img.rotate(-angle, expand=True)

    icon_w, icon_h = ikon_img_rotated.size
    center_x, center_y = center_position

    paste_x = int(center_x - icon_w // 2)
    paste_y = int(center_y - icon_h // 2)

    base_img.paste(
        ikon_img_rotated,
        (paste_x, paste_y),
        ikon_img_rotated,
    )

# =====================================================================
# FUNGSI IKON CUACA
# =====================================================================
def paste_ikon_cuaca(base_img, ikon_dir, position, ikon_filename):
    nama_tanpa_ext = os.path.splitext(ikon_filename)[0]
    ikon_path = None

    for ext in [".svg", ".png"]:
        kandidat = os.path.join(ikon_dir, nama_tanpa_ext + ext)
        if os.path.exists(kandidat):
            ikon_path = kandidat
            break

    if ikon_path is None:
        return

    ikon_img = Image.open(ikon_path).convert("RGBA")

    target_width = 55
    scale_ratio = target_width / ikon_img.width
    target_height = int(ikon_img.height * scale_ratio)

    ikon_img = ikon_img.resize(
        (target_width, target_height),
        Image.LANCZOS,
    )

    x, y = position
    base_img.paste(
        ikon_img,
        (int(x), int(y)),
        ikon_img,
    )

# =====================================================================
# DATA POSISI
# =====================================================================
# Gunakan blok data koordinat lengkap dari skrip Anda sebelumnya.
data = []

# =====================================================================
# PLOT DATA
# =====================================================================
for item in data:
    x = item["x"]
    y = item["y"]
    baris, kolom = item["cell"]

    teks = ambil_nilai(df, baris, kolom)

    if "File Ikon" not in kolom:
        draw.text((int(x), int(y)), teks, font=font, fill="white")

    if "Kecepatan Angin" in kolom:
        arah_angin = ambil_nilai(df, baris, "Arah Angin (°)")
        try:
            angle = float(str(arah_angin).replace("°", "").strip())
            paste_rotated_icon(
                overlay_img,
                ikon_arah_path,
                (int(x - 50), int(y + 15)),
                angle,
            )
        except:
            pass

    if "File Ikon" in kolom:
        paste_ikon_cuaca(overlay_img, ikon_dir, (x, y), teks)

# =====================================================================
# KONVERSI OVERLAY
# =====================================================================
overlay_array = np.array(overlay_img)

# =====================================================================
# DURASI OVERLAY
# =====================================================================
START_TIME = 32.5
END_TIME = 51

overlay_clip = (
    ImageClip(overlay_array)
    .with_start(START_TIME)
    .with_end(END_TIME)
    .with_duration(END_TIME - START_TIME)
)

# =====================================================================
# GABUNGKAN VIDEO
# =====================================================================
final_video = CompositeVideoClip([video, overlay_clip])

# =====================================================================
# RENDER VIDEO
# =====================================================================
print("🎞️ Rendering video...")
final_video.write_videofile(
    output_video_path,
    codec="libx264",
    audio_codec="aac",
    fps=video.fps,
    threads=4,
    preset="medium",
)

# =====================================================================
# CLOSE VIDEO
# =====================================================================
video.close()
final_video.close()
overlay_clip.close()

print(f"✅ Video berhasil dibuat: {output_video_path}")

# =====================================================================
# KIRIM EMAIL + UPLOAD VIDEO KE GOOGLE DRIVE (folder per tanggal)
# =====================================================================
import os
import mimetypes
import smtplib
import json
from datetime import datetime
from email.message import EmailMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("☁️ Mengupload video ke Google Drive...")
try:
    # --- Setup credentials ---
    service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    drive_service = build("drive", "v3", credentials=credentials)

    # --- ID folder utama "Prakiraan Cuaca STMKG" di Google Drive ---
    # Buat folder ini manual di Drive, lalu share ke email service account,
    # kemudian copy ID-nya dari URL: drive.google.com/drive/folders/<FOLDER_ID>
    PARENT_FOLDER_ID = os.environ.get("GDRIVE_PARENT_FOLDER_ID", "")

    # --- Buat folder tanggal hari ini (misal: "2026-05-11") ---
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Cek apakah folder tanggal sudah ada
    query = (
        f"name='{today_str}' "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and '{PARENT_FOLDER_ID}' in parents "
        f"and trashed=false"
    )
    existing = drive_service.files().list(
        q=query, fields="files(id, name)"
    ).execute().get("files", [])

    if existing:
        # Folder sudah ada, pakai yang lama
        date_folder_id = existing[0]["id"]
        print(f"📁 Folder '{today_str}' sudah ada, menggunakan folder yang ada.")
    else:
        # Buat folder tanggal baru
        folder_metadata = {
            "name": today_str,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [PARENT_FOLDER_ID] if PARENT_FOLDER_ID else []
        }
        date_folder = drive_service.files().create(
            body=folder_metadata, fields="id"
        ).execute()
        date_folder_id = date_folder["id"]

        # Jadikan folder publik
        drive_service.permissions().create(
            fileId=date_folder_id,
            body={"type": "anyone", "role": "reader"}
        ).execute()
        print(f"📁 Folder '{today_str}' berhasil dibuat.")

    # --- Upload video ke folder tanggal ---
    mime_type, _ = mimetypes.guess_type(output_video_path)
    mime_type = mime_type or "video/mp4"

    file_metadata = {
        "name": os.path.basename(output_video_path),
        "parents": [date_folder_id]
    }
    media = MediaFileUpload(output_video_path, mimetype=mime_type, resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    # Jadikan file publik
    drive_service.permissions().create(
        fileId=uploaded_file["id"],
        body={"type": "anyone", "role": "reader"}
    ).execute()

    video_link = uploaded_file["webViewLink"]
    print(f"✅ Video berhasil diupload ke folder '{today_str}': {video_link}")

except Exception as e:
    video_link = None
    date_folder_id = None
    print(f"⚠️ Gagal upload ke Google Drive: {e}")

# --- Upload CSV ke folder yang sama ---
print("☁️ Mengupload CSV ke Google Drive...")
try:
    csv_metadata = {
        "name": os.path.basename(csv_path),
        "parents": [date_folder_id]
    }
    csv_media = MediaFileUpload(csv_path, mimetype="text/csv", resumable=False)
    uploaded_csv = drive_service.files().create(
        body=csv_metadata,
        media_body=csv_media,
        fields="id, webViewLink"
    ).execute()

    drive_service.permissions().create(
        fileId=uploaded_csv["id"],
        body={"type": "anyone", "role": "reader"}
    ).execute()

    csv_link = uploaded_csv["webViewLink"]
    print(f"✅ CSV berhasil diupload: {csv_link}")

except Exception as e:
    csv_link = None
    print(f"⚠️ Gagal upload CSV ke Google Drive: {e}")

# --- Kirim Email ---
print("📧 Mengirim email...")
try:
    email_address = os.environ["EMAIL_ADDRESS"]
    email_password = os.environ["EMAIL_PASSWORD"]
    recipient_email = os.environ.get("RECIPIENT_EMAIL", "ferdyindra38@gmail.com")

    msg = EmailMessage()
    msg["Subject"] = f"Prakiraan Cuaca Harian STMKG - {today_str}"
    msg["From"] = email_address
    msg["To"] = recipient_email

    lines = [
        f"Prakiraan cuaca harian STMKG untuk tanggal {today_str} telah tersedia.\n",
    ]
    if video_link:
        lines.append(f"🎬 Video Prakiraan Cuaca:\n{video_link}\n")
    else:
        lines.append("⚠️ Video gagal diupload ke Google Drive.\n")

    if csv_link:
        lines.append(f"📊 File CSV:\n{csv_link}\n")
    else:
        lines.append("⚠️ CSV gagal diupload ke Google Drive.\n")

    lines.append("Semua file tersimpan di Google Drive folder tanggal hari ini.")

    msg.set_content("\n".join(lines))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)
    print(f"✅ Email berhasil dikirim ke {recipient_email}")

except KeyError as e:
    print(f"❌ Environment variable belum diset: {e}")
except Exception as e:
    print(f"❌ Gagal mengirim email: {e}")

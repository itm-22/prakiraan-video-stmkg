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
# KIRIM EMAIL
# =====================================================================
print("📧 Mengirim email...")

try:
    email_address = os.environ["EMAIL_ADDRESS"]
    email_password = os.environ["EMAIL_PASSWORD"]

    recipient_email = os.environ.get(
        "RECIPIENT_EMAIL",
        email_address,
    )

    msg = EmailMessage()
    msg["Subject"] = "Prakiraan Cuaca Harian STMKG"
    msg["From"] = email_address
    msg["To"] = recipient_email

    msg.set_content(
        "Berikut terlampir file prakiraan cuaca harian dalam format CSV dan video MP4."
    )

    # Lampirkan CSV
    with open(csv_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="text",
            subtype="csv",
            filename=os.path.basename(csv_path),
        )

    # Lampirkan Video
    with open(output_video_path, "rb") as f:
        mime_type, _ = mimetypes.guess_type(output_video_path)

        if mime_type:
            maintype, subtype = mime_type.split("/")
        else:
            maintype, subtype = "video", "mp4"

        msg.add_attachment(
            f.read(),
            maintype=maintype,
            subtype=subtype,
            filename=os.path.basename(output_video_path),
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)

    print(f"✅ Email berhasil dikirim ke {recipient_email}")

except KeyError as e:
    print(f"❌ Environment variable belum diset: {e}")

except Exception as e:
    print(f"❌ Gagal mengirim email: {e}")

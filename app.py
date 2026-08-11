from flask import Flask, request, send_file
import yt_dlp
import os
import uuid

app = Flask(__name__)
os.makedirs("downloads", exist_ok=True)

@app.route("/download", methods=["GET"])
def download():

    url = request.args.get("url")
    filename = f"downloads/{uuid.uuid4()}.mp4"

    ydl_opts = {
        "outtmpl": filename,
        "format": "best",
        "merge_output_format": "mp4",
        "quiet": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return send_file(filename, as_attachment=True)


if __name__ == "__main__":
    app.run()

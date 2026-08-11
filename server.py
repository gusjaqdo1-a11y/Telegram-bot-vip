import yt_dlp
import os
import uuid

app = Flask(__name__)

os.makedirs("downloads", exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/download", methods=["GET"])
def download():

    url = request.args.get("url")

    if not url:
        return jsonify({"error": "No URL provided"})

    filename = f"downloads/{uuid.uuid4()}.mp4"

    ydl_opts = {
        "outtmpl": filename,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return jsonify({
            "video": f"/file/{os.path.basename(filename)}"
        })

    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/file/<name>")
def file(name):
    path = f"downloads/{name}"
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

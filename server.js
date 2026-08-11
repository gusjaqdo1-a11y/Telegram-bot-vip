import express from "express";
import cors from "cors";
import { exec } from "child_process";

const app = express();
app.use(cors());

app.get("/download", (req, res) => {

    const url = req.query.url;

    if (!url) {
        return res.json({ error: "No URL" });
    }

    const cmd = `yt-dlp -f mp4 -g "${url}"`;

    exec(cmd, (err, stdout) => {

        if (err) {
            return res.json({ error: err.message });
        }

        res.json({
            video: stdout.trim()
        });
    });
});

app.listen(3000, () => console.log("Server running

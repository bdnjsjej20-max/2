import os
import re
import json
import subprocess
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
SOUND_DIR = os.path.expanduser("~/sounds")
os.makedirs(SOUND_DIR, exist_ok=True)
ALLOWED = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
current = None  # текущий процесс воспроизведения


def clean_name(name):
    name = os.path.basename(name)
    name = re.sub(r"[^\w .\-()]", "_", name, flags=re.UNICODE)
    return name


def stop_sound():
    global current
    if current and current.poll() is None:
        current.terminate()
    current = None


def play_sound(path):
    global current
    stop_sound()
    current = subprocess.Popen(
        ["mpv", "--no-video", "--really-quiet", "--ao=opensles", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def list_sounds():
    return sorted(
        f for f in os.listdir(SOUND_DIR)
        if os.path.splitext(f)[1].lower() in ALLOWED
    )


def get_volume():
    """Возвращает (текущая, максимальная) громкость мультимедиа."""
    try:
        out = subprocess.check_output(["termux-volume"], timeout=5)
        for s in json.loads(out):
            if s["stream"] == "music":
                return s["volume"], s["max_volume"]
    except Exception:
        pass
    return None, None


PAGE = """
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Звуковая панель</title>
<style>
  body { font-family: sans-serif; background:#111; color:#eee; margin:0; padding:12px; }
  h2 { margin:8px 0; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .item { display:flex; gap:4px; }
  .play { flex:1; padding:18px 8px; font-size:16px; border:0; border-radius:10px;
          background:#2d7ff9; color:#fff; word-break:break-word; }
  .play:active { background:#1b5fc4; }
  .del { width:40px; border:0; border-radius:10px; background:#552; color:#fff; }
  .stop { width:100%; padding:16px; font-size:18px; border:0; border-radius:10px;
          background:#d33; color:#fff; margin:10px 0; }
  .box { background:#222; padding:12px; border-radius:10px; margin-top:16px; }
  #msg { color:#8f8; min-height:20px; }

  /* Громкость */
  .vol { background:#222; padding:14px; border-radius:12px; margin:10px 0; }
  .vol-top { display:flex; justify-content:space-between; align-items:center; }
  .vol-num { font-size:34px; font-weight:bold; color:#6cf; }
  .vol-row { display:flex; align-items:center; gap:10px; margin:12px 0; }
  .vbtn { width:60px; height:60px; font-size:30px; border:0; border-radius:12px;
          background:#333; color:#fff; flex-shrink:0; }
  .vbtn:active { background:#555; }
  input[type=range] { -webkit-appearance:none; appearance:none; flex:1; height:16px;
          border-radius:8px; background:#444; outline:none; margin:0; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; appearance:none;
          width:44px; height:44px; border-radius:50%; background:#6cf; border:3px solid #fff; }
  input[type=range]::-moz-range-thumb { width:40px; height:40px; border-radius:50%;
          background:#6cf; border:3px solid #fff; }
  .presets { display:grid; grid-template-columns:repeat(6,1fr); gap:6px; }
  .presets button { padding:12px 0; font-size:14px; border:0; border-radius:8px;
          background:#333; color:#fff; }
  .presets button:active { background:#555; }
  .presets button.on { background:#2d7ff9; }
</style>
</head>
<body>
<h2>🔊 Звуковая панель</h2>
<button class="stop" onclick="stopAll()">⏹ СТОП</button>
<div id="msg"></div>

<div class="vol">
  <div class="vol-top">
    <span>🔈 Громкость</span>
    <span class="vol-num"><span id="vol">--</span>%</span>
  </div>
  <div class="vol-row">
    <button class="vbtn" onclick="step(-5)">−</button>
    <input type="range" id="slider" min="0" max="100" step="1" value="50">
    <button class="vbtn" onclick="step(5)">+</button>
  </div>
  <div class="presets" id="presets">
    <button onclick="setVol(0)">0</button>
    <button onclick="setVol(20)">20</button>
    <button onclick="setVol(40)">40</button>
    <button onclick="setVol(60)">60</button>
    <button onclick="setVol(80)">80</button>
    <button onclick="setVol(100)">100</button>
  </div>
</div>

<div class="grid">
{% for s in sounds %}
  <div class="item">
    <button class="play" onclick="play('{{ s|e }}')">{{ s }}</button>
    <button class="del" onclick="del('{{ s|e }}')">✕</button>
  </div>
{% else %}
  <p>Звуков пока нет. Загрузи ниже.</p>
{% endfor %}
</div>

<div class="box">
  <b>Добавить звуки (с этого телефона):</b><br><br>
  <input type="file" id="files" multiple accept="audio/*"><br><br>
  <button onclick="upload()" style="padding:12px 20px;">Загрузить</button>
</div>

<script>
function show(t){ document.getElementById('msg').textContent = t; }
async function post(url, data){
  const r = await fetch(url, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  return r.json();
}
async function play(name){ const j = await post('/play', {name}); show(j.ok ? '▶ ' + name : 'Ошибка'); }
async function stopAll(){ await post('/stop', {}); show('Остановлено'); }
async function del(name){
  if(!confirm('Удалить ' + name + '?')) return;
  await post('/delete', {name}); location.reload();
}
async function upload(){
  const files = document.getElementById('files').files;
  if(!files.length){ show('Выбери файлы'); return; }
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  show('Загружаю...');
  await fetch('/upload', {method:'POST', body:fd});
  location.reload();
}

/* ---- Громкость ---- */
const slider = document.getElementById('slider');
const volLabel = document.getElementById('vol');
let sendTimer = null;

function paint(p){
  slider.value = p;
  volLabel.textContent = p;
  const btns = document.querySelectorAll('#presets button');
  btns.forEach(b => b.classList.toggle('on', +b.textContent === p));
}

function sendVol(p){
  clearTimeout(sendTimer);
  sendTimer = setTimeout(async () => {
    try {
      const j = await post('/volume', {percent: p});
      if(!j.ok) show('Не удалось изменить громкость');
    } catch(e){ show('Нет связи с телефоном'); }
  }, 120);
}

function setVol(p){
  p = Math.max(0, Math.min(100, Math.round(p)));
  paint(p);
  sendVol(p);
}

function step(d){ setVol(+slider.value + d); }
slider.oninput = () => setVol(+slider.value);

async function loadVol(){
  try {
    const j = await (await fetch('/volume')).json();
    if(j.ok) paint(j.percent);
    else volLabel.textContent = '?';
  } catch(e){}
}
loadVol();
document.addEventListener('visibilitychange', () => { if(!document.hidden) loadVol(); });
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, sounds=list_sounds())


@app.route("/play", methods=["POST"])
def play():
    name = clean_name(request.json.get("name", ""))
    path = os.path.join(SOUND_DIR, name)
    if not os.path.isfile(path):
        return jsonify(ok=False), 404
    play_sound(path)
    return jsonify(ok=True)


@app.route("/stop", methods=["POST"])
def stop():
    stop_sound()
    return jsonify(ok=True)


@app.route("/upload", methods=["POST"])
def upload():
    for f in request.files.getlist("files"):
        name = clean_name(f.filename or "")
        if os.path.splitext(name)[1].lower() in ALLOWED:
            f.save(os.path.join(SOUND_DIR, name))
    return jsonify(ok=True)


@app.route("/delete", methods=["POST"])
def delete():
    name = clean_name(request.json.get("name", ""))
    path = os.path.join(SOUND_DIR, name)
    if os.path.isfile(path):
        os.remove(path)
    return jsonify(ok=True)


@app.route("/volume", methods=["GET"])
def volume_get():
    v, m = get_volume()
    if v is None:
        return jsonify(ok=False), 500
    return jsonify(ok=True, percent=round(v * 100 / m))


@app.route("/volume", methods=["POST"])
def volume_set():
    percent = max(0, min(100, int(request.json.get("percent", 50))))
    v, m = get_volume()
    if m is None:
        return jsonify(ok=False), 500
    subprocess.run(["termux-volume", "music", str(round(percent * m / 100))])
    return jsonify(ok=True, percent=percent)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

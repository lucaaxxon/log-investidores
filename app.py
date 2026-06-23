from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os
import json as json_lib

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "logs.db"))
PORT    = int(os.environ.get("PORT", 5000))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            investidor       TEXT NOT NULL,
            data             TEXT NOT NULL,
            tipo_contato     TEXT NOT NULL,
            apresentou_arquivo TEXT,
            follow_up        TEXT,
            comentario       TEXT,
            fase_pipeline    TEXT,
            motivo_descarte  TEXT,
            criado_em        TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investidores (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


TIPOS_CONTATO = [
    "Reunião (presencial)",
    "Reunião (online)",
    "E-mail",
    "WhatsApp",
    "Ligação",
]

ARQUIVOS = ["Não", "Teaser", "Full Deck", "Modelo"]

FASES_PIPELINE = ["NDA", "Q&A", "Soft Commitment", "Signed", "Descarte"]


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Log de Interação</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f0f2f5;
    min-height: 100vh;
    padding: 16px 16px 40px;
  }
  .card {
    background: #fff;
    border-radius: 16px;
    padding: 24px 20px;
    max-width: 480px;
    margin: 0 auto;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
  }
  h1 { font-size: 20px; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
  .subtitle { font-size: 13px; color: #888; margin-bottom: 24px; }
  .field { margin-top: 20px; }
  .field:first-child { margin-top: 0; }
  label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #444;
    margin-bottom: 7px;
  }
  .required { color: #e74c3c; }
  input[type=text], input[type=date], textarea {
    width: 100%;
    padding: 12px 14px;
    border: 1.5px solid #e0e0e0;
    border-radius: 10px;
    font-size: 15px;
    color: #222;
    background: #fafafa;
    outline: none;
    transition: border-color .2s;
  }
  input:focus, textarea:focus { border-color: #4f6ef7; background: #fff; }
  textarea { resize: vertical; min-height: 90px; }
  .autocomplete-wrap { position: relative; }
  .autocomplete-list {
    display: none;
    position: absolute;
    top: 100%; left: 0; right: 0;
    background: #fff;
    border: 1.5px solid #e0e0e0;
    border-top: none;
    border-radius: 0 0 10px 10px;
    max-height: 200px;
    overflow-y: auto;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,.1);
  }
  .autocomplete-list li {
    padding: 11px 14px;
    font-size: 14px;
    color: #222;
    cursor: pointer;
    list-style: none;
  }
  .autocomplete-list li:hover, .autocomplete-list li.active {
    background: #f0f4ff;
    color: #4f6ef7;
  }
  .pill-group { display: flex; gap: 8px; flex-wrap: wrap; }
  .pill-group input[type=radio] { display: none; }
  .pill-group label {
    margin: 0;
    padding: 9px 16px;
    border-radius: 20px;
    border: 1.5px solid #e0e0e0;
    font-size: 14px;
    font-weight: 500;
    color: #555;
    cursor: pointer;
    background: #fafafa;
    transition: all .15s;
  }
  .pill-group input[type=radio]:checked + label {
    background: #4f6ef7;
    border-color: #4f6ef7;
    color: #fff;
  }
  .btn {
    display: block;
    width: 100%;
    padding: 15px;
    margin-top: 28px;
    background: #4f6ef7;
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: background .2s;
  }
  .btn:active { background: #3755d8; }
  .btn:disabled { background: #aaa; cursor: default; }
  .toast {
    display: none;
    position: fixed;
    bottom: 28px;
    left: 50%;
    transform: translateX(-50%);
    background: #222;
    color: #fff;
    padding: 13px 24px;
    border-radius: 24px;
    font-size: 14px;
    font-weight: 600;
    z-index: 999;
    white-space: nowrap;
  }
  .toast.success { background: #27ae60; }
  .toast.error   { background: #e74c3c; }
</style>
</head>
<body>
<div class="card">
  <h1>Log de Interação</h1>
  <p class="subtitle">Registre o contato com o investidor</p>
  <form id="logForm" autocomplete="off">

    <div class="field">
      <label for="investidor">Investidor <span class="required">*</span></label>
      <div class="autocomplete-wrap">
        <input type="text" id="investidor" name="investidor" placeholder="Digite o nome..." required>
        <ul class="autocomplete-list" id="autocomplete-list"></ul>
      </div>
    </div>

    <div class="field">
      <label for="data">Data <span class="required">*</span></label>
      <input type="date" id="data" name="data" required>
    </div>

    <div class="field">
      <label>Tipo de Contato <span class="required">*</span></label>
      <div class="pill-group">
        {% for t in tipos %}
        <input type="radio" name="tipo_contato" id="tc_{{ loop.index }}" value="{{ t }}">
        <label for="tc_{{ loop.index }}">{{ t }}</label>
        {% endfor %}
      </div>
    </div>

    <div class="field">
      <label>Apresentação de arquivo? <span class="required">*</span></label>
      <div class="pill-group">
        {% for a in arquivos %}
        <input type="radio" name="apresentou_arquivo" id="arq_{{ loop.index }}" value="{{ a }}"
               {% if loop.first %}checked{% endif %}>
        <label for="arq_{{ loop.index }}">{{ a }}</label>
        {% endfor %}
      </div>
    </div>

    <div class="field">
      <label>Fase no Pipeline <span style="font-weight:400;color:#aaa">(opcional)</span></label>
      <div class="pill-group" id="fase-group">
        {% for f in fases %}
        <input type="radio" name="fase_pipeline" id="fp_{{ loop.index }}" value="{{ f }}">
        <label for="fp_{{ loop.index }}">{{ f }}</label>
        {% endfor %}
      </div>
    </div>

    <div class="field" id="motivo-block" style="display:none;">
      <label for="motivo_descarte">Motivo do Descarte <span class="required">*</span></label>
      <textarea id="motivo_descarte" name="motivo_descarte" placeholder="Descreva o motivo..."></textarea>
    </div>

    <div class="field">
      <label for="follow_up">Data de follow-up <span style="font-weight:400;color:#aaa">(opcional)</span></label>
      <input type="date" id="follow_up" name="follow_up">
    </div>

    <div class="field">
      <label for="comentario">Comentário <span style="font-weight:400;color:#aaa">(opcional)</span></label>
      <textarea id="comentario" name="comentario" placeholder="Observações sobre a interação..."></textarea>
    </div>

    <button type="submit" class="btn" id="submitBtn">Salvar Interação</button>
  </form>
</div>
<div class="toast" id="toast"></div>

<script>
const INVESTIDORES = {{ investidores_json | safe }};

function setTodayDate(id) {
  const d = new Date();
  document.getElementById(id).value =
    `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
setTodayDate('data');

const input = document.getElementById('investidor');
const list  = document.getElementById('autocomplete-list');
let activeIdx = -1;

input.addEventListener('input', () => {
  const q = input.value.trim().toLowerCase();
  list.innerHTML = ''; activeIdx = -1;
  if (!q) { list.style.display = 'none'; return; }
  const matches = INVESTIDORES.filter(n => n.toLowerCase().includes(q));
  if (!matches.length) { list.style.display = 'none'; return; }
  matches.slice(0, 8).forEach(name => {
    const li = document.createElement('li');
    li.textContent = name;
    li.addEventListener('mousedown', e => { e.preventDefault(); selectInvestidor(name); });
    list.appendChild(li);
  });
  list.style.display = 'block';
});

input.addEventListener('keydown', e => {
  const items = list.querySelectorAll('li');
  if (e.key === 'ArrowDown')  { activeIdx = Math.min(activeIdx+1, items.length-1); highlight(items); e.preventDefault(); }
  else if (e.key === 'ArrowUp')   { activeIdx = Math.max(activeIdx-1, 0); highlight(items); e.preventDefault(); }
  else if (e.key === 'Enter' && activeIdx >= 0) { selectInvestidor(items[activeIdx].textContent); e.preventDefault(); }
  else if (e.key === 'Escape') { list.style.display = 'none'; }
});

input.addEventListener('blur', () => {
  setTimeout(() => { list.style.display = 'none'; }, 150);
  const nome = input.value.trim();
  if (nome) preSelectFase(nome);
});

document.addEventListener('click', e => {
  if (!e.target.closest('.autocomplete-wrap')) list.style.display = 'none';
});

function highlight(items) {
  items.forEach((li, i) => li.classList.toggle('active', i === activeIdx));
}

function selectInvestidor(name) {
  input.value = name;
  list.style.display = 'none';
  preSelectFase(name);
}

async function preSelectFase(nome) {
  try {
    const res  = await fetch('/fase?investidor=' + encodeURIComponent(nome));
    const json = await res.json();
    document.querySelectorAll('[name=fase_pipeline]').forEach(r => r.checked = false);
    if (json.fase) {
      const match = document.querySelector(`[name=fase_pipeline][value="${json.fase}"]`);
      if (match) match.checked = true;
    }
    checkDescarte();
  } catch {}
}

function checkDescarte() {
  const el = document.querySelector('[name=fase_pipeline]:checked');
  document.getElementById('motivo-block').style.display =
    el && el.value === 'Descarte' ? 'block' : 'none';
}

document.querySelectorAll('[name=fase_pipeline]').forEach(el => {
  el.addEventListener('change', checkDescarte);
});

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast ' + type; t.style.display = 'block';
  setTimeout(() => { t.style.display = 'none'; }, 3500);
}

document.getElementById('logForm').addEventListener('submit', async e => {
  e.preventDefault();
  const form = e.target;
  const tipoEl = form.querySelector('[name=tipo_contato]:checked');
  if (!tipoEl) { showToast('Selecione o tipo de contato', 'error'); return; }
  const faseEl = form.querySelector('[name=fase_pipeline]:checked');
  const fase   = faseEl?.value || '';
  const motivo = form.motivo_descarte?.value || '';
  if (fase === 'Descarte' && !motivo.trim()) {
    showToast('Informe o motivo do descarte', 'error'); return;
  }
  const btn = document.getElementById('submitBtn');
  btn.disabled = true; btn.textContent = 'Salvando...';
  const payload = {
    investidor:         form.investidor.value.trim(),
    data:               form.data.value,
    tipo_contato:       tipoEl.value,
    apresentou_arquivo: form.querySelector('[name=apresentou_arquivo]:checked')?.value || 'Não',
    follow_up:          form.follow_up.value || '',
    comentario:         form.comentario.value,
    fase_pipeline:      fase,
    motivo_descarte:    motivo,
  };
  try {
    const res  = await fetch('/log', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
    const json = await res.json();
    if (json.ok) {
      showToast('Interação salva!', 'success');
      form.reset(); setTodayDate('data');
      document.querySelectorAll('[name=fase_pipeline]').forEach(r => r.checked = false);
      document.getElementById('motivo-block').style.display = 'none';
      document.getElementById('autocomplete-list').style.display = 'none';
    } else { showToast('Erro: ' + json.error, 'error'); }
  } catch { showToast('Erro de conexão', 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Salvar Interação'; }
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    conn = get_db()
    rows = conn.execute("SELECT nome FROM investidores ORDER BY nome").fetchall()
    conn.close()
    investidores = [r["nome"] for r in rows]
    return render_template_string(
        HTML,
        investidores_json=json_lib.dumps(investidores, ensure_ascii=False),
        tipos=TIPOS_CONTATO,
        arquivos=ARQUIVOS,
        fases=FASES_PIPELINE,
    )


@app.route("/fase")
def fase():
    investidor = request.args.get("investidor", "").strip()
    if not investidor:
        return jsonify(fase="")
    conn = get_db()
    row = conn.execute(
        "SELECT fase_pipeline FROM logs WHERE LOWER(investidor)=LOWER(?) AND fase_pipeline != '' ORDER BY id DESC LIMIT 1",
        (investidor,)
    ).fetchone()
    conn.close()
    return jsonify(fase=row["fase_pipeline"] if row else "")


@app.route("/log", methods=["POST"])
def log_entry():
    data = request.get_json()
    for field in ["investidor", "data", "tipo_contato"]:
        if not data.get(field):
            return jsonify(ok=False, error=f"Campo obrigatório: {field}")

    fase   = data.get("fase_pipeline", "")
    motivo = data.get("motivo_descarte", "") if fase == "Descarte" else ""

    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO investidores (nome) VALUES (?)",
        (data["investidor"].strip(),)
    )
    conn.execute(
        """INSERT INTO logs
           (investidor, data, tipo_contato, apresentou_arquivo, follow_up, comentario, fase_pipeline, motivo_descarte)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            data["investidor"].strip(),
            data["data"],
            data["tipo_contato"],
            data.get("apresentou_arquivo", "Não"),
            data.get("follow_up", ""),
            data.get("comentario", ""),
            fase,
            motivo,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/seed_investors", methods=["POST"])
def seed_investors():
    data = request.get_json()
    names = data.get("names", [])
    if not names:
        return jsonify(ok=False, error="Nenhum nome enviado")
    conn = get_db()
    added = 0
    for nome in names:
        nome = nome.strip()
        if nome:
            cur = conn.execute("INSERT OR IGNORE INTO investidores (nome) VALUES (?)", (nome,))
            added += cur.rowcount
    conn.commit()
    conn.close()
    return jsonify(ok=True, added=added)


@app.route("/export")
def export():
    since_id = int(request.args.get("since_id", 0))
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM logs WHERE id > ? ORDER BY id", (since_id,)
    ).fetchall()
    investors = conn.execute("SELECT nome FROM investidores ORDER BY nome").fetchall()
    conn.close()

    last_id = rows[-1]["id"] if rows else since_id
    return jsonify(
        rows=[dict(r) for r in rows],
        investors=[r["nome"] for r in investors],
        last_id=last_id,
    )


if __name__ == "__main__":
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    print(f"\n  Acesse pelo celular: http://{local_ip}:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)

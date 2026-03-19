import sqlite3
import os
import unicodedata
import re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lal_venture.db')

def ascii(text):
    if not text:
        return ""
    text = ''.join(
        c for c in unicodedata.normalize('NFD', str(text))
        if unicodedata.category(c) != 'Mn'
    )
    return text.encode('ascii', 'ignore').decode('ascii')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Tripulantes — dados completos
    c.execute('''CREATE TABLE IF NOT EXISTS tripulantes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        slug         TEXT UNIQUE,
        nome         TEXT NOT NULL,
        nome_busca   TEXT NOT NULL,
        raca         TEXT,
        patente      TEXT,
        divisao      TEXT,
        departamento TEXT,
        posto        TEXT,
        tempo_servico TEXT,
        data_admissao TEXT,
        nascimento_sl TEXT,
        cidade        TEXT,
        historia      TEXT,
        timeline      TEXT,
        cursos        TEXT,
        diario_publico INTEGER DEFAULT 0,
        total_diarios  INTEGER DEFAULT 0
    )''')

    # Pontos e promoção
    c.execute('''CREATE TABLE IF NOT EXISTS pontos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ficha_slug  TEXT NOT NULL,
        total       INTEGER DEFAULT 0,
        patente_atual TEXT,
        proxima_patente TEXT,
        pontos_necessarios INTEGER DEFAULT 0,
        pontos_faltam INTEGER DEFAULT 0,
        updated_at  TEXT
    )''')

    # Histórico de pontos
    c.execute('''CREATE TABLE IF NOT EXISTS pontos_historico (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ficha_slug  TEXT NOT NULL,
        pontos      INTEGER,
        motivo      TEXT,
        data        TEXT
    )''')

    # Missões/operações
    c.execute('''CREATE TABLE IF NOT EXISTS missoes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo      TEXT NOT NULL,
        data        TEXT,
        nave_slug   TEXT,
        status      TEXT,
        resumo      TEXT
    )''')

    # Naves
    c.execute('''CREATE TABLE IF NOT EXISTS naves (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        slug            TEXT UNIQUE,
        nome            TEXT NOT NULL,
        classe          TEXT,
        comissionamento TEXT,
        comandante      TEXT,
        comandante_slug TEXT,
        tipo            TEXT,
        status          TEXT,
        descricao       TEXT
    )''')

    # Tripulantes de cada nave
    c.execute('''CREATE TABLE IF NOT EXISTS naves_tripulantes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nave_slug   TEXT NOT NULL,
        nome_nave   TEXT,
        ficha_slug  TEXT,
        nome        TEXT,
        posto       TEXT
    )''')

    # Divisões
    c.execute('''CREATE TABLE IF NOT EXISTS divisoes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nome            TEXT NOT NULL,
        cor             TEXT,
        qtd_tripulantes INTEGER,
        chefe           TEXT,
        descricao       TEXT
    )''')

    # Patentes com hierarquia e pontos
    c.execute('''CREATE TABLE IF NOT EXISTS patentes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nome        TEXT NOT NULL,
        hierarquia  INTEGER,
        pontos_min  INTEGER DEFAULT 0,
        descricao   TEXT
    )''')

    # Lore geral
    c.execute('''CREATE TABLE IF NOT EXISTS lore (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        tema    TEXT NOT NULL,
        conteudo TEXT NOT NULL
    )''')

    # Índices
    c.execute('CREATE INDEX IF NOT EXISTS idx_tripulante_busca ON tripulantes(nome_busca)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tripulante_slug  ON tripulantes(slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pontos_slug      ON pontos(ficha_slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_hist_slug        ON pontos_historico(ficha_slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_nave_slug        ON naves(slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_nave_trip        ON naves_tripulantes(nave_slug)')

    conn.commit()
    conn.close()
    print(f"Banco inicializado em {DB_PATH}")


# ─── BUSCAS ──────────────────────────────────────────────────────────────────

def buscar_tripulante(nome):
    """Busca tripulante por nome / slug (parcial, case-insensitive)."""
    conn = get_db()
    nome_lower = nome.strip().lower()
    # Remove " resident" e parênteses (display name SL)
    nome_lower = re.sub(r'\s*\([^)]*\)', '', nome_lower).strip()
    nome_lower = re.sub(r'\s+resident$', '', nome_lower).strip()

    for query in [
        "SELECT * FROM tripulantes WHERE nome_busca = ?",
        "SELECT * FROM tripulantes WHERE slug = ?",
        "SELECT * FROM tripulantes WHERE nome_busca LIKE ?",
        "SELECT * FROM tripulantes WHERE slug LIKE ?",
    ]:
        param = nome_lower if '= ?' in query else f"%{nome_lower}%"
        row = conn.execute(query, (param,)).fetchone()
        if row:
            conn.close()
            return dict(row)

    # Fallback: primeiro token com >= 4 chars
    primeiro = nome_lower.split()[0] if nome_lower.split() else nome_lower
    if len(primeiro) >= 4:
        row = conn.execute(
            "SELECT * FROM tripulantes WHERE nome_busca LIKE ?", (f"{primeiro}%",)
        ).fetchone()
        if row:
            conn.close()
            return dict(row)

    conn.close()
    return None


def buscar_pontos(ficha_slug):
    conn = get_db()
    row = conn.execute("SELECT * FROM pontos WHERE ficha_slug = ?", (ficha_slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_historico_pontos(ficha_slug, limite=5):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pontos_historico WHERE ficha_slug = ? ORDER BY data DESC LIMIT ?",
        (ficha_slug, limite)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_nave_do_tripulante(ficha_slug):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM naves_tripulantes WHERE ficha_slug = ?", (ficha_slug,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def buscar_tripulantes_da_nave(nave_slug):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM naves_tripulantes WHERE nave_slug = ? ORDER BY posto", (nave_slug,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_nave(nome_ou_slug):
    conn = get_db()
    n = nome_ou_slug.lower().strip()
    row = conn.execute(
        "SELECT * FROM naves WHERE LOWER(slug) LIKE ? OR LOWER(nome) LIKE ?",
        (f"%{n}%", f"%{n}%")
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_naves():
    conn = get_db()
    rows = conn.execute("SELECT * FROM naves ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_missoes(limite=5):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM missoes ORDER BY data DESC LIMIT ?", (limite,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_divisoes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM divisoes ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_divisao(nome):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM divisoes WHERE LOWER(nome) LIKE ?", (f"%{nome.lower()}%",)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_patentes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM patentes ORDER BY hierarquia").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_lore(tema):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM lore WHERE LOWER(tema) LIKE ?", (f"%{tema.lower()}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_nomes_na_mensagem(mensagem, excluir_nome_busca=""):
    clean = re.sub(r'[.,!?;:"\'()]', ' ', mensagem.lower())
    palavras = clean.split()

    conn = get_db()
    encontrados = []
    vistos = set()
    if excluir_nome_busca:
        vistos.add(excluir_nome_busca.lower())

    skip = {'quem', 'como', 'qual', 'onde', 'voce', 'sobre', 'busque',
            'informacoes', 'dados', 'fale', 'conte', 'diga', 'para',
            'esse', 'essa', 'este', 'esta', 'dele', 'dela', 'nome',
            'rank', 'divisao', 'patente', 'tripulante', 'oficial',
            'lal', 'data', 'conhece', 'sabe', 'nave', 'naves'}

    # Pares consecutivos
    for i in range(len(palavras) - 1):
        if len(encontrados) >= 3: break
        par = palavras[i] + " " + palavras[i + 1]
        if len(par) < 5: continue
        row = conn.execute("SELECT * FROM tripulantes WHERE nome_busca = ?", (par,)).fetchone()
        if row:
            d = dict(row)
            if d['nome_busca'] not in vistos:
                encontrados.append(d)
                vistos.add(d['nome_busca'])

    # Palavras individuais
    for palavra in palavras:
        if len(encontrados) >= 3: break
        if len(palavra) < 4 or palavra in skip: continue
        row = conn.execute(
            "SELECT * FROM tripulantes WHERE nome_busca LIKE ?", (f"{palavra}%",)
        ).fetchone()
        if row:
            d = dict(row)
            if d['nome_busca'] not in vistos:
                encontrados.append(d)
                vistos.add(d['nome_busca'])

    conn.close()
    return encontrados

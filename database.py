import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lal_venture.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS tripulantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        nome_busca TEXT NOT NULL,
        raca TEXT,
        patente TEXT,
        divisao TEXT,
        departamento TEXT,
        posto TEXT,
        tempo_servico TEXT,
        data_admissao TEXT,
        nascimento_sl TEXT,
        cidade TEXT,
        carreira TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS divisoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cor TEXT,
        qtd_tripulantes INTEGER,
        descricao TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS patentes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        hierarquia INTEGER,
        descricao TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS naves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        classe TEXT,
        comissionamento TEXT,
        comandante TEXT,
        tipo TEXT,
        status TEXT,
        descricao TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS lore (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tema TEXT NOT NULL,
        conteudo TEXT NOT NULL
    )''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_tripulante_busca ON tripulantes(nome_busca)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_divisao_nome ON divisoes(nome)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_patente_nome ON patentes(nome)')

    conn.commit()
    conn.close()
    print(f"Banco de dados inicializado em {DB_PATH}")


def buscar_tripulante(nome):
    """Busca tripulante por nome (parcial, case-insensitive)."""
    conn = get_db()
    nome_lower = nome.strip().lower()

    # 1. Busca exata pelo nome de busca
    row = conn.execute(
        "SELECT * FROM tripulantes WHERE nome_busca = ?", (nome_lower,)
    ).fetchone()

    if not row:
        # 2. Busca parcial (LIKE)
        row = conn.execute(
            "SELECT * FROM tripulantes WHERE nome_busca LIKE ?", (f"%{nome_lower}%",)
        ).fetchone()

    if not row:
        # 3. Busca por primeiro nome
        primeiro = nome_lower.split()[0] if nome_lower.split() else nome_lower
        if len(primeiro) >= 4:
            row = conn.execute(
                "SELECT * FROM tripulantes WHERE nome_busca LIKE ?", (f"{primeiro}%",)
            ).fetchone()

    conn.close()
    return dict(row) if row else None


def listar_divisoes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM divisoes ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_divisao(nome):
    conn = get_db()
    nome_lower = nome.strip().lower()
    row = conn.execute(
        "SELECT * FROM divisoes WHERE LOWER(nome) LIKE ?", (f"%{nome_lower}%",)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def listar_patentes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM patentes ORDER BY hierarquia").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_naves():
    conn = get_db()
    rows = conn.execute("SELECT * FROM naves ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_lore(tema):
    conn = get_db()
    tema_lower = tema.strip().lower()
    rows = conn.execute(
        "SELECT * FROM lore WHERE LOWER(tema) LIKE ?", (f"%{tema_lower}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

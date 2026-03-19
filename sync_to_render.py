#!/usr/bin/env python3
"""
sync_to_render.py — Exporta dados do MySQL local (XAMPP) e envia para o Render Flask API.

Uso:
    python sync_to_render.py

Rode sempre que atualizar dados no site (fichas, pontos, naves).
O script lê do MySQL local (localhost) e faz POST para o Render.
"""
import json
import sys
import unicodedata
import requests
import mysql.connector
from datetime import datetime

# ── Configuração ──────────────────────────────────────────────────────────────
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_DB   = 'frota_venture'
MYSQL_USER = 'root'
MYSQL_PASS = ''

RENDER_URL  = 'https://lal-api.onrender.com/sync/full'
SYNC_KEY    = 'venture2025'  # deve coincidir com LAL_SYNC_KEY no Render


def fa(text):
    """ASCII puro — remove acentos."""
    if not text:
        return ''
    text = ''.join(
        c for c in unicodedata.normalize('NFD', str(text))
        if unicodedata.category(c) != 'Mn'
    )
    return text.encode('ascii', 'ignore').decode('ascii')


def connect():
    return mysql.connector.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        database=MYSQL_DB, user=MYSQL_USER,
        password=MYSQL_PASS, charset='utf8mb4'
    )


def export_tripulantes(cur):
    cur.execute("""
        SELECT slug, nome, patente, divisao, departamento, raca, cidade,
               admissao, nascimento_sl, historia, timeline, cursos, diarios
        FROM fichas
        ORDER BY nome
    """)
    rows = cur.fetchall()
    result = []
    for r in rows:
        slug   = r['slug'] or ''
        diarios_raw = r['diarios']
        try:
            diarios_list = json.loads(diarios_raw) if diarios_raw else []
        except:
            diarios_list = []
        diario_publico = any(d.get('publico') for d in diarios_list) if isinstance(diarios_list, list) else False
        total_diarios  = sum(1 for d in diarios_list if d.get('publico')) if isinstance(diarios_list, list) else 0

        result.append({
            'slug':          slug,
            'nome':          r['nome'] or '',
            'patente':       r['patente'] or '',
            'divisao':       r['divisao'] or '',
            'departamento':  r['departamento'] or '',
            'raca':          r['raca'] or '',
            'cidade':        r['cidade'] or '',
            'admissao':      str(r['admissao']) if r['admissao'] else '',
            'nascimento_sl': str(r['nascimento_sl']) if r['nascimento_sl'] else '',
            'historia':      r['historia'] or '',
            'timeline':      json.loads(r['timeline']) if r['timeline'] else [],
            'cursos':        json.loads(r['cursos']) if r['cursos'] else {},
            'diario_publico': diario_publico,
            'total_diarios':  total_diarios,
        })
    print(f"  -> {len(result)} tripulantes exportados")
    return result


def export_pontos(cur):
    # Regras de promoco: pontos minimos por patente
    PROXIMA_PATENTE = {
        'Recruta': 'Designado', 'Designado': 'Cadete', 'Cadete': 'Alferes',
        'Alferes': 'Tenente Junior', 'Tenente Junior': 'Tenente',
        'Tenente': 'Tenente Comandante', 'Tenente Comandante': 'Comandante',
        'Comandante': 'Capitao', 'Capitao': 'Comodoro',
        'Comodoro': None, 'Vice-Almirante': None, 'Almirante': None,
    }
    PONTOS_NECESSARIOS = {
        'Designado': 50, 'Cadete': 150, 'Alferes': 300,
        'Tenente Junior': 500, 'Tenente': 700, 'Tenente Comandante': 900,
        'Comandante': 1100, 'Capitao': 1300, 'Comodoro': 99999,
    }

    # Somar pontos por tripulante direto da tabela pontos
    cur.execute("""
        SELECT f.slug as ficha_slug, f.patente,
               COALESCE((SELECT SUM(p.pontos) FROM pontos p WHERE p.ficha_slug = f.slug), 0) as total
        FROM fichas f
    """)
    rows = cur.fetchall()
    result = []
    for r in rows:
        patente    = fa(r['patente'] or '')
        total      = int(r['total'] or 0)
        prox       = PROXIMA_PATENTE.get(patente)
        pontos_nec = PONTOS_NECESSARIOS.get(prox, 0) if prox else 0
        result.append({
            'ficha_slug':         r['ficha_slug'],
            'total':              total,
            'patente_atual':      patente,
            'proxima_patente':    prox or 'PATENTE MAXIMA',
            'pontos_necessarios': pontos_nec,
            'pontos_faltam':      max(0, pontos_nec - total) if prox else 0,
            'updated_at':         datetime.now().isoformat(),
        })
    print(f"  -> {len(result)} registros de pontos exportados")
    return result


def export_historico_pontos(cur):
    # Tabela 'pontos' tem: at_id, ficha_slug, tipo, descricao, R, D, M, P, bonus, pontos, data
    try:
        cur.execute("""
            SELECT ficha_slug, pontos, descricao as motivo, tipo, data
            FROM pontos
            ORDER BY data DESC
            LIMIT 2000
        """)
        rows = cur.fetchall()
        result = [{
            'ficha_slug': r['ficha_slug'],
            'pontos':     int(r['pontos'] or 0),
            'motivo':     fa((r['motivo'] or '') + (' [' + fa(r['tipo'] or '') + ']' if r['tipo'] else '')),
            'data':       str(r['data']) if r['data'] else '',
        } for r in rows]
        print(f"  -> {len(result)} entradas de historico de pontos exportadas")
        return result
    except Exception as e:
        print(f"  [AVISO] Historico pontos: {e}")
        return []


def export_naves(cur):
    # Tentar ler da tabela naves_crew ou montar manualmente
    try:
        cur.execute("SELECT * FROM naves_crew")
        rows = cur.fetchall()
    except:
        rows = []

    naves_map = {
        'adventure': {'nome': 'USS Adventure NCC 74508',   'classe': 'Desconhecida', 'status': 'Ativa'},
        'altotting':  {'nome': 'USS Altotting NCC 171133', 'classe': 'Desconhecida', 'status': 'Ativa'},
        'nautilus':  {'nome': 'USS Nautilus NCC 38187',    'classe': 'Desconhecida', 'status': 'Ativa'},
        'rerum':     {'nome': 'USS Rerum NCC 61913',       'classe': 'Desconhecida', 'status': 'Ativa'},
        'serenity':  {'nome': 'USS Serenity NCC 7777',     'classe': 'Explorer',     'status': 'Ativa'},
        'suidara':   {'nome': 'USS Suidara NCC 7808',      'classe': 'Desconhecida', 'status': 'Ativa'},
        'venture':   {'nome': 'USS Venture NCC 71854',     'classe': 'Sovereign',    'status': 'Ativa'},
    }

    result = []
    tripulantes_naves = []

    for r in rows:
        slug      = r['nave_slug']
        nome_nave = naves_map.get(slug, {}).get('nome', slug.upper())
        cap_slug  = r.get('capitao_slug', '')

        # Buscar nome do capitão
        try:
            cur.execute("SELECT nome FROM fichas WHERE slug = %s", (cap_slug,))
            cap_row = cur.fetchone()
            cap_nome = fa(cap_row['nome']) if cap_row else cap_slug
        except:
            cap_nome = cap_slug

        result.append({
            'slug':             slug,
            'nome':             nome_nave,
            'classe':           naves_map.get(slug, {}).get('classe', ''),
            'comandante':       cap_nome,
            'comandante_slug':  cap_slug,
            'status':           naves_map.get(slug, {}).get('status', 'Ativa'),
        })

        # Capitão como tripulante
        if cap_slug:
            tripulantes_naves.append({
                'nave_slug':  slug,
                'nome_nave':  nome_nave,
                'ficha_slug': cap_slug,
                'nome':       cap_nome,
                'posto':      'Capitao',
            })

        # Outros tripulantes
        try:
            trips = json.loads(r.get('tripulantes') or '[]')
            for t in trips:
                f_slug = t.get('fichaSlug', '')
                try:
                    cur.execute("SELECT nome FROM fichas WHERE slug = %s", (f_slug,))
                    t_row = cur.fetchone()
                    t_nome = fa(t_row['nome']) if t_row else f_slug
                except:
                    t_nome = f_slug
                tripulantes_naves.append({
                    'nave_slug':  slug,
                    'nome_nave':  nome_nave,
                    'ficha_slug': f_slug,
                    'nome':       t_nome,
                    'posto':      fa(t.get('posto', 'Tripulante')),
                })
        except:
            pass

    # Se não tem tabela naves_crew, exportar apenas dados estáticos
    if not result:
        for slug, info in naves_map.items():
            result.append({'slug': slug, 'nome': info['nome'],
                           'classe': info['classe'], 'status': info['status'],
                           'comandante': '', 'comandante_slug': ''})

    print(f"  -> {len(result)} naves, {len(tripulantes_naves)} atribuições exportadas")
    return result, tripulantes_naves


def export_missoes(cur):
    try:
        cur.execute("""
            SELECT titulo, data, nave_slug, texto
            FROM missoes ORDER BY data DESC LIMIT 50
        """)
        rows = cur.fetchall()
        result = [{
            'titulo':    r['titulo'] or '',
            'data':      str(r['data']) if r['data'] else '',
            'nave_slug': r['nave_slug'] or '',
            'resumo':    fa((r['texto'] or '')[:200]),
        } for r in rows]
        print(f"  -> {len(result)} missoes exportadas")
        return result
    except Exception as e:
        print(f"  [AVISO] Tabela missoes: {e}")
        return []


def main():
    print("=" * 60)
    print("LAL-API Sync -- MySQL Local -> Render")
    print("=" * 60)

    try:
        conn = connect()
        cur = conn.cursor(dictionary=True)
        print("[1/5] Conectado ao MySQL local")
    except Exception as e:
        print(f"ERRO ao conectar ao MySQL: {e}")
        sys.exit(1)

    print("[2/5] Exportando dados...")
    tripulantes      = export_tripulantes(cur)
    pontos           = export_pontos(cur)
    pontos_historico = export_historico_pontos(cur)
    naves, naves_trip = export_naves(cur)
    missoes          = export_missoes(cur)
    cur.close()
    conn.close()

    divisoes = [
        {'nome': 'Comando',      'cor': 'vermelho', 'qtd_tripulantes': 3,  'chefe': 'RonnAndrew',          'descricao': 'Lideranca estrategica e tomada de decisoes.'},
        {'nome': 'Academia',     'cor': 'cinza',    'qtd_tripulantes': 5,  'chefe': 'Achila16',            'descricao': 'Tripulantes em treinamento ou reciclagem.'},
        {'nome': 'Ciencias',     'cor': 'azul',     'qtd_tripulantes': 5,  'chefe': 'Marchezini Winchester','descricao': 'Experimentos, pesquisa, astronomia, divisao medica.'},
        {'nome': 'Comunicacoes', 'cor': 'verde',    'qtd_tripulantes': 1,  'chefe': 'Tvashtar Uriza',      'descricao': 'Presenca do Grupo nos meios de comunicacao.'},
        {'nome': 'Engenharia',   'cor': 'amarelo',  'qtd_tripulantes': 4,  'chefe': 'laizamia',            'descricao': 'Construcao e manutencao de estruturas e naves.'},
        {'nome': 'Operacoes',    'cor': 'amarelo',  'qtd_tripulantes': 2,  'chefe': 'Ludmilla Benoir',     'descricao': 'Pessoal, suprimentos, logistica, eventos, RPG.'},
        {'nome': 'Tatico',       'cor': 'vermelho', 'qtd_tripulantes': 2,  'chefe': 'DanielRoma',          'descricao': 'Taticas de combate e armamentos.'},
        {'nome': 'Civil',        'cor': 'neutro',   'qtd_tripulantes': 1,  'chefe': '',                    'descricao': 'Pessoal nao pertencente a Frota Estelar.'},
    ]

    payload = {
        'key':              SYNC_KEY,
        'tripulantes':      tripulantes,
        'pontos':           pontos,
        'pontos_historico': pontos_historico,
        'naves':            naves,
        'naves_tripulantes': naves_trip,
        'missoes':          missoes,
        'divisoes':         divisoes,
    }

    total_bytes = len(json.dumps(payload))
    print(f"\n[3/5] Payload montado: {total_bytes:,} bytes")
    print(f"[4/5] Enviando para {RENDER_URL} ...")

    try:
        resp = requests.post(
            RENDER_URL,
            json=payload,
            timeout=120,
            headers={'Content-Type': 'application/json'}
        )
        if resp.status_code == 200:
            stats = resp.json().get('stats', {})
            print(f"[5/5] SUCESSO! Stats: {stats}")
        elif resp.status_code == 401:
            print("ERRO: Chave SYNC_KEY incorreta. Verifique SYNC_KEY no script e LAL_SYNC_KEY no Render.")
        else:
            print(f"ERRO HTTP {resp.status_code}: {resp.text[:300]}")
    except requests.exceptions.ConnectionError:
        print("ERRO: Nao foi possivel conectar ao Render. Verifique se o servico esta ativo em render.com")
    except requests.exceptions.Timeout:
        print("AVISO: Timeout. O Render pode estar inicializando (free tier dorme apos inatividade). Tente novamente.")
    except Exception as e:
        print(f"ERRO inesperado: {e}")


if __name__ == '__main__':
    main()

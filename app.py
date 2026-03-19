"""
app.py — Flask API LAL Data (Render)
Arquitetura:
  SL (llHTTPRequest) -> Render Flask /rag (sem anti-bot, texto plano ASCII)
  InfinityFree PHP / local Python -> POST /sync/full (atualiza SQLite)
"""
import os
import unicodedata
import json
import re
from flask import Flask, request, jsonify
from database import (
    get_db, init_db, DB_PATH,
    buscar_tripulante, buscar_pontos, buscar_historico_pontos,
    buscar_nave_do_tripulante, buscar_tripulantes_da_nave, buscar_nave,
    listar_naves, listar_missoes, listar_divisoes, buscar_divisao,
    listar_patentes, buscar_lore, buscar_nomes_na_mensagem
)

app = Flask(__name__)

# ── Chave secreta mínima para o endpoint /sync/full ──────────────────────────
SYNC_KEY = os.environ.get('LAL_SYNC_KEY', 'venture2025')


def fa(text):
    """Converte para ASCII puro (remove acentos)."""
    if not text:
        return ""
    text = ''.join(
        c for c in unicodedata.normalize('NFD', str(text))
        if unicodedata.category(c) != 'Mn'
    )
    return text.encode('ascii', 'ignore').decode('ascii')


def ad(d):
    """ASCII dict — converte valores string de um dict."""
    return {k: fa(v) if isinstance(v, str) else v for k, v in d.items()}


# ═══════════════════════════════════════════════════════════════════════════════
#  FASE 1 — ROTAS DE MANUTENÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/health')
def health():
    return jsonify({"status": "online", "service": "lal-api", "version": "2.0"})


@app.route('/sync/full', methods=['POST'])
def sync_full():
    """
    Recebe JSON completo do site e atualiza o SQLite.
    Esperado no body:
    {
      "key": "venture2025",
      "tripulantes": [...],
      "pontos": [...],
      "pontos_historico": [...],
      "naves": [...],
      "naves_tripulantes": [...],
      "missoes": [...],
      "divisoes": [...],
      "patentes": [...]
    }
    """
    data = request.get_json(force=True, silent=True) or {}
    if data.get('key') != SYNC_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    c = conn.cursor()
    stats = {}

    # ── Tripulantes ──────────────────────────────────────────────────────────
    if 'tripulantes' in data:
        c.execute('DELETE FROM tripulantes')
        for t in data['tripulantes']:
            slug      = fa(t.get('slug', ''))
            nome      = fa(t.get('nome', ''))
            nome_busca = nome.lower().replace(' resident', '').strip()
            c.execute('''INSERT INTO tripulantes
                (slug, nome, nome_busca, raca, patente, divisao, departamento,
                 posto, tempo_servico, data_admissao, nascimento_sl, cidade,
                 historia, timeline, cursos, diario_publico, total_diarios)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (slug, nome, nome_busca,
                 fa(t.get('raca','')), fa(t.get('patente','')),
                 fa(t.get('divisao','')), fa(t.get('departamento','')),
                 fa(t.get('posto','')), fa(t.get('tempo_servico','')),
                 t.get('admissao',''), t.get('nascimento_sl',''), fa(t.get('cidade','')),
                 fa(t.get('historia','')),
                 json.dumps(t.get('timeline', []), ensure_ascii=True),
                 json.dumps(t.get('cursos', {}), ensure_ascii=True),
                 1 if t.get('diario_publico') else 0,
                 int(t.get('total_diarios', 0))
                ))
        stats['tripulantes'] = len(data['tripulantes'])

    # ── Pontos ───────────────────────────────────────────────────────────────
    if 'pontos' in data:
        c.execute('DELETE FROM pontos')
        for p in data['pontos']:
            c.execute('''INSERT INTO pontos
                (ficha_slug, total, patente_atual, proxima_patente,
                 pontos_necessarios, pontos_faltam, updated_at)
                VALUES (?,?,?,?,?,?,?)''',
                (p.get('ficha_slug',''), int(p.get('total',0)),
                 fa(p.get('patente_atual','')), fa(p.get('proxima_patente','')),
                 int(p.get('pontos_necessarios',0)), int(p.get('pontos_faltam',0)),
                 p.get('updated_at','')))
        stats['pontos'] = len(data['pontos'])

    # ── Histórico de pontos ───────────────────────────────────────────────────
    if 'pontos_historico' in data:
        c.execute('DELETE FROM pontos_historico')
        for h in data['pontos_historico']:
            c.execute('''INSERT INTO pontos_historico
                (ficha_slug, pontos, motivo, data)
                VALUES (?,?,?,?)''',
                (h.get('ficha_slug',''), int(h.get('pontos',0)),
                 fa(h.get('motivo','')), h.get('data','')))
        stats['pontos_historico'] = len(data['pontos_historico'])

    # ── Naves ─────────────────────────────────────────────────────────────────
    if 'naves' in data:
        c.execute('DELETE FROM naves')
        for n in data['naves']:
            c.execute('''INSERT INTO naves
                (slug, nome, classe, comissionamento, comandante, comandante_slug,
                 tipo, status, descricao)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (fa(n.get('slug','')), fa(n.get('nome','')),
                 fa(n.get('classe','')), n.get('comissionamento',''),
                 fa(n.get('comandante','')), fa(n.get('comandante_slug','')),
                 fa(n.get('tipo','')), fa(n.get('status','')),
                 fa(n.get('descricao',''))))
        stats['naves'] = len(data['naves'])

    # ── Naves — tripulantes ───────────────────────────────────────────────────
    if 'naves_tripulantes' in data:
        c.execute('DELETE FROM naves_tripulantes')
        for nt in data['naves_tripulantes']:
            c.execute('''INSERT INTO naves_tripulantes
                (nave_slug, nome_nave, ficha_slug, nome, posto)
                VALUES (?,?,?,?,?)''',
                (fa(nt.get('nave_slug','')), fa(nt.get('nome_nave','')),
                 fa(nt.get('ficha_slug','')), fa(nt.get('nome','')),
                 fa(nt.get('posto',''))))
        stats['naves_tripulantes'] = len(data['naves_tripulantes'])

    # ── Missões ───────────────────────────────────────────────────────────────
    if 'missoes' in data:
        c.execute('DELETE FROM missoes')
        for m in data['missoes']:
            c.execute('''INSERT INTO missoes
                (titulo, data, nave_slug, status, resumo)
                VALUES (?,?,?,?,?)''',
                (fa(m.get('titulo','')), m.get('data',''),
                 fa(m.get('nave_slug','')), fa(m.get('status','')),
                 fa(m.get('resumo',''))))
        stats['missoes'] = len(data['missoes'])

    # ── Divisões ──────────────────────────────────────────────────────────────
    if 'divisoes' in data:
        c.execute('DELETE FROM divisoes')
        for d in data['divisoes']:
            c.execute('''INSERT INTO divisoes
                (nome, cor, qtd_tripulantes, chefe, descricao)
                VALUES (?,?,?,?,?)''',
                (fa(d.get('nome','')), fa(d.get('cor','')),
                 int(d.get('qtd_tripulantes', 0)),
                 fa(d.get('chefe','')), fa(d.get('descricao',''))))
        stats['divisoes'] = len(data['divisoes'])

    # ── Patentes ──────────────────────────────────────────────────────────────
    if 'patentes' in data:
        c.execute('DELETE FROM patentes')
        for p in data['patentes']:
            c.execute('''INSERT INTO patentes
                (nome, hierarquia, pontos_min, descricao)
                VALUES (?,?,?,?)''',
                (fa(p.get('nome','')), int(p.get('hierarquia',0)),
                 int(p.get('pontos_min',0)), fa(p.get('descricao',''))))
        stats['patentes'] = len(data['patentes'])

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "stats": stats}), 200


# ═══════════════════════════════════════════════════════════════════════════════
#  FASE 2 — ROTA RAG PARA O LSL
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/rag')
def get_rag():
    """
    Rota principal para o NPC no SL.
    GET /rag?speaker=sailespy2&msg=quem+sou+eu&ctx=ultimo_citado
    Retorna: texto plano ASCII com contexto completo
    """
    speaker = request.args.get('speaker', '').strip()
    msg     = request.args.get('msg', '').strip()
    ctx     = request.args.get('ctx', '').strip()

    if not speaker and not msg:
        return "ERRO:parametros insuficientes", 400

    resultado = []
    msg_lower = msg.lower() if msg else ""

    # ── 1. Ficha do speaker (quem está falando) ──────────────────────────────
    speaker_slug = ""
    if speaker:
        trip = buscar_tripulante(speaker)
        if trip:
            t = ad(trip)
            speaker_slug = t.get('slug', '')
            entry = (f"[FALANTE] {t['nome']} | Patente: {t['patente']} | "
                     f"Divisao: {t['divisao']}")
            if t.get('departamento'): entry += f" | Depto: {t['departamento']}"
            if t.get('raca'):         entry += f" | Raca: {t['raca']}"
            if t.get('tempo_servico'): entry += f" | Servico: {t['tempo_servico']}"
            resultado.append(entry)

            # Pontos de promoção do speaker
            if any(w in msg_lower for w in ['ponto', 'promo', 'patente', 'quanto falta',
                                             'faltam', 'proximo', 'proxima', 'rank',
                                             'minha patente', 'meus pontos', 'sou eu',
                                             'quem sou']):
                pts = buscar_pontos(speaker_slug)
                if pts:
                    p = ad(pts)
                    if p.get('proxima_patente') and p.get('proxima_patente') != p.get('patente_atual'):
                        resultado.append(
                            f"[PONTOS {t['nome']}] Total: {p['total']} pts | "
                            f"Proxima patente: {p['proxima_patente']} "
                            f"(faltam {p['pontos_faltam']} pts de {p['pontos_necessarios']} necessarios)"
                        )
                    else:
                        resultado.append(f"[PONTOS {t['nome']}] Total: {p['total']} pts | Patente maxima atingida.")

            # Nave do speaker
            nave_trip = buscar_nave_do_tripulante(speaker_slug)
            if nave_trip:
                nt = ad(nave_trip)
                resultado.append(
                    f"[NAVE {t['nome']}] Embarcado em {nt['nome_nave']} | Posto: {nt['posto']}"
                )

            # Diários
            if trip.get('diario_publico') and trip.get('total_diarios', 0) > 0:
                resultado.append(
                    f"[DIARIOS {t['nome']}] Possui {trip['total_diarios']} diario(s) publico(s)."
                )

            # Timeline (últimas 5 entradas)
            if any(w in msg_lower for w in ['carreira', 'historico', 'timeline',
                                             'quando', 'promovido', 'transfer',
                                             'minha carreira', 'meu historico']):
                try:
                    tl = json.loads(trip.get('timeline') or '[]')
                    tl_sorted = sorted(tl, key=lambda x: x.get('data',''), reverse=True)[:5]
                    for ev in tl_sorted:
                        resultado.append(f"[CARREIRA] {ev.get('data','?')}: {fa(ev.get('evento',''))}")
                except:
                    pass

            # Cursos
            if any(w in msg_lower for w in ['curso', 'academia', 'formacao', 'treina',
                                             'meus cursos', 'estudei']):
                try:
                    cur = json.loads(trip.get('cursos') or '{}')
                    academia = cur.get('academia', [])
                    if academy := academia[:8]:
                        for c_item in academy:
                            resultado.append(
                                f"[CURSO] {fa(c_item.get('area',''))} - "
                                f"{fa(c_item.get('nome',''))} ({c_item.get('data','')})"
                            )
                except:
                    pass

    # ── 2. Tripulantes citados na mensagem ───────────────────────────────────
    citados = buscar_nomes_na_mensagem(msg + " " + ctx, excluir_nome_busca=speaker_slug)
    for trip in citados:
        t = ad(trip)
        slug = t.get('slug', '')
        entry = (f"[TRIPULANTE] {t['nome']} | Patente: {t['patente']} | "
                 f"Divisao: {t['divisao']}")
        if t.get('raca'):         entry += f" | Raca: {t['raca']}"
        if t.get('departamento'): entry += f" | Depto: {t['departamento']}"
        if t.get('tempo_servico'): entry += f" | Servico: {t['tempo_servico']}"
        resultado.append(entry)

        # Pontos do citado se perguntado
        if any(w in msg_lower for w in ['ponto', 'promo', 'falta', 'rank']):
            pts = buscar_pontos(slug)
            if pts:
                p = ad(pts)
                if p.get('proxima_patente'):
                    resultado.append(
                        f"[PONTOS {t['nome']}] Total: {p['total']} | "
                        f"Proxima: {p['proxima_patente']} (faltam {p['pontos_faltam']})"
                    )

        # Nave do citado
        nave_trip = buscar_nave_do_tripulante(slug)
        if nave_trip:
            nt = ad(nave_trip)
            resultado.append(f"[NAVE {t['nome']}] {nt['nome_nave']} | Posto: {nt['posto']}")

        # Cursos do citado
        if any(w in msg_lower for w in ['curso', 'academia', 'formacao']):
            try:
                cur = json.loads(trip.get('cursos') or '{}')
                academia = cur.get('academia', [])[:5]
                for c_item in academia:
                    resultado.append(f"[CURSO {t['nome']}] {fa(c_item.get('nome',''))}")
            except:
                pass

    # ── 3. Naves ─────────────────────────────────────────────────────────────
    nave_kw = ['nave', 'naves', 'uss', 'esquadra', 'frota', 'capitao', 'capitan',
               'adventure', 'altotting', 'nautilus', 'rerum', 'serenity', 'suidara', 'venture']
    if any(w in msg_lower for w in nave_kw):
        # Nave específica?
        naves = listar_naves()
        found_nave = False
        for n in naves:
            nslug = fa(n.get('slug','')).lower()
            nnome = fa(n.get('nome','')).lower()
            if any(w in msg_lower for w in nslug.split('-') + nnome.split()):
                nt_data = ad(n)
                entry = (f"[NAVE] {nt_data['nome']} | Classe: {nt_data['classe']} | "
                         f"Cmd: {nt_data['comandante']} | Status: {nt_data['status']}")
                if nt_data.get('descricao'): entry += f" | {nt_data['descricao']}"
                resultado.append(entry)
                # Tripulação
                tripulacao = buscar_tripulantes_da_nave(n.get('slug',''))
                for m_t in tripulacao[:8]:
                    mt = ad(m_t)
                    resultado.append(f"[TRIPULACAO {nt_data['nome']}] {mt['nome']} | {mt['posto']}")
                found_nave = True

        if not found_nave and any(w in msg_lower for w in ['naves', 'esquadra', 'frota']):
            for n in naves:
                nt_data = ad(n)
                resultado.append(f"[NAVE] {nt_data['nome']} | Cmd: {nt_data['comandante']} | {nt_data['status']}")

    # ── 4. Divisões ───────────────────────────────────────────────────────────
    div_kw = ['divisao', 'comando', 'academia', 'ciencias', 'comunicacoes',
              'engenharia', 'operacoes', 'tatico', 'civil']
    if any(w in msg_lower for w in div_kw):
        divs = listar_divisoes()
        for d in divs:
            dname = fa(d.get('nome','')).lower()
            if dname and dname in msg_lower:
                dd = ad(d)
                resultado.append(
                    f"[DIVISAO] {dd['nome']} | Chefe: {dd.get('chefe','?')} | "
                    f"Tripulantes: {dd.get('qtd_tripulantes','?')} | {dd.get('descricao','')}"
                )

    # ── 5. Missões recentes ───────────────────────────────────────────────────
    if any(w in msg_lower for w in ['missao', 'operacao', 'ultima missao', 'recente']):
        missoes = listar_missoes(limite=3)
        for m in missoes:
            mm = ad(m)
            resultado.append(f"[MISSAO] {mm['titulo']} | Data: {mm.get('data','')} | {mm.get('resumo','')}")

    # ── 6. Histórico de pontos recente ────────────────────────────────────────
    if speaker_slug and any(w in msg_lower for w in ['historico', 'ultimo', 'recente',
                                                      'pontos', 'ganhou', 'registro']):
        hist = buscar_historico_pontos(speaker_slug, limite=5)
        for h in hist:
            hh = ad(h)
            resultado.append(f"[HIST PONTOS] {hh.get('data','')} | +{hh.get('pontos',0)} pts | {hh.get('motivo','')}")

    if not resultado:
        return "SEM_DADOS", 404, {'Content-Type': 'text/plain; charset=ascii'}

    return "\n".join(resultado), 200, {'Content-Type': 'text/plain; charset=ascii'}


# ═══════════════════════════════════════════════════════════════════════════════
#  ROTAS LEGADAS (compatibilidade)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/tripulante')
def get_tripulante():
    nome = request.args.get('nome', '').strip()
    if not nome:
        return jsonify({"erro": "Parametro 'nome' obrigatorio"}), 400
    resultado = buscar_tripulante(nome)
    if resultado:
        return jsonify(ad(resultado))
    return jsonify({"erro": f"Tripulante '{fa(nome)}' nao encontrado"}), 404


@app.route('/naves')
def get_naves():
    return jsonify([ad(n) for n in listar_naves()])


@app.route('/divisoes')
def get_divisoes():
    return jsonify([ad(d) for d in listar_divisoes()])


# ═══════════════════════════════════════════════════════════════════════════════
#  INIT
# ═══════════════════════════════════════════════════════════════════════════════

if not os.path.exists(DB_PATH):
    print("Banco nao encontrado. Inicializando...")
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)

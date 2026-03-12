"""
app.py — Flask API para a Lal Data NPC (Frota Venture)
Serve dados de tripulantes, divisoes, patentes, naves e lore em ASCII puro.
"""
import os
import unicodedata
from flask import Flask, request, jsonify
from database import (
    buscar_tripulante, listar_divisoes, buscar_divisao,
    listar_patentes, listar_naves, buscar_lore, buscar_nomes_na_mensagem,
    init_db, DB_PATH
)

app = Flask(__name__)


def forceASCII(text):
    """Remove acentos e caracteres nao-ASCII."""
    if not text:
        return ""
    text = ''.join(
        c for c in unicodedata.normalize('NFD', str(text))
        if unicodedata.category(c) != 'Mn'
    )
    return text.encode('ascii', 'ignore').decode('ascii')


def ascii_dict(d):
    """Converte todos os valores string de um dict para ASCII puro."""
    return {k: forceASCII(v) if isinstance(v, str) else v for k, v in d.items()}


# ===== ROTAS =====

@app.route('/health')
def health():
    return jsonify({"status": "online", "service": "lal-api", "version": "1.0"})


@app.route('/tripulante')
def get_tripulante():
    nome = request.args.get('nome', '').strip()
    if not nome:
        return jsonify({"erro": "Parametro 'nome' obrigatorio"}), 400

    resultado = buscar_tripulante(nome)
    if resultado:
        return jsonify(ascii_dict(resultado))
    else:
        return jsonify({"erro": f"Tripulante '{forceASCII(nome)}' nao encontrado"}), 404


@app.route('/divisao')
def get_divisao():
    nome = request.args.get('nome', '').strip()
    if not nome:
        # Listar todas
        divs = listar_divisoes()
        return jsonify([ascii_dict(d) for d in divs])

    resultado = buscar_divisao(nome)
    if resultado:
        return jsonify(ascii_dict(resultado))
    else:
        return jsonify({"erro": f"Divisao '{forceASCII(nome)}' nao encontrada"}), 404


@app.route('/patentes')
def get_patentes():
    pats = listar_patentes()
    return jsonify([ascii_dict(p) for p in pats])


@app.route('/naves')
def get_naves():
    navs = listar_naves()
    return jsonify([ascii_dict(n) for n in navs])


@app.route('/lore')
def get_lore():
    tema = request.args.get('tema', '').strip()
    if not tema:
        return jsonify({"erro": "Parametro 'tema' obrigatorio. Ex: historia, academia, estacao"}), 400

    resultados = buscar_lore(tema)
    if resultados:
        return jsonify([ascii_dict(r) for r in resultados])
    else:
        return jsonify({"erro": f"Tema '{forceASCII(tema)}' nao encontrado"}), 404


# ===== ROTA COMPACTA PARA LSL =====
@app.route('/perfil')
def get_perfil():
    """
    Rota otimizada para LSL: retorna dados em texto plano compacto.
    Uso: /perfil?nome=sailespy2
    Retorno: Nome|Raca|Patente|Divisao|Tempo|Posto
    """
    nome = request.args.get('nome', '').strip()
    if not nome:
        return "ERRO:parametro nome obrigatorio", 400

    resultado = buscar_tripulante(nome)
    if resultado:
        r = ascii_dict(resultado)
        perfil = f"{r.get('nome','?')}|{r.get('raca','?')}|{r.get('patente','?')}|{r.get('divisao','?')}|{r.get('tempo_servico','?')}|{r.get('posto','?')}"
        return perfil, 200, {'Content-Type': 'text/plain; charset=ascii'}
    else:
        return f"NAO_ENCONTRADO:{forceASCII(nome)}", 404, {'Content-Type': 'text/plain; charset=ascii'}


# ===== ROTA RAG COMPLETA PARA LSL =====
@app.route('/rag')
def get_rag():
    """
    Rota inteligente para LSL: busca speaker + nomes citados na mensagem.
    Uso: /rag?speaker=sailespy2&msg=quem+e+elemer+piek
    Retorno: texto plano com contexto RAG completo.
    """
    speaker = request.args.get('speaker', '').strip()
    msg = request.args.get('msg', '').strip()

    if not speaker:
        return "ERRO:parametro speaker obrigatorio", 400

    resultado_rag = ""

    # 1. Buscar ficha do speaker
    speaker_data = buscar_tripulante(speaker)
    speaker_busca = ""
    if speaker_data:
        s = ascii_dict(speaker_data)
        speaker_busca = s.get('nome_busca', '')
        resultado_rag += f"[FALANTE {forceASCII(speaker)} e {s.get('raca','?')}, {s.get('patente','?')} da Divisao {s.get('divisao','?')}, serve ha {s.get('tempo_servico','?')}]. "

    # 2. Buscar nomes citados na mensagem
    if msg:
        citados = buscar_nomes_na_mensagem(msg, excluir_nome_busca=speaker_busca)
        for cit in citados:
            c = ascii_dict(cit)
            resultado_rag += f"[CITOU {c.get('nome_busca','?')}: {c.get('raca','?')} {c.get('patente','?')} ({c.get('divisao','?')}), serve ha {c.get('tempo_servico','?')}, posto: {c.get('posto','?')}]. "

    if not resultado_rag:
        return "SEM_DADOS", 404, {'Content-Type': 'text/plain; charset=ascii'}

    return resultado_rag, 200, {'Content-Type': 'text/plain; charset=ascii'}


# ===== INIT =====
if not os.path.exists(DB_PATH):
    print("Banco nao encontrado. Inicializando...")
    init_db()
    # Tenta importar dados
    try:
        from import_data import importar_tripulantes, popular_divisoes, popular_patentes, popular_naves, popular_lore
        importar_tripulantes()
        popular_divisoes()
        popular_patentes()
        popular_naves()
        popular_lore()
    except Exception as e:
        print(f"Erro ao importar dados: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)

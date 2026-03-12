"""
import_data.py — Importa frotaventure_db.json para o SQLite e popula tabelas de lore.
Executar: python import_data.py
"""
import json
import os
import re
import unicodedata
from database import init_db, get_db, DB_PATH

# ========== UTILIDADES ==========
def remover_acentos(text):
    if not text:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(text))
        if unicodedata.category(c) != 'Mn'
    )

def fix_double_encoding(text):
    """Tenta corrigir double-encoded UTF-8 (ex: Ã£ -> ã -> a)."""
    if not text:
        return ""
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text

def forceASCII(text):
    if not text:
        return ""
    text = fix_double_encoding(str(text))
    return remover_acentos(text).encode('ascii', 'ignore').decode('ascii')

def limpar_nome(nome_raw):
    """Remove patentes, titulos e 'Resident' do nome."""
    nome = remover_acentos(nome_raw).strip().lower()
    nome = nome.replace(" resident", "")

    patentes = [
        'almirante', 'comodoro', 'comandante', 'capitao',
        'tenente', 'alferes', 'cadete', 'chefe', 'recruta', 'tripulante'
    ]
    partes = nome.split()
    if len(partes) > 1 and partes[0] in patentes:
        partes = partes[1:]
        if len(partes) > 0 and partes[0] in ['junior', 'comandante', 'classe']:
            partes = partes[1:]
            if len(partes) > 0 and partes[0] in ['1', '2', '3']:
                partes = partes[1:]

    return " ".join(partes).strip()


# ========== IMPORTAR TRIPULANTES ==========
def importar_tripulantes():
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frotaventure_db.json')
    if not os.path.exists(json_path):
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frotaventure_db.json')

    with open(json_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    conn = get_db()
    conn.execute("DELETE FROM tripulantes")

    count = 0
    for membro in db:
        nome_completo = membro.get('Nome Completo', '')
        nome_busca = limpar_nome(nome_completo)

        if not nome_busca or nome_busca == '(indefinido)':
            continue

        raca = forceASCII(membro.get('Raça', 'N/A'))
        patente = forceASCII(membro.get('Patente Atual', 'N/A'))
        divisao = forceASCII(membro.get('Divisão Atual', 'N/A'))
        departamento = forceASCII(membro.get('Departamento Atual', 'N/A'))
        posto = forceASCII(membro.get('Posto Atual', 'N/A'))
        tempo = forceASCII(membro.get('Tempo de Serviço', 'N/A'))
        data_adm = membro.get('Data Admissão', 'N/A')
        nascimento = membro.get('Nascimento SL', 'N/A')
        cidade = forceASCII(membro.get('Cidade', 'N/A'))

        # Carreira: juntar todos os eventos em um bloco de texto
        carreira_list = membro.get('Carreira na USS Venture', [])
        carreira = " | ".join([forceASCII(c) for c in carreira_list[:15]])  # Max 15 events

        conn.execute("""INSERT INTO tripulantes
            (nome, nome_busca, raca, patente, divisao, departamento, posto,
             tempo_servico, data_admissao, nascimento_sl, cidade, carreira)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (forceASCII(nome_completo), nome_busca, raca, patente, divisao,
             departamento, posto, tempo, data_adm, nascimento, cidade, carreira)
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"Importados {count} tripulantes para o banco de dados.")


# ========== POPULAR DIVISOES ==========
def popular_divisoes():
    divisoes_data = [
        ("Comando", "vermelho", 3, "Esta divisao compreende os oficiais mais graduados do Grupo."),
        ("Academia", "cinza", 5, "Tripulantes em treinamento ou que ainda nao foram designados a nenhuma divisao especifica, bem como os que estao fazendo a reciclagem."),
        ("Ciencias", "azul", 5, "Responsavel por lidar com todos os experimentos cientificos do Grupo USS Venture e pelo desenvolvimento de novas tecnologias. Pesquisa, Equipamentos e Astronomia sao alguns dos departamentos."),
        ("Comunicacoes", "verde", 1, "Responsavel pela emissao de Press Releases, pronunciamentos e manter a presenca do Grupo nos diversos meios de comunicacao seja no SL ou na Web."),
        ("Engenharia", "amarelo", 4, "Divisao dos construtores/criadores do Grupo. Responsaveis por construir e manter todas as estruturas, naves, artes, armas dentro do grupo."),
        ("Operacoes", "amarelo", 2, "Cuida das operacoes do dia-a-dia do Grupo. Inclui Pessoal, Suprimentos e Logistica, Eventos e Treinamentos. Coordena Simulacoes e Roleplaying (RPG)."),
        ("Tatico", "vermelho", 2, "Responsavel por desenvolver as taticas de combate e defesa, pessoais bem como nas estacoes e naves. Desenvolver e treinar o uso de armamentos."),
        ("Civil", "nao aplicavel", 1, "Pessoal pertencente ao grupo porem nao faz parte da Frota Estelar."),
        ("Reserva", "nao aplicavel", 0, "Oficiais que nao estao em servico ativo. Podem ser convocados para missoes especiais ou eventos."),
    ]

    conn = get_db()
    conn.execute("DELETE FROM divisoes")
    for nome, cor, qtd, desc in divisoes_data:
        conn.execute("INSERT INTO divisoes (nome, cor, qtd_tripulantes, descricao) VALUES (?, ?, ?, ?)",
                     (nome, cor, qtd, desc))
    conn.commit()
    conn.close()
    print(f"Populadas {len(divisoes_data)} divisoes.")


# ========== POPULAR PATENTES ==========
def popular_patentes():
    patentes_data = [
        ("Almirante", 1, "Patente mais alta da Frota Venture. Responsavel pelo comando geral."),
        ("Comodoro", 2, "Oficial superior responsavel por coordenar esquadras ou divisoes estrategicas."),
        ("Capitao", 3, "Comandante de nave estelar. Autoridade maxima a bordo."),
        ("Comandante", 4, "Segundo em comando. Pode assumir o comando na ausencia do Capitao."),
        ("Tenente Comandante", 5, "Oficial intermediario entre Tenente e Comandante. Geralmente chefes de departamento."),
        ("Tenente", 6, "Oficial com experiencia. Lidera equipes e participa de missoes criticas."),
        ("Tenente Junior", 7, "Oficial em desenvolvimento. Apoia tenentes e comandantes em suas funcoes."),
        ("Alferes", 8, "Primeiro posto oficial apos a graduacao na Academia. Inicio da carreira ativa."),
        ("Cadete", 9, "Tripulante em treinamento na Academia da Venture."),
        ("Tripulante Classe 2", 10, "Tripulante em fase inicial de integracao ao grupo."),
        ("Tripulante Classe 3", 11, "Tripulante recem-admitido no grupo."),
        ("Recruta", 12, "Nivel inicial. Recem-chegado ao Grupo USS Venture."),
    ]

    conn = get_db()
    conn.execute("DELETE FROM patentes")
    for nome, hierarquia, desc in patentes_data:
        conn.execute("INSERT INTO patentes (nome, hierarquia, descricao) VALUES (?, ?, ?)",
                     (nome, hierarquia, desc))
    conn.commit()
    conn.close()
    print(f"Populadas {len(patentes_data)} patentes.")


# ========== POPULAR NAVES ==========
def popular_naves():
    naves_data = [
        ("USS Venture NCC 71854", "Sovereign", "2008", "Almirante Elemer Piek", "Capitania", "Ativa", "Nave Capitania da Frota Venture. Principal nave do grupo."),
        ("USS Adventure", "Nao informada", "2010", "Nao informado", "Exploracao", "Ativa", "Lema: Buscando novos caminhos..."),
        ("USS Altotting", "Nao informada", "2022", "Capitao RonnAndrew", "Patrulhamento", "Ativa", "Nave de patrulhamento comissionada em 2022."),
        ("USS Andor NX 92095", "Nao informada", "2010", "Nao informado", "Exploracao", "Descomissionada (2014)", "Nave de exploracao descomissionada em 2014."),
        ("USS Nautilus", "Nao informada", "2010", "Nao informado", "Cientifica", "Ativa", "Nave cientifica da frota."),
        ("USS Rerum", "Nao informada", "2017", "Capitao Jeff", "Nao informado", "Ativa", "Comissionada em 2017."),
        ("USS Serenity", "Nao informada", "2022", "Comandante Marchezini", "Explorador", "Ativa", "Nave exploradora comandada por March7777 (Marchezini)."),
        ("USS Suidara", "Nao informada", "2014", "Nao informado", "Nao informado", "Ativa", "Comissionada em 2014."),
    ]

    conn = get_db()
    conn.execute("DELETE FROM naves")
    for nome, classe, com, cmd, tipo, status, desc in naves_data:
        conn.execute("""INSERT INTO naves
            (nome, classe, comissionamento, comandante, tipo, status, descricao)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (nome, classe, com, cmd, tipo, status, desc))
    conn.commit()
    conn.close()
    print(f"Populadas {len(naves_data)} naves.")


# ========== POPULAR LORE ==========
def popular_lore():
    lore_data = [
        ("historia", "A Frota Venture e um grupo brasileiro de roleplay Star Trek no Second Life, fundado em 2008. Sediada na Estacao SB-245 em orbita de Nova Trivas, na land Trivas do Second Life. O grupo simula operacoes da Frota Estelar no seculo 24, com tripulantes de diversas especies. O Almirante Elemer Piek e o Comodoro RonnAndrew sao os oficiais fundadores."),
        ("estacao", "A Estacao SB-245 e a base principal da Frota Venture. Orbita o planeta Nova Trivas no sistema Neural. Abriga o quartel-general do grupo, areas de treinamento da Academia, laboratorios de Ciencias e baia de naves. E o ponto de encontro principal dos tripulantes."),
        ("academia", "A Academia da Venture e responsavel pelo treinamento de novos tripulantes. Cadetes passam por cursos antes de serem promovidos a Alferes. Areas de estudo incluem procedimentos da Frota, combate tatico, ciencias e engenharia. A Comandante Achila16 e a atual chefe da Academia."),
        ("localizacao", "A Frota Venture opera na land Trivas no Second Life. Endereco direto: https://slurl.com/secondlife/Trivas/125/125/600/. Ao chegar, procure pelos tripulantes Elemer Piek ou RonnAndrew para orientacao inicial."),
        ("fanfilme", "O grupo produziu o primeiro fanfilme brasileiro sobre Star Trek: 'Star Trek USS Andor - Phoenix' partes 1 e 2. Disponivel na pagina oficial do grupo."),
        ("ingresso", "Para ingressar na Frota Venture: 1) Crie uma conta gratuita no Second Life (secondlife.com). 2) Baixe o navegador do SL. 3) Visite a Land Trivas. 4) Procure Elemer Piek ou RonnAndrew. 5) Voce entrara como Cadete e apos curso na Academia sera promovido a Alferes."),
    ]

    conn = get_db()
    conn.execute("DELETE FROM lore")
    for tema, conteudo in lore_data:
        conn.execute("INSERT INTO lore (tema, conteudo) VALUES (?, ?)", (tema, conteudo))
    conn.commit()
    conn.close()
    print(f"Populados {len(lore_data)} itens de lore.")


# ========== MAIN ==========
if __name__ == '__main__':
    # Limpa banco antigo se existir
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Banco anterior removido.")

    init_db()
    importar_tripulantes()
    popular_divisoes()
    popular_patentes()
    popular_naves()
    popular_lore()
    print("\nBanco de dados completo! Pronto para deploy.")

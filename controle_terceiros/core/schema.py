"""Estrutura do banco de dados (abas da planilha Google) e dados iniciais.

Para acrescentar um campo novo, basta incluir o nome da coluna na lista da
tabela: o sistema cria a coluna na planilha automaticamente na próxima execução.
"""

TABELAS = {
    "fornecedores": ["id", "nome", "razao_social", "cnpj", "contato", "telefone", "email",
                     "cidade", "servicos", "lead_time_dias", "ativo", "observacoes",
                     "criado_em", "criado_por", "atualizado_em"],
    "servicos": ["id", "nome", "descricao", "ativo", "criado_em", "criado_por", "atualizado_em"],
    "produtos": ["id", "nome", "codigo", "descricao", "ativo", "criado_em", "criado_por", "atualizado_em"],
    "envios": ["id", "data", "fornecedor", "servico", "produto", "quantidade", "nf", "op",
               "corrida", "responsavel", "observacao", "criado_em", "criado_por", "atualizado_em"],
    "recebimentos": ["id", "data", "fornecedor", "servico", "produto", "qtd_aprovada",
                     "qtd_nao_conforme", "qtd_sucata", "motivo_nc", "nf_retorno", "nf_referencia",
                     "responsavel", "observacao", "criado_em", "criado_por", "atualizado_em"],
    "programacao": ["id", "data", "fornecedor", "servico", "produto", "qtd_prevista",
                    "criado_em", "criado_por"],
    "usuarios": ["usuario", "nome", "senha_hash", "perfil", "ativo", "criado_em"],
}

CHAVE = {t: ("usuario" if t == "usuarios" else "id") for t in TABELAS}

PREFIXO_ID = {
    "fornecedores": "FOR", "servicos": "SRV", "produtos": "PRD",
    "envios": "ENV", "recebimentos": "REC", "programacao": "PRG",
}

NUMERICOS = {
    "fornecedores": ["lead_time_dias"],
    "envios": ["quantidade"],
    "recebimentos": ["qtd_aprovada", "qtd_nao_conforme", "qtd_sucata"],
    "programacao": ["qtd_prevista"],
}

DATAS = {"envios": ["data"], "recebimentos": ["data"], "programacao": ["data"]}

PERFIS = {
    "admin": "Administrador (tudo, inclusive cadastros e usuários)",
    "operador": "Operador (registra envios/recebimentos e corrige os próprios)",
    "consulta": "Consulta (somente visualiza)",
}

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
DIAS_CURTO = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

MOTIVOS_NC = ["Dimensional fora de tolerância", "Acabamento superficial",
              "Trinca / defeito de material", "Batida / dano no transporte",
              "Falta de usinagem", "Erro de identificação", "Outro"]

# ---- Dados iniciais (inseridos só quando a aba está vazia) -------------------
SERV_CANECA = "Usinagem de caneca bruta"
SERV_PERFIL = "Usinagem de perfil acabado"
PRODUTO_PADRAO = "Casco 155 Estendida"

SEED = {
    "servicos": [
        {"nome": SERV_CANECA, "descricao": "Canecas brutas enviadas para usinagem", "ativo": "Sim"},
        {"nome": SERV_PERFIL, "descricao": "Canecas ogivadas para usinagem do perfil acabado", "ativo": "Sim"},
    ],
    "produtos": [
        {"nome": PRODUTO_PADRAO, "codigo": "CASCO-155-EST", "descricao": "Casco 155 Estendida", "ativo": "Sim"},
    ],
    "fornecedores": [
        {"nome": n, "servicos": SERV_CANECA, "ativo": "Sim", "lead_time_dias": ""}
        for n in ["LOTUS", "MARBOM", "LEMOR", "DELAVI"]
    ] + [
        {"nome": n, "servicos": SERV_PERFIL, "ativo": "Sim", "lead_time_dias": ""}
        for n in ["UNIFORJA", "MNG"]
    ],
}
